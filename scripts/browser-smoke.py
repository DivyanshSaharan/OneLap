"""Default: read-only preflight. See docs/browser-smoke.md before any live run."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from onelap.browser_smoke import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
