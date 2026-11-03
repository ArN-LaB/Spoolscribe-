"""Protect the independent CI oracle; its scan libraries stay outside the app."""
import importlib.util
import json
import unittest

from tests.support import ROOT
from spoolscribe import qr_transfer

spec = importlib.util.spec_from_file_location("ssqr1_ci_check", ROOT / ".github/scripts/check_frozen_ssqr1.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


class FrozenSsqr1OracleTests(unittest.TestCase):
    def test_normative_vectors_and_both_codecs(self):
        vectors = json.loads((ROOT / "tests/fixtures/qr/ssqr1_vectors.json").read_text(encoding="utf-8"))["vectors"]
        for entry in vectors.values():
            message = bytes.fromhex(entry["hex"])
            for codec in (0, 1):
                decoded, record = oracle.decode_transfer(qr_transfer.envelope(entry["protocol"], message, codec))
                self.assertEqual(decoded, message)
                self.assertEqual((record["tnf"], record["records"], record["identifier"]), (2, 1, ""))

    def test_oracle_refuses_bad_prefix_truncation_and_digest(self):
        entry = json.loads((ROOT / "tests/fixtures/qr/ssqr1_vectors.json").read_text(encoding="utf-8"))["vectors"]["catalogue-essential"]
        text = qr_transfer.envelope(1, bytes.fromhex(entry["hex"]), 0)
        damaged = bytearray(qr_transfer.b45decode(text[6:]))
        damaged[4] ^= 1
        for bad in (text.replace("SSQR1:", "SSQR2:", 1), text[:-1], "SSQR1:A", "SSQR1:" + "A" * 4296,
                    "SSQR1:" + qr_transfer.b45encode(damaged)):
            with self.subTest(bad=bad[:20]), self.assertRaises(ValueError):
                oracle.decode_transfer(bad)
