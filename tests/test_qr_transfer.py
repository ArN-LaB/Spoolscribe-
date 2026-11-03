"""SSQR1 transfer contract (SPOOLSCRIBE-QR-2026-001): exact NDEF, strict refusals, codec choice."""
import hashlib
import json
import random
import tempfile
import unittest
import zlib
from unittest.mock import patch

import tests.support  # noqa: F401  (network refused for the whole suite)
from tests.support import ROOT
from spoolscribe import core, opentag3d, qr_layout, qr_transfer as q

VECTORS = json.loads((ROOT / "tests/fixtures/qr/ssqr1_vectors.json").read_text(encoding="utf-8"))


def vector(name):
    entry = VECTORS["vectors"][name]
    return entry["protocol"], bytes.fromhex(entry["hex"])


def body(text):
    return q.b45decode(text[len(q.PREFIX):])


def text_of(raw_body):
    return q.PREFIX + q.b45encode(raw_body)


def independent_record(message):
    """Reading written from the NDEF specification, without the module under test."""
    flags, type_length = message[0], message[1]
    short = bool(flags & 0x10)
    length = message[2] if short else int.from_bytes(message[2:6], "big")
    start = 3 if short else 6
    return dict(mb=bool(flags & 0x80), me=bool(flags & 0x40), cf=bool(flags & 0x20), il=bool(flags & 0x08),
                tnf=flags & 7, mime=message[start:start + type_length], payload=message[start + type_length:], length=length)


class Base45Tests(unittest.TestCase):
    def test_rfc_9285_examples(self):
        for raw, text in ((b"AB", "BB8"), (b"Hello!!", "%69 VD92EX0"), (b"base-45", "UJCLQE7W581"), (b"ietf!", "QED8WEX0")):
            self.assertEqual(q.b45encode(raw), text)
            self.assertEqual(q.b45decode(text), raw)

    def test_every_byte_pair_round_trips(self):
        data = bytes(range(256)) + bytes(reversed(range(256)))
        for size in (0, 1, 2, 3, 255, 512):
            self.assertEqual(q.b45decode(q.b45encode(data[:size])), data[:size])

    def test_strict_decoding(self):
        for bad in ("A", "BB8B", "bb8", "BB8\n", "BB8\t", "BB8_", "GGW", "::"):
            with self.subTest(bad=bad), self.assertRaises(q.TransferError):
                q.b45decode(bad)
        self.assertEqual(q.b45decode("FGW"), b"\xff\xff")  # 65535 is the largest valid triplet
        self.assertEqual(q.b45decode("U5"), b"\xff")      # 255 is the largest valid doublet


