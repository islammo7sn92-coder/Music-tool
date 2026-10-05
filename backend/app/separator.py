"""Demucs wrapper: runs the real neural source-separation model in a subprocess.

Running it as a subprocess keeps the API process light, lets us stream progress
from tqdm, enforce a timeout and kill it on cancel.
"""
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

from . import config
from .errors import Cancelled, DiskFull, SeparationFailed, Timeout
from .media import ProcHook

_PCT = re.compile(r"(\d{1,3})%\|")


def resolve_device() -> str:
    dev = config.DEMUCS_DEVICE
    if dev != "auto":
        return dev
    try:
        import torch  # noqa: WPS433 (lazy: only needed to pick a device)
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def build_command(wav: Path, out_dir: Path, device: str) -> list[str]:
    cmd = [sys.executable, "-m", "demucs", "--two-stems", "vocals", "-n", config.DEMUCS_MODEL,
           "-d", device, "--float32", "--shifts", str(config.DEMUCS_SHIFTS), "-o", str(out_dir)]
    if config.DEMUCS_SEGMENT:
        cmd += ["--segment", config.DEMUCS_SEGMENT]
    if config.DEMUCS_JOBS:
        cmd += ["-j", str(config.DEMUCS_JOBS)]
    return cmd + [str(wav)]


def separate(wav: Path, out_dir: Path, *, deadline: float, hook: ProcHook,
             on_progress: Callable[[float], None]) -> dict[str, Path]:
    """Returns {"vocals": path, "no_vocals": path}. `on_progress` gets 0..1."""
    out_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TORCH_HOME=str(config.MODELS_DIR), PYTHONUNBUFFERED="1")
    cmd = build_command(wav, out_dir, resolve_device())
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=env)
    except OSError as e:
        raise SeparationFailed(str(e))
    hook(proc)

    tail = bytearray()
    bar, last_pct = 0, 0
    buf = b""
    import selectors
    sel = selectors.DefaultSelector()
    sel.register(proc.stderr, selectors.EVENT_READ)
    try:
        while proc.poll() is None or buf:
            if getattr(proc, "_cancelled", False):
                raise Cancelled()
            if time.time() > deadline:
                proc.kill()
                proc.wait()
                raise Timeout()
            if sel.select(timeout=1):
                chunk = os.read(proc.stderr.fileno(), 4096)
                if not chunk:
                    break
                tail += chunk
                del tail[:-4000]
                buf += chunk
                parts = re.split(rb"[\r\n]", buf)
                buf = parts.pop()
                for line in parts:
                    m = _PCT.search(line.decode("utf-8", "ignore"))
                    if not m:
                        continue
                    pct = min(100, int(m.group(1)))
                    if pct < last_pct - 30:  # a new bar started (bag-of-models)
                        bar = min(bar + 1, config.DEMUCS_BAG_SIZE - 1)
                    last_pct = pct
                    on_progress(min(1.0, (bar + pct / 100) / config.DEMUCS_BAG_SIZE))
        proc.wait()
    finally:
        hook(None)
        sel.close()
        if proc.poll() is None:
            proc.kill()

    if getattr(proc, "_cancelled", False):
        raise Cancelled()
    text = tail.decode("utf-8", "ignore")
    if proc.returncode != 0:
        if "No space left" in text:
            raise DiskFull(text[-300:])
        raise SeparationFailed(text[-500:])

    stem_dir = out_dir / config.DEMUCS_MODEL / wav.stem
    stems = {"vocals": stem_dir / "vocals.wav", "no_vocals": stem_dir / "no_vocals.wav"}
    if not all(p.is_file() for p in stems.values()):
        raise SeparationFailed("model produced no output: " + text[-300:])
    return stems
