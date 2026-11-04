"""Execute the colour-measurement smoke check inside each platform's built executable."""
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
    report = Path(directory) / "measurements.json"
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", SPOOLSCRIBE_RUN_SCRIPT_ALLOW=str(root / ".github/scripts"),
               SPOOLSCRIBE_MEASUREMENTS_REPORT=str(report), SPOOLSCRIBE_DATA_HOME=directory,
               SPOOLSCRIBE_CONFIG_PATH=str(Path(directory) / "config.json"))
    subprocess.run([str(root / "dist" / relative), "--run-script", str(root / ".github/scripts/probe_frozen_measurements.py")],
                   env=env, check=True, timeout=180)
    result = json.loads(report.read_text(encoding="utf-8"))
    assert result["offline"] and result["measurements"] == 1 and result["catalogue_untouched"] and result["csv_valid"] == 1
    print("FROZEN_MEASUREMENTS_OK", json.dumps(result))
