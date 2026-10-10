"""Run from the project root: .venv/Scripts/python.exe scripts/smoke.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from onelap.smoke import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
