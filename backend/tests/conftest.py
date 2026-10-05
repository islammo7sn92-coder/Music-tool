import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Isolated storage + a *fake* demucs so the pipeline can be tested without the 80 MB model.
_tmp = Path(tempfile.mkdtemp(prefix="sep-test-"))
for name in ("UPLOADS", "OUTPUTS", "TEMP", "MODELS"):
    os.environ[f"{name}_DIR"] = str(_tmp / name.lower())
os.environ["RETENTION_MINUTES"] = "1"
os.environ["MAX_UPLOAD_MB"] = "5"
os.environ["FRONTEND_DIST"] = str(_tmp / "nodist")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def sine_wav(tmp_path_factory):
    p = tmp_path_factory.mktemp("media") / "tone.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                    "-ac", "2", "-ar", "44100", str(p)], check=True)
    return p


@pytest.fixture(scope="session")
def sample_mp4(tmp_path_factory, sine_wav):
    p = tmp_path_factory.mktemp("media") / "clip.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=160x120:rate=10:duration=3",
                    "-i", str(sine_wav), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(p)],
                   check=True)
    return p
