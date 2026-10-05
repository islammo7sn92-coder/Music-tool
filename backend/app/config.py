"""Runtime configuration. Everything can be overridden with environment variables."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


UPLOADS_DIR = Path(os.environ.get("UPLOADS_DIR", ROOT / "uploads"))
OUTPUTS_DIR = Path(os.environ.get("OUTPUTS_DIR", ROOT / "outputs"))
TEMP_DIR = Path(os.environ.get("TEMP_DIR", ROOT / "temp"))
MODELS_DIR = Path(os.environ.get("MODELS_DIR", ROOT / "models"))
FRONTEND_DIST = Path(os.environ.get("FRONTEND_DIST", ROOT / "frontend" / "dist"))

# Limits
MAX_UPLOAD_MB = _int("MAX_UPLOAD_MB", 500)            # maximum size of an uploaded file
MAX_DURATION_MIN = _int("MAX_DURATION_MIN", 60)       # maximum media duration
RETENTION_MINUTES = _int("RETENTION_MINUTES", 30)     # how long finished results stay on disk
PROCESS_TIMEOUT_SEC = _int("PROCESS_TIMEOUT_SEC", 3600)  # hard limit per job
CONCURRENT_JOBS = max(1, _int("CONCURRENT_JOBS", 1))  # separation is heavy: keep this low

# Separation model (htdemucs = fast + great, htdemucs_ft = slower, a bit better)
DEMUCS_MODEL = os.environ.get("DEMUCS_MODEL", "htdemucs")
DEMUCS_DEVICE = os.environ.get("DEMUCS_DEVICE", "auto")  # auto | cpu | cuda
DEMUCS_SHIFTS = _int("DEMUCS_SHIFTS", 1)              # >1 = better quality, proportionally slower
DEMUCS_SEGMENT = os.environ.get("DEMUCS_SEGMENT", "")  # seconds; lower it to save RAM/VRAM
DEMUCS_JOBS = _int("DEMUCS_JOBS", 0)                  # CPU threads (0 = default)
# htdemucs_ft is a bag of 4 models, so progress runs through 4 bars
DEMUCS_BAG_SIZE = 4 if DEMUCS_MODEL.endswith("_ft") else 1

ALLOWED_ORIGINS = [o for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o]

EXPORT_FORMATS = {
    "wav": {"ext": "wav"},
    "mp3_320": {"ext": "mp3", "bitrate": "320k"},
    "mp3_192": {"ext": "mp3", "bitrate": "192k"},
    "mp3_128": {"ext": "mp3", "bitrate": "128k"},
}
MODES = {"instrumental": "no_vocals", "vocals": "vocals"}

for _d in (UPLOADS_DIR, OUTPUTS_DIR, TEMP_DIR, MODELS_DIR):
    _d.mkdir(parents=True, exist_ok=True)
