"""Job store, worker threads and the processing pipeline."""
import logging
import queue
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import config, media, separator
from .errors import Cancelled, DiskFull, JobError, SeparationFailed, TooLong

log = logging.getLogger("jobs")

STAGES = ("queued", "analyzing", "separating", "finalizing", "done")


@dataclass
class Job:
    id: str
    mode: str
    fmt: str
    keep_video: bool
    original_name: str
    src: Path
    created: float = field(default_factory=time.time)
    finished: Optional[float] = None
    status: str = "queued"          # queued | processing | done | error
    stage: str = "queued"
    progress: float = 0.0           # 0..100 of server-side work
    error: Optional[str] = None
    result: Optional[Path] = None
    preview: Optional[Path] = None
    result_name: str = ""
    result_kind: str = "audio"      # audio | video
    proc: Optional[subprocess.Popen] = None
    cancelled: bool = False

    @property
    def dirs(self) -> list[Path]:
        return [config.UPLOADS_DIR / self.id, config.TEMP_DIR / self.id, config.OUTPUTS_DIR / self.id]

    def public(self, position: int = 0) -> dict:
        d = {"id": self.id, "status": self.status, "stage": self.stage,
             "progress": round(self.progress, 1), "error": self.error, "queue_position": position}
        if self.status == "done":
            d.update(filename=self.result_name, kind=self.result_kind,
                     expires_in=max(0, int(self.finished + config.RETENTION_MINUTES * 60 - time.time())))
        return d


