"""Run the desktop interface with python -m spoolscribe."""
# Resolve an interrupted restoration before any model/GUI import (stdlib only).
from . import recovery as _recovery
_recovery.bootstrap()

from .app_gui import main

raise SystemExit(main())
