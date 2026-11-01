"""PyInstaller entry point; also launches an uninstalled source checkout."""
from pathlib import Path
import sys

if not getattr(sys, "frozen", False):
    root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(root / "src"), str(root)]

from spoolscribe.app_gui import main

if __name__ == "__main__":
    raise SystemExit(main())
