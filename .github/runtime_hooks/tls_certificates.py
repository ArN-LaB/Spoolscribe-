"""Supply packaged roots only when Python cannot find any default trust roots.

Executed by PyInstaller before the GUI or a standalone update worker starts.
Explicit trust configuration and existing system roots remain authoritative.
"""
import os
import ssl

import certifi


def _configure_tls():
    if os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR"):
        return
    if ssl.create_default_context().cert_store_stats()["x509_ca"] == 0:
        os.environ["SSL_CERT_FILE"] = certifi.where()


_configure_tls()
