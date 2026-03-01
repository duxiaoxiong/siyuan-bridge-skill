#!/usr/bin/env python3
"""Siyuan CLI entrypoint."""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(SCRIPT_DIR)
if SKILL_ROOT not in sys.path:
    sys.path.insert(0, SKILL_ROOT)

from scripts.cli.siyuan_cli import main


if __name__ == "__main__":
    raise SystemExit(main())
