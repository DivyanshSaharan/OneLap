"""Offline command: .venv/Scripts/python.exe scripts/evaluate.py validate."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from onelap.evaluation import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
