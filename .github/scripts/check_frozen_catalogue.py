"""Execute the catalogue smoke check inside each platform's built executable."""
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
    report = Path(directory) / "catalogue.json"
    env = dict(os.environ, SPOOLSCRIBE_RUN_SCRIPT_ALLOW=str(root / ".github/scripts"), SPOOLSCRIBE_CATALOGUE_REPORT=str(report), SPOOLSCRIBE_DATA_HOME=directory,
               SPOOLSCRIBE_CONFIG_PATH=str(Path(directory) / "config.json"))
    subprocess.run([str(root / "dist" / relative), "--run-script", str(root / ".github/scripts/probe_frozen_catalogue.py")],
                   env=env, check=True, timeout=120)
    result = json.loads(report.read_text(encoding="utf-8"))
    assert result["main_window_rendered"] and result["offline"] and result["empty_first_install"] and result["fixture_references"] == 1
    assert result["interface_languages"] == ["en","fr","es","zh_CN"]
    print("FROZEN_CATALOGUE_OK", json.dumps(result))
