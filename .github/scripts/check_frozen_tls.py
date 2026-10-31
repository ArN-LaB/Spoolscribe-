"""Launch the packaged application's offline TLS probe on each native CI OS."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[2]
relative = ("SpoolScribe.exe" if sys.platform == "win32" else
            "SpoolScribe.app/Contents/MacOS/SpoolScribe" if sys.platform == "darwin" else "SpoolScribe")
with tempfile.TemporaryDirectory() as directory:
    report = Path(directory) / "tls.json"
    env = dict(os.environ, SPOOLSCRIBE_TLS_REPORT=str(report),
               SPOOLSCRIBE_DATA_HOME=directory, SPOOLSCRIBE_CONFIG_PATH=str(Path(directory) / "config.json"))
    subprocess.run([str(root / "dist" / relative), "--run-script",
                    str(root / ".github/scripts/probe_frozen_tls.py")], env=env, check=True, timeout=120)
    result = json.loads(report.read_text())
    assert result["frozen"] and result["default_roots"] > 0 and result["bundled_roots"] > 100
    assert result["verify_mode"] == 2 and result["check_hostname"]
    print("FROZEN_TLS_OK", json.dumps(result))
