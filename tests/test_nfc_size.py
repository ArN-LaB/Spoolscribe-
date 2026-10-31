import unittest

import core


def encode_mime(text):
    """Independent test encoder: one application/json record, no ID."""
    payload = text.encode("utf-8")
    short = len(payload) < 256
    record = bytes([0xD2 if short else 0xC2, 16])
    record += bytes([len(payload)]) if short else len(payload).to_bytes(4, "big")
    record += b"application/json" + payload
    tlv = b"\x03" + (bytes([len(record)]) if len(record) < 255 else b"\xff" + len(record).to_bytes(2, "big"))
    return record, tlv + record + b"\xfe"


class NfcSizeTests(unittest.TestCase):
    def test_header_boundaries_and_utf8(self):
        for text in ("", "a" * 235, "a" * 236, "a" * 254, "a" * 255, "a" * 256, "é" * 130, "🧵" * 220):
            with self.subTest(length=len(text)):
                record, tlv = encode_mime(text)
                size = core.nfc_size(text)
                self.assertEqual(size.characters, len(text))
                self.assertEqual(size.utf8_bytes, len(text.encode("utf-8")))
                self.assertEqual(size.ndef_bytes, len(record))
                self.assertEqual(size.type2_bytes, len(tlv))

    def test_capacity_boundary(self):
        self.assertTrue(core.nfc_size("a" * 845).fits)   # 845 + 22 + 5 = 872
        self.assertFalse(core.nfc_size("a" * 846).fits)
