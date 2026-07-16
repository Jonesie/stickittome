"""``python -m stickitto`` entry point."""

from __future__ import annotations

import sys

from .app import run


def main() -> int:
    try:
        run()
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())