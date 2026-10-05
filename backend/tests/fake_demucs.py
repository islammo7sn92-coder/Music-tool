"""Stand-in for `python -m demucs` used by the tests: mimics its CLI, tqdm output and file layout."""
import argparse
import subprocess
import sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("-n"); ap.add_argument("-d"); ap.add_argument("-o"); ap.add_argument("--two-stems")
ap.add_argument("--shifts"); ap.add_argument("--float32", action="store_true")
ap.add_argument("--segment"); ap.add_argument("-j")
ap.add_argument("track")
a = ap.parse_args()
for pct in (0, 30, 60, 100):
    sys.stderr.write(f"\r{pct:3d}%|{'#' * (pct // 10)}| {pct}/100\r"); sys.stderr.flush()
out = Path(a.o) / a.n / Path(a.track).stem
out.mkdir(parents=True, exist_ok=True)
for stem in ("vocals", "no_vocals"):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", a.track, str(out / f"{stem}.wav")], check=True)
