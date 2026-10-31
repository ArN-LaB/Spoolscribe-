import os
from pathlib import Path
import runpy
import ssl
import unittest
from unittest.mock import Mock, patch

import certifi
from tests.support import ROOT

HOOK = ROOT / ".github/runtime_hooks/tls_certificates.py"


class FrozenTrustTests(unittest.TestCase):
    def run_hook(self, ca_count):
        context = Mock()
        context.cert_store_stats.return_value = {"x509_ca": ca_count}
        with patch("ssl.create_default_context", return_value=context) as create:
            runpy.run_path(str(HOOK))
        return create

    def test_missing_default_roots_select_bundled_ca(self):
        with patch.dict(os.environ, {}, clear=True):
            self.run_hook(0)
            self.assertEqual(os.environ["SSL_CERT_FILE"], certifi.where())

    def test_existing_system_roots_are_preserved(self):
        with patch.dict(os.environ, {}, clear=True):
            self.run_hook(100)
            self.assertNotIn("SSL_CERT_FILE", os.environ)

    def test_explicit_certificate_file_is_preserved(self):
        with patch.dict(os.environ, {"SSL_CERT_FILE": "explicit.pem"}, clear=True):
            create = self.run_hook(0)
            create.assert_not_called()
            self.assertEqual(os.environ["SSL_CERT_FILE"], "explicit.pem")

    def test_explicit_certificate_directory_is_preserved(self):
        with patch.dict(os.environ, {"SSL_CERT_DIR": "explicit-directory"}, clear=True):
            create = self.run_hook(0)
            create.assert_not_called()
            self.assertNotIn("SSL_CERT_FILE", os.environ)

    def test_fallback_loads_real_roots_without_disabling_verification(self):
        with patch.dict(os.environ, {}, clear=True):
            self.run_hook(0)
            context = ssl.create_default_context()
            self.assertTrue(Path(certifi.where()).is_file())
            self.assertGreater(context.cert_store_stats()["x509_ca"], 100)
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(context.check_hostname)