class ExactMessageTests(unittest.TestCase):
    """QR-01: the transferred message is the export's NDEF, byte for byte."""

    def test_the_five_normative_vectors(self):
        for name, entry in VECTORS["vectors"].items():
            with self.subTest(vector=name):
                protocol, raw = vector(name)
                self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()), (entry["length"], entry["sha256"]))
                record = independent_record(raw)
                self.assertEqual((record["mb"], record["me"], record["cf"], record["il"], record["tnf"]), (True, True, False, False, 2))
                self.assertEqual(record["mime"], b"application/json" if protocol == q.OPENSPOOL else b"application/opentag3d")
                self.assertEqual(len(record["payload"]), record["length"])
                for codec in (q.RAW, q.ZLIB):
                    decoded = q.decode(q.envelope(protocol, raw, codec))
                    self.assertEqual((decoded.protocol, decoded.codec, decoded.ndef), (protocol, codec, raw))

    def test_the_vectors_are_rebuilt_by_the_existing_encoders(self):
        database = json.loads((ROOT / "tests/fixtures/catalogues/polymaker_db.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as orca, patch.object(core, "ORCA_DIR", orca):
            view = core.get_sku_view(database, "PA03006")
            payload = core.build_openspool(dict(database["_skus"]["PA03006"], sku="PA03006"), view.product_data, brand_meta=view.brand_meta)
            for profile, name in (("essential", "catalogue-essential"), ("full", "catalogue-full")):
                text = core.serialize_openspool(payload, profile=profile, tag_type="NTAG216", reserved_bytes=0)
                message = q.openspool_ndef(text.encode("utf-8"))
                self.assertEqual(message, vector(name)[1])
                self.assertEqual(len(message), core.nfc_size(text).ndef_bytes)
                self.assertEqual(independent_record(message)["payload"], text.encode("utf-8"))  # JSON bytes untouched
        fields = dict(material="PLA", manufacturer="Polymaker", color_name="Silk Lime", color_1="91C500FF", sku="PA03006",
                      diameter=1.75, density=1.24, print_temp=210, min_print_temp=190, max_print_temp=230, chamber_temp=0,
                      bed_temp=60, min_bed_temp=60, max_bed_temp=60, weight=1000)
        payload = opentag3d.encode(fields)
        self.assertEqual(opentag3d.ndef(payload), vector("opentag-real-explicit")[1])
        self.assertEqual(opentag3d.ndef(payload)[:3], bytes([0xD2, 0x15, 0xE0]))
        self.assertEqual((len(payload), len(opentag3d.ndef(payload))), (224, 248))

    def test_long_openspool_records_use_a_four_byte_length(self):
        _, raw = vector("catalogue-full")
        self.assertEqual(raw[:6], bytes([0xC2, 0x10, 0, 0, 0x02, 0xFC]))
        self.assertEqual(q.openspool_ndef(independent_record(raw)["payload"]), raw)

    def test_the_reference_text_from_another_zlib_is_accepted(self):
        reference = VECTORS["reference_text"]
        decoded = q.decode(reference["text"])
        self.assertEqual((decoded.protocol, decoded.codec, decoded.ndef), (q.OPENSPOOL, q.ZLIB, vector("catalogue-essential")[1]))

    def test_any_valid_zlib_stream_of_the_same_message_is_accepted(self):
        protocol, raw = vector("openspool-utf8")
        header = bytes([protocol, q.ZLIB]) + len(raw).to_bytes(2, "big") + hashlib.sha256(raw).digest()
        for level in (0, 1, 6, 9):
            self.assertEqual(q.decode(text_of(header + zlib.compress(raw, level))).ndef, raw)
        self.assertIn("Étiquette café 测试".encode("utf-8"), raw)


class RefusalTests(unittest.TestCase):
    """QR-03: every malformed or inconsistent transfer is refused explicitly."""

    def setUp(self):
        self.protocol, self.raw = vector("catalogue-essential")
        self.header = bytes([self.protocol, q.ZLIB]) + len(self.raw).to_bytes(2, "big") + hashlib.sha256(self.raw).digest()
        self.good = q.envelope(self.protocol, self.raw, q.ZLIB)

    def refused(self, text, message=None):
        with self.assertRaises(q.TransferError) as caught:
            q.decode(text)
        if message:
            self.assertIn(message, str(caught.exception))

    def test_prefix_version_and_alphabet(self):
        tail = self.good[len(q.PREFIX):]
        for text in (tail, "SSQR2:" + tail, "ssqr1:" + tail, " " + self.good, self.good + "\n", self.good.lower(), "SSQR1:"):
            with self.subTest(text=text[:12]):
                self.refused(text)
        self.refused(None)

    def test_header_protocol_codec_and_lengths(self):
        data = zlib.compress(self.raw, 9)
        digest = hashlib.sha256(self.raw).digest()
        cases = {
            "short": bytes(36),
            "protocol": bytes([3, 1]) + self.header[2:] + data,
            "codec": bytes([1, 2]) + self.header[2:] + data,
            "zero length": bytes([1, 1, 0, 0]) + digest + data,
            "too long": bytes([1, 1]) + (4097).to_bytes(2, "big") + digest + data,
            "announced length": bytes([1, 1]) + (len(self.raw) - 1).to_bytes(2, "big") + digest + data,
            "sha": self.header[:4] + bytes(32) + data,
            "raw length": bytes([1, 0]) + self.header[2:] + self.raw[:-1],
            "raw trailing": bytes([1, 0]) + self.header[2:] + self.raw + b"\0",
        }
        for name, raw_body in cases.items():
            with self.subTest(case=name):
                self.refused(text_of(raw_body))

    def test_zlib_truncated_concatenated_trailing_dictionary_and_bomb(self):
        data = zlib.compress(self.raw, 9)
        compressor = zlib.compressobj(9, zdict=b'"protocol":"openspool"')
        with_dictionary = compressor.compress(self.raw) + compressor.flush()
        bomb = zlib.compress(b"{" + b" " * 1_000_000, 9)
        cases = {"truncated": data[:-5], "concatenated": data + data, "trailing": data + b"\0", "garbage": b"\x78\x9c\xff\xff",
                 "dictionary": with_dictionary, "bomb": bomb}
        for name, stream in cases.items():
            with self.subTest(case=name):
                self.refused(text_of(self.header + stream))

    def test_bomb_output_is_bounded_by_the_announced_length(self):
        produced = []
        real = zlib.decompressobj

        class Spy:
            def __init__(self):
                self.inner = real()

            def decompress(self, data, max_length=0):
                out = self.inner.decompress(data, max_length)
                produced.append((max_length, len(out)))
                return out

            def __getattr__(self, name):
                return getattr(self.inner, name)
        with patch("spoolscribe.qr_transfer.zlib.decompressobj", Spy):
            self.refused(text_of(self.header + zlib.compress(b"{" + b" " * 1_000_000, 9)))
        self.assertEqual(produced, [(len(self.raw) + 1, len(self.raw) + 1)])

    def test_malformed_ndef_messages(self):
        payload = independent_record(self.raw)["payload"]
        mime = b"application/json"
        second = q.mime_record(mime, payload)
        cases = {
            "two records": bytes([0x92]) + self.raw[1:] + bytes([0x52]) + second[1:],
            "chunked": bytes([0xF2]) + self.raw[1:],
            "identifier": bytes([0xDA, len(mime), len(payload), 1]) + mime + b"x" + payload,
            "well-known type": bytes([0xD1]) + self.raw[1:],
            "not first": bytes([0x52]) + self.raw[1:],
            "not last": bytes([0x92]) + self.raw[1:],
            "trailing": self.raw + b"\0",
            "truncated": self.raw[:-1],
            "wrong mime": q.mime_record(b"application/opentag3d", payload),
            "invalid utf-8": q.mime_record(mime, b'{"protocol":"openspool","x":"\xff"}'),
            "not json": q.mime_record(mime, b"protocol=openspool"),
            "invalid openspool": q.mime_record(mime, json.dumps({"protocol": "openspool", "version": "2.0"}).encode()),
            "empty type": bytes([0xD2, 0, 1, 0x7B]),
        }
        for name, message in cases.items():
            with self.subTest(case=name):
                with self.assertRaises(q.TransferError):
                    q.validate_ndef(q.OPENSPOOL, message)
                raw_body = bytes([q.OPENSPOOL, q.RAW]) + len(message).to_bytes(2, "big") + hashlib.sha256(message).digest() + message
                self.refused(text_of(raw_body))

    def test_opentag_payload_is_checked(self):
        protocol, raw = vector("opentag-real-explicit")
        payload = independent_record(raw)["payload"]
        for name, message in {"short": opentag3d.ndef(payload[:-1]), "version": opentag3d.ndef(b"\x07\xd5" + payload[2:]),
                              "json mime": q.mime_record(b"application/json", payload)}.items():
            with self.subTest(case=name), self.assertRaises(q.TransferError):
                q.validate_ndef(protocol, message)
        with self.assertRaises(q.TransferError):
            q.validate_ndef(q.OPENSPOOL, raw)  # Protocol and MIME must agree.

    def test_text_and_qr_capacity_bounds(self):
        self.refused(q.PREFIX + "0" * (q.MAX_TEXT_CHARS - len(q.PREFIX) + 1), "trop long")
        rng = random.Random(9285)
        noise = "".join(chr(rng.randrange(0x4E00, 0x9FFF)) for _ in range(1200))  # 3 600 UTF-8 bytes, little redundancy
        payload = json.loads(independent_record(self.raw)["payload"])
        message = q.openspool_ndef(json.dumps(dict(payload, product=noise), separators=(",", ":")).encode())
        with self.assertRaises(q.TransferError):
            q.envelope(q.OPENSPOOL, message, q.RAW)  # Base45 text above 4 296 characters
        for error in ("M", "Q"):
            with self.subTest(error=error), self.assertRaises(q.TransferError):
                qr_layout.make_symbol(q.OPENSPOOL, message, error)
        with self.assertRaises(q.TransferError):
            q.validate_ndef(q.OPENSPOOL, b"")
        with self.assertRaises(q.TransferError):
            q.envelope(q.OPENSPOOL, self.raw, 2)


class CodecChoiceTests(unittest.TestCase):
    """QR-04: smallest QR version of the two codecs, raw on a tie; nothing removed."""

    def versions(self, protocol, raw, error):
        import segno
        out = {}
        for codec in (q.RAW, q.ZLIB):
            try:
                out[codec] = segno.make(q.envelope(protocol, raw, codec), error=error.lower(), mode="alphanumeric",
                                        micro=False, boost_error=False).version
            except segno.DataOverflowError:
                out[codec] = 99
        return out

    def check(self, protocol, raw, error):
        symbol = qr_layout.make_symbol(protocol, raw, error)
        versions = self.versions(protocol, raw, error)
        expected_codec = q.RAW if versions[q.RAW] <= versions[q.ZLIB] else q.ZLIB
        self.assertEqual((symbol.codec, symbol.version), (expected_codec, versions[expected_codec]))
        self.assertEqual(q.decode(symbol.text).ndef, raw)
        self.assertEqual(symbol.sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual(symbol.size, 17 + 4 * symbol.version)
        return symbol

    def test_vectors_in_m_and_q(self):
        expected = {"catalogue-essential": (11, 13), "catalogue-full": (15, 19), "opentag-real-explicit": (8, 10),
                    "openspool-utf8": (12, 15), "opentag-utf8": (8, 10)}
        for name, (m, qv) in expected.items():
            protocol, raw = vector(name)
            with self.subTest(vector=name):
                self.assertEqual(self.check(protocol, raw, "M").version, m)
                self.assertEqual(self.check(protocol, raw, "Q").version, qv)

    def test_incompressible_message_stays_raw_and_short_one_is_minimal(self):
        rng = random.Random(45)
        base = json.loads(independent_record(vector("catalogue-essential")[1])["payload"])
        for size in (0, 40, 400, 1200):
            noise = "".join(rng.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(size))
            raw = q.openspool_ndef(json.dumps(dict(base, product=noise), separators=(",", ":"), ensure_ascii=False).encode())
            with self.subTest(size=size):
                symbol = self.check(q.OPENSPOOL, raw, "M")
                self.assertIn(noise, independent_record(q.decode(symbol.text).ndef)["payload"].decode("utf-8"))

    def test_a_tie_prefers_raw(self):
        protocol, raw = vector("catalogue-essential")
        texts = {codec: q.envelope(protocol, raw, codec) for codec in (q.RAW, q.ZLIB)}

        class Code:
            def __init__(self, text):
                self.text, self.version = text, 11
                import segno
                self._real = segno.make(text, error="m", mode="alphanumeric", micro=False, boost_error=False)

            def matrix_iter(self, **kwargs):
                return self._real.matrix_iter(**kwargs)
        with patch("spoolscribe.qr_layout._segno", lambda text, error: Code(text)):
            symbol = qr_layout.make_symbol(protocol, raw, "M")
        self.assertEqual((symbol.codec, symbol.text), (q.RAW, texts[q.RAW]))

    def test_no_automatic_error_boost_micro_or_eci(self):
        protocol, raw = vector("opentag-real-explicit")
        import segno
        calls = []
        real = segno.make

        def spy(*args, **kwargs):
            calls.append(kwargs)
            return real(*args, **kwargs)
        with patch("spoolscribe.qr_layout.segno.make", spy):
            qr_layout.make_symbol(protocol, raw, "M")
        self.assertTrue(calls)
        for kwargs in calls:
            self.assertEqual((kwargs["boost_error"], kwargs["micro"], kwargs["mode"], kwargs.get("eci", False), kwargs["error"]),
                             (False, False, "alphanumeric", False, "m"))
        with self.assertRaises(q.TransferError):
            qr_layout.make_symbol(protocol, raw, "L")


if __name__ == "__main__":
    unittest.main()
