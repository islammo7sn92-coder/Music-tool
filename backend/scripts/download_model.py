"""Download the Demucs weights into ./models so the first request is not slow.

    python backend/scripts/download_model.py            # uses DEMUCS_MODEL (default htdemucs)
    python backend/scripts/download_model.py htdemucs_ft
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import config  # noqa: E402

os.environ["TORCH_HOME"] = str(config.MODELS_DIR)

from demucs.pretrained import get_model  # noqa: E402

name = sys.argv[1] if len(sys.argv) > 1 else config.DEMUCS_MODEL
print(f"Downloading '{name}' into {config.MODELS_DIR} ...")
get_model(name)
print("Done.")
