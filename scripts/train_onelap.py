"""Default is an offline token preview, not a training request."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from onelap.training import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
