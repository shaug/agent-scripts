#!/usr/bin/env python3
"""Run the hunk-preview command."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["hunk-preview", *sys.argv[1:]]))
