"""FFmpeg / FFprobe helpers. All work happens on temporary files on disk (no big buffers in RAM)."""
import errno
import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from . import config
from .errors import (Cancelled, CorruptFile, DiskFull, ExtractFailed, FFmpegFailed,
                     Timeout, UnsupportedFile)

# A job can register its running subprocess here so it can be cancelled.
ProcHook = Callable[[Optional[subprocess.Popen]], None]


@dataclass
class MediaInfo:
    duration: float
    has_video: bool
    has_audio: bool
    audio_codec: str
    bits: int  # bits per sample of the source audio (0 if unknown/lossy)
    video_codec: str


def ffmpeg_available() -> bool:
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def probe(path: Path) -> MediaInfo:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
            capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        raise CorruptFile("ffprobe timeout")
    except FileNotFoundError:
        raise FFmpegFailed("ffprobe not installed")
    if r.returncode != 0:
        raise UnsupportedFile(r.stderr.strip()[-300:])
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise CorruptFile("bad ffprobe output")
    streams = data.get("streams", [])
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    # attached cover art ("video" stream of an mp3/m4a) is not a real video
    video = next((s for s in streams if s.get("codec_type") == "video"
                  and not s.get("disposition", {}).get("attached_pic")), None)
    if not streams or (audio is None and video is None):
        raise UnsupportedFile("no media streams")
    try:
        duration = float(data.get("format", {}).get("duration") or (audio or {}).get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    bits = 0
    if audio:
        try:
            bits = int(audio.get("bits_per_raw_sample") or audio.get("bits_per_sample") or 0)
        except ValueError:
            bits = 0
    return MediaInfo(duration, video is not None, audio is not None,
                     (audio or {}).get("codec_name", ""), bits, (video or {}).get("codec_name", ""))


def run_ffmpeg(args: list[str], *, deadline: float, hook: ProcHook, error_cls=FFmpegFailed) -> None:
    """Run ffmpeg to completion, honouring a deadline and cancellation."""
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", *args]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError:
        raise FFmpegFailed("ffmpeg not installed")
    hook(proc)
    try:
        while True:
            try:
                _, err = proc.communicate(timeout=1)
                break
            except subprocess.TimeoutExpired:
                if getattr(proc, "_cancelled", False):
                    raise Cancelled()
                if time.time() > deadline:
                    proc.kill()
                    proc.communicate()
                    raise Timeout()
    finally:
        hook(None)
    if getattr(proc, "_cancelled", False):
        raise Cancelled()
    if proc.returncode != 0:
        if "No space left" in (err or ""):
            raise DiskFull(err)
        raise error_cls((err or "")[-500:])


def extract_audio(src: Path, dst_wav: Path, *, deadline: float, hook: ProcHook) -> None:
    """Decode any audio/video container into 44.1 kHz stereo 32-bit-float WAV (Demucs' native format)."""
    run_ffmpeg(["-i", str(src), "-vn", "-map", "0:a:0", "-ac", "2", "-ar", "44100",
                "-c:a", "pcm_f32le", str(dst_wav)],
               deadline=deadline, hook=hook, error_cls=ExtractFailed)


def encode_audio(src_wav: Path, dst: Path, fmt: str, bits: int, *, deadline: float, hook: ProcHook) -> None:
    spec = config.EXPORT_FORMATS[fmt]
    if spec["ext"] == "wav":
        codec = "pcm_s24le" if bits > 16 else "pcm_s16le"
        args = ["-i", str(src_wav), "-c:a", codec, str(dst)]
    else:
        args = ["-i", str(src_wav), "-c:a", "libmp3lame", "-b:a", spec["bitrate"], "-id3v2_version", "3", str(dst)]
    run_ffmpeg(args, deadline=deadline, hook=hook)


def make_preview(src: Path, dst_mp3: Path, *, deadline: float, hook: ProcHook) -> None:
    """Small, universally playable preview (iOS Safari plays MP3 with range requests)."""
    run_ffmpeg(["-i", str(src), "-vn", "-c:a", "libmp3lame", "-b:a", "160k", str(dst_mp3)],
               deadline=deadline, hook=hook)


def mux_video(video_src: Path, audio: Path, dst: Path, fmt: str, *, deadline: float, hook: ProcHook) -> None:
    """Replace the audio track of `video_src` with `audio`, copying the picture untouched."""
    spec = config.EXPORT_FORMATS[fmt]
    abr = spec.get("bitrate", "320k")
    base = ["-i", str(video_src), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0",
            "-c:a", "aac", "-b:a", abr, "-shortest", "-movflags", "+faststart"]
    try:
        run_ffmpeg([*base[:6], "-c:v", "copy", *base[6:], str(dst)], deadline=deadline, hook=hook)
    except FFmpegFailed:
        # picture codec not allowed in this container -> re-encode it as H.264
        run_ffmpeg([*base[:6], "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
                    "-pix_fmt", "yuv420p", *base[6:], str(dst)], deadline=deadline, hook=hook)


def is_enospc(exc: BaseException) -> bool:
    return isinstance(exc, OSError) and exc.errno == errno.ENOSPC
