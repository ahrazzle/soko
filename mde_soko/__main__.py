"""Module execution hook for `python3 -m mde_soko`."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
