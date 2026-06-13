#!/usr/bin/env python3
"""Generate API documentation using pdoc.

Usage:
    python scripts/generate_api_docs.py          # HTML output → docs/api/
    python scripts/generate_api_docs.py --serve   # Live server at localhost:8080
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "docs" / "api"


def main() -> None:
    if "--serve" in sys.argv:
        subprocess.run(
            [sys.executable, "-m", "pdoc", "prism", "--host", "localhost", "--port", "8080"],
            cwd=ROOT / "src",
            check=True,
        )
    else:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [sys.executable, "-m", "pdoc", "prism", "--output-directory", str(OUTPUT_DIR)],
            cwd=ROOT / "src",
            check=True,
        )
        print(f"API docs generated at {OUTPUT_DIR}")
        print(f"  Open: file://{OUTPUT_DIR / 'prism.html'}")


if __name__ == "__main__":
    main()
