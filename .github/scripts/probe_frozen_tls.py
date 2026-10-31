"""Runs inside the frozen app, without network or user database access."""
import json
import os
from pathlib import Path
import socket
import ssl
import sys

import certifi


def _offline(event, args):
    if event in ("socket.connect", "socket.getaddrinfo"):
        raise AssertionError("The frozen TLS smoke test must stay offline")


sys.addaudithook(_offline)
assert getattr(sys, "frozen", False)
bundle = Path(certifi.where())
assert bundle.is_file()
context = ssl.create_default_context()
bundled = ssl.create_default_context(cafile=str(bundle))
assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
assert context.cert_store_stats()["x509_ca"] > 0
assert bundled.verify_mode == ssl.CERT_REQUIRED and bundled.check_hostname
assert bundled.cert_store_stats()["x509_ca"] > 100
result = {"frozen": True, "certifi": certifi.__version__,
          "default_roots": context.cert_store_stats()["x509_ca"],
          "bundled_roots": bundled.cert_store_stats()["x509_ca"],
          "verify_mode": int(context.verify_mode), "check_hostname": context.check_hostname}
Path(os.environ["SPOOLSCRIBE_TLS_REPORT"]).write_text(json.dumps(result))
