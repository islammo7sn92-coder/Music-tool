import subprocess
import time

import pytest

from app import config, separator


@pytest.fixture(autouse=True)
def fake_model(monkeypatch):
    from pathlib import Path
    fake = str(Path(__file__).with_name("fake_demucs.py"))
    monkeypatch.setattr(separator, "build_command",
                        lambda wav, out, dev: [__import__("sys").executable, fake, "-n", config.DEMUCS_MODEL,
                                               "-o", str(out), str(wav)])


def submit(client, path, mode="instrumental", fmt="wav", keep_video=False, name=None):
    with open(path, "rb") as f:
        r = client.post("/api/jobs", files={"file": (name or path.name, f)},
                        data={"mode": mode, "format": fmt, "keep_video": str(keep_video).lower()})
    return r


def wait(client, job_id, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f"/api/jobs/{job_id}").json()
        if j["status"] in ("done", "error"):
            return j
        time.sleep(0.3)
    raise AssertionError("timeout")


def test_config_and_health(client):
    assert client.get("/api/config").json()["max_upload_mb"] == 5
    assert client.get("/api/health").json()["ffmpeg"] is True


@pytest.mark.parametrize("mode,suffix", [("instrumental", "instrumental"), ("vocals", "vocals")])
def test_wav_roundtrip(client, sine_wav, mode, suffix):
    r = submit(client, sine_wav, mode=mode, name="my song.wav")
    assert r.status_code == 200
    j = wait(client, r.json()["id"])
    assert j["status"] == "done", j
    assert j["filename"] == f"my song_{suffix}.wav"
    d = client.get(f"/api/jobs/{j['id']}/download")
    assert d.status_code == 200 and d.content[:4] == b"RIFF"
    assert "attachment" in d.headers["content-disposition"]
    p = client.get(f"/api/jobs/{j['id']}/preview", headers={"Range": "bytes=0-99"})
    assert p.status_code == 206  # seekable preview (needed by iOS Safari)


def test_mp3_export(client, sine_wav):
    j = wait(client, submit(client, sine_wav, fmt="mp3_192").json()["id"])
    assert j["status"] == "done" and j["filename"].endswith("_instrumental.mp3")


def test_video_keep(client, sample_mp4):
    j = wait(client, submit(client, sample_mp4, mode="vocals", keep_video=True).json()["id"])
    assert j["status"] == "done" and j["kind"] == "video" and j["filename"].endswith("_vocals.mp4")
    out = config.OUTPUTS_DIR / j["id"] / "result.mp4"
    streams = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(out)],
                             capture_output=True, text=True).stdout.split()
    assert sorted(streams) == ["audio", "video"]


def test_video_audio_only(client, sample_mp4):
    j = wait(client, submit(client, sample_mp4).json()["id"])
    assert j["status"] == "done" and j["kind"] == "audio" and j["filename"].endswith(".wav")


def test_unsupported_file(client, tmp_path):
    p = tmp_path / "x.mp3"
    p.write_bytes(b"this is not media" * 100)
    assert wait(client, submit(client, p).json()["id"])["error"] == "unsupported"


def test_empty_file(client, tmp_path):
    p = tmp_path / "e.wav"
    p.write_bytes(b"")
    r = submit(client, p)
    assert r.status_code == 400 and r.json()["error"] == "corrupt"


def test_too_large(client, tmp_path):
    p = tmp_path / "big.wav"
    p.write_bytes(b"0" * (6 * 1024 * 1024))
    r = submit(client, p)
    assert r.status_code == 413 and r.json()["error"] == "too_large"


def test_model_failure(client, sine_wav, monkeypatch):
    import sys
    monkeypatch.setattr(separator, "build_command",
                        lambda wav, out, dev: [sys.executable, "-c", "import sys; print('boom', file=sys.stderr); sys.exit(1)"])
    assert wait(client, submit(client, sine_wav).json()["id"])["error"] == "separation_failed"


def test_bad_mode(client, sine_wav):
    assert submit(client, sine_wav, mode="nope").status_code == 400


def test_delete_cleans_files(client, sine_wav):
    j = wait(client, submit(client, sine_wav).json()["id"])
    assert (config.OUTPUTS_DIR / j["id"]).exists()
    client.delete(f"/api/jobs/{j['id']}")
    assert not (config.OUTPUTS_DIR / j["id"]).exists()
    assert client.get(f"/api/jobs/{j['id']}").status_code == 404


def test_intermediates_removed(client, sine_wav):
    j = wait(client, submit(client, sine_wav).json()["id"])
    assert not (config.TEMP_DIR / j["id"]).exists()
    assert not (config.UPLOADS_DIR / j["id"]).exists()


def test_arabic_filename_download(client, sine_wav):
    j = wait(client, submit(client, sine_wav, name="أغنية جميلة.wav").json()["id"])
    assert j["filename"] == "أغنية جميلة_instrumental.wav"
    cd = client.get(f"/api/jobs/{j['id']}/download").headers["content-disposition"]
    assert "filename*=utf-8''" in cd.lower()
