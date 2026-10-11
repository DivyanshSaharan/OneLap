"""Preview or explicitly run the bounded synthetic OneLap evaluation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from onelap.experiments import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
