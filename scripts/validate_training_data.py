"""Offline validation only; never loads credentials or creates a provider client."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from onelap.training_data import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