class JobManager:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.lock = threading.Lock()
        self.q: "queue.Queue[str]" = queue.Queue()
        self.waiting: list[str] = []
        self._stop = threading.Event()
        for i in range(config.CONCURRENT_JOBS):
            threading.Thread(target=self._worker, name=f"worker-{i}", daemon=True).start()
        threading.Thread(target=self._janitor, name="janitor", daemon=True).start()

    # ---- public API -------------------------------------------------------
    def create(self, mode: str, fmt: str, keep_video: bool, original_name: str) -> Job:
        job_id = uuid.uuid4().hex
        (config.UPLOADS_DIR / job_id).mkdir(parents=True)
        job = Job(job_id, mode, fmt, keep_video, original_name, config.UPLOADS_DIR / job_id / "source")
        with self.lock:
            self.jobs[job_id] = job
        return job

    def submit(self, job: Job) -> None:
        with self.lock:
            self.waiting.append(job.id)
        self.q.put(job.id)

    def get(self, job_id: str) -> Optional[Job]:
        return self.jobs.get(job_id)

    def position(self, job: Job) -> int:
        with self.lock:
            return self.waiting.index(job.id) + 1 if job.id in self.waiting else 0

    def delete(self, job_id: str) -> None:
        job = self.jobs.get(job_id)
        if not job:
            return
        job.cancelled = True
        if job.proc is not None:
            job.proc._cancelled = True  # type: ignore[attr-defined]
            try:
                job.proc.kill()
            except OSError:
                pass
        if job.status != "processing":
            self._remove(job)

    # ---- internals --------------------------------------------------------
    def _remove(self, job: Job) -> None:
        for d in job.dirs:
            shutil.rmtree(d, ignore_errors=True)
        with self.lock:
            self.jobs.pop(job.id, None)
            if job.id in self.waiting:
                self.waiting.remove(job.id)

    def _set(self, job: Job, stage: str, progress: float) -> None:
        job.stage, job.progress = stage, max(job.progress, progress)

    def _worker(self) -> None:
        while not self._stop.is_set():
            job_id = self.q.get()
            with self.lock:
                if job_id in self.waiting:
                    self.waiting.remove(job_id)
            job = self.jobs.get(job_id)
            if job is None or job.cancelled:
                if job:
                    self._remove(job)
                continue
            self._run(job)

    def _hook(self, job: Job):
        def hook(proc):
            job.proc = proc
            if proc is not None and job.cancelled:
                proc._cancelled = True  # type: ignore[attr-defined]
                proc.kill()
        return hook

    def _run(self, job: Job) -> None:
        job.status = "processing"
        deadline = time.time() + config.PROCESS_TIMEOUT_SEC
        hook = self._hook(job)
        work = config.TEMP_DIR / job.id
        out = config.OUTPUTS_DIR / job.id
        try:
            work.mkdir(parents=True, exist_ok=True)
            out.mkdir(parents=True, exist_ok=True)
            self._pipeline(job, work, out, deadline, hook)
            job.finished = time.time()
            job.status, job.stage, job.progress = "done", "done", 100.0
        except Cancelled:
            job.status = "error"
            job.error = "cancelled"
        except JobError as e:
            log.warning("job %s failed: %s (%s)", job.id, e.code, e.detail)
            job.status, job.error = "error", e.code
        except Exception as e:  # noqa: BLE001
            code = "disk_full" if media.is_enospc(e) else "internal"
            log.exception("job %s crashed", job.id)
            job.status, job.error = "error", code
        finally:
            job.finished = job.finished or time.time()
            # privacy: intermediates are never needed after the run
            shutil.rmtree(work, ignore_errors=True)
            if job.status != "done":
                shutil.rmtree(out, ignore_errors=True)
            shutil.rmtree(config.UPLOADS_DIR / job.id, ignore_errors=True)
            if job.cancelled:
                self._remove(job)

    def _pipeline(self, job: Job, work: Path, out: Path, deadline: float, hook) -> None:
        # disk space guard: need roughly 12x the upload size (float wavs + stems + output)
        need = job.src.stat().st_size * 12
        if shutil.disk_usage(config.TEMP_DIR).free < need:
            raise DiskFull("not enough free space")

        self._set(job, "analyzing", 2)
        info = media.probe(job.src)
        if not info.has_audio:
            raise media.ExtractFailed("no audio track")
        if info.duration > config.MAX_DURATION_MIN * 60:
            raise TooLong(f"{info.duration:.0f}s")
        keep_video = job.keep_video and info.has_video

        wav = work / "input.wav"
        media.extract_audio(job.src, wav, deadline=deadline, hook=hook)
        self._set(job, "separating", 8)

        def on_progress(frac: float) -> None:
            self._set(job, "separating", 8 + frac * 80)

        stems = separator.separate(wav, work / "demucs", deadline=deadline, hook=hook, on_progress=on_progress)
        wav.unlink(missing_ok=True)

        self._set(job, "finalizing", 90)
        stem = stems[config.MODES[job.mode]]
        suffix = "instrumental" if job.mode == "instrumental" else "vocals"
        base = _safe_stem(job.original_name)
        audio_ext = config.EXPORT_FORMATS[job.fmt]["ext"]
        audio_out = out / f"result.{audio_ext}"
        media.encode_audio(stem, audio_out, job.fmt, info.bits, deadline=deadline, hook=hook)
        self._set(job, "finalizing", 95)

        if keep_video:
            video_out = out / "result.mp4"
            media.mux_video(job.src, audio_out, video_out, job.fmt, deadline=deadline, hook=hook)
            audio_out.unlink(missing_ok=True)
            job.result, job.result_kind = video_out, "video"
            job.result_name = f"{base}_{suffix}.mp4"
            job.preview = video_out
        else:
            job.result, job.result_kind = audio_out, "audio"
            job.result_name = f"{base}_{suffix}.{audio_ext}"
            if audio_ext == "wav":
                preview = out / "preview.mp3"
                media.make_preview(audio_out, preview, deadline=deadline, hook=hook)
                job.preview = preview
            else:
                job.preview = audio_out

    def _janitor(self) -> None:
        while not self._stop.wait(30):
            now = time.time()
            ttl = config.RETENTION_MINUTES * 60
            for job in list(self.jobs.values()):
                if job.status in ("done", "error") and job.finished and now - job.finished > ttl:
                    self._remove(job)
                elif job.status in ("queued",) and now - job.created > ttl + config.PROCESS_TIMEOUT_SEC:
                    self._remove(job)
            # orphan directories (e.g. left over by a crash)
            known = set(self.jobs)
            for root in (config.UPLOADS_DIR, config.TEMP_DIR, config.OUTPUTS_DIR):
                for d in root.iterdir() if root.exists() else []:
                    if d.is_dir() and d.name not in known and now - d.stat().st_mtime > ttl:
                        shutil.rmtree(d, ignore_errors=True)


def purge_all_storage() -> None:
    """On start-up nothing from a previous run may survive."""
    for root in (config.UPLOADS_DIR, config.TEMP_DIR, config.OUTPUTS_DIR):
        for d in root.iterdir():
            if d.name == ".gitkeep":
                continue
            shutil.rmtree(d, ignore_errors=True) if d.is_dir() else d.unlink(missing_ok=True)


def _safe_stem(name: str) -> str:
    stem = Path(name).stem or "audio"
    stem = "".join(c for c in stem if c not in '\\/:*?"<>|\r\n\t\x00').strip(" .")
    return stem[:120] or "audio"
