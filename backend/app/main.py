"""FastAPI application: upload -> job -> poll -> preview/download."""
import logging
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, media, separator
from .jobs import JobManager, purge_all_storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("api")

CHUNK = 1024 * 1024
manager: JobManager


@asynccontextmanager
async def lifespan(_: FastAPI):
    global manager
    purge_all_storage()
    manager = JobManager()
    if not media.ffmpeg_available():
        log.error("ffmpeg/ffprobe not found in PATH - install FFmpeg!")
    yield


app = FastAPI(title="Vocal / Music Separator", lifespan=lifespan)
if config.ALLOWED_ORIGINS:
    app.add_middleware(CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS,
                       allow_methods=["*"], allow_headers=["*"])


def _err(status: int, code: str) -> JSONResponse:
    return JSONResponse({"error": code}, status_code=status)


@app.get("/api/config")
def get_config():
    return {"max_upload_mb": config.MAX_UPLOAD_MB, "max_duration_min": config.MAX_DURATION_MIN,
            "retention_minutes": config.RETENTION_MINUTES, "model": config.DEMUCS_MODEL,
            "formats": list(config.EXPORT_FORMATS), "device": separator.resolve_device()}


@app.get("/api/health")
def health():
    return {"ok": True, "ffmpeg": media.ffmpeg_available(),
            "free_gb": round(shutil.disk_usage(config.TEMP_DIR).free / 1e9, 1)}


@app.post("/api/jobs")
async def create_job(request: Request, file: UploadFile = File(...), mode: str = Form(...),
                     format: str = Form("wav"), keep_video: bool = Form(False)):
    if mode not in config.MODES or format not in config.EXPORT_FORMATS:
        return _err(400, "bad_request")
    limit = config.MAX_UPLOAD_MB * 1024 * 1024
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit + 1024 * 1024:
        return _err(413, "too_large")

    job = manager.create(mode, format, keep_video, file.filename or "audio")
    size = 0
    try:
        with open(job.src, "wb") as out:
            while chunk := await file.read(CHUNK):   # streamed in 1 MiB pieces
                size += len(chunk)
                if size > limit:
                    manager.delete(job.id)
                    return _err(413, "too_large")
                out.write(chunk)
    except OSError as e:
        manager.delete(job.id)
        return _err(507 if media.is_enospc(e) else 500, "disk_full" if media.is_enospc(e) else "internal")
    finally:
        await file.close()
    if size == 0:
        manager.delete(job.id)
        return _err(400, "corrupt")

    manager.submit(job)
    return {"id": job.id}


def _job_or_404(job_id: str):
    job = manager.get(job_id)
    if not job:
        raise HTTPException(404, "not_found")
    return job


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = _job_or_404(job_id)
    return JSONResponse(job.public(manager.position(job)), headers={"Cache-Control": "no-store"})


@app.get("/api/jobs/{job_id}/preview")
def job_preview(job_id: str):
    job = _job_or_404(job_id)
    if job.status != "done" or not job.preview:
        raise HTTPException(409, "not_ready")
    return FileResponse(job.preview, headers={"Cache-Control": "no-store"})  # supports HTTP Range


@app.get("/api/jobs/{job_id}/download")
def job_download(job_id: str):
    job = _job_or_404(job_id)
    if job.status != "done" or not job.result:
        raise HTTPException(409, "not_ready")
    # `filename=` makes Starlette send Content-Disposition: attachment (RFC 5987 for Arabic names),
    # which makes iOS Safari, Android Chrome and desktop browsers all save the file.
    return FileResponse(job.result, filename=job.result_name, headers={"Cache-Control": "no-store"})


@app.delete("/api/jobs/{job_id}")
def job_delete(job_id: str):
    manager.delete(job_id)
    return {"ok": True}


# Serve the built frontend (single-server deployment). In dev, Vite serves it instead.
if config.FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIST, html=True), name="web")
