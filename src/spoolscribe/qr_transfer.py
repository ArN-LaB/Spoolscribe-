"""SSQR1: one QR text carrying the complete NDEF message of a tag, without a server.

Text: ``SSQR1:`` + Base45 (RFC 9285) of the body below.

====  ========================================================================
0     protocol: 01 OpenSpool 1.0, 02 OpenTag3D 2.004
1     codec: 00 raw NDEF, 01 zlib (RFC 1950, DEFLATE, no preset dictionary)
2-3   original NDEF length, uint16 big-endian
4-35  SHA-256 of the original NDEF (binary digest)
36-   raw NDEF or one complete zlib stream
====  ========================================================================

SHA-256 detects accidental changes; it is not an authenticity signature. The
NDEF is the whole message (one MIME record): no Type 2 TLV, terminator,
capability container, UID or password. Nothing found in a decoded payload is
opened, downloaded or executed.
"""
from dataclasses import dataclass
import hashlib
import json
import zlib

from . import opentag3d

PREFIX = "SSQR1:"
OPENSPOOL, OPENTAG3D = 1, 2
RAW, ZLIB = 0, 1
PROTOCOLS = {OPENSPOOL: "OpenSpool 1.0", OPENTAG3D: "OpenTag3D 2.004"}
MIME = {OPENSPOOL: b"application/json", OPENTAG3D: opentag3d.MIME}
HEADER_BYTES = 36
MAX_NDEF_BYTES = 4096
MAX_TEXT_CHARS = 4296  # Largest alphanumeric QR (V40-L); the real limit depends on the error level.
ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:"
_VALUES = {c: i for i, c in enumerate(ALPHABET)}


class TransferError(ValueError):
    """The text or message is refused; nothing partial is returned."""


class TextTooLong(TransferError):
    """One candidate text exceeds the transfer bound; another codec may still fit."""


def b45encode(data: bytes) -> str:
    """RFC 9285: two bytes become three characters, a final byte two."""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("Octets attendus.")
    out = []
    for i in range(0, len(data) - 1, 2):
        n = data[i] * 256 + data[i + 1]
        out += [ALPHABET[n % 45], ALPHABET[n // 45 % 45], ALPHABET[n // 2025]]
    if len(data) % 2:
        n = data[-1]
        out += [ALPHABET[n % 45], ALPHABET[n // 45]]
    return "".join(out)


def b45decode(text: str) -> bytes:
    """Strict: exact alphabet (space included), no cleaning, values in range."""
    if not isinstance(text, str):
        raise TransferError("Texte Base45 attendu.")
    if len(text) % 3 == 1:
        raise TransferError("Base45 : longueur invalide.")
    try:
        values = [_VALUES[c] for c in text]
    except KeyError as exc:
        raise TransferError("Base45 : caractère hors alphabet.") from exc
    out = bytearray()
    for i in range(0, len(values), 3):
        group = values[i:i + 3]
        if len(group) == 3:
            n = group[0] + group[1] * 45 + group[2] * 2025
            if n > 0xFFFF:
                raise TransferError("Base45 : triplet hors plage.")
            out += n.to_bytes(2, "big")
        else:
            n = group[0] + group[1] * 45
            if n > 0xFF:
                raise TransferError("Base45 : doublet hors plage.")
            out.append(n)
    return bytes(out)


def mime_record(mime: bytes, payload: bytes) -> bytes:
    """One complete NDEF message: MIME record, TNF 2, MB/ME set, ID absent."""
    length = len(payload)
    header = bytes([0xD2, len(mime), length]) if length < 256 else bytes([0xC2, len(mime)]) + length.to_bytes(4, "big")
    return header + mime + payload


def openspool_ndef(json_bytes: bytes) -> bytes:
    """Wrap the exact UTF-8 JSON of the NFC export; the bytes are not re-serialised."""
    return mime_record(MIME[OPENSPOOL], bytes(json_bytes))


def parse_record(message: bytes):
    """(mime, payload) of a message made of exactly one MIME record; strict."""
    if not isinstance(message, (bytes, bytearray)) or len(message) < 3:
        raise TransferError("NDEF : message trop court.")
    flags, type_length = message[0], message[1]
    if flags & 0x07 != 0x02:
        raise TransferError("NDEF : enregistrement MIME (TNF 2) attendu.")
    if not flags & 0x80 or not flags & 0x40:
        raise TransferError("NDEF : un seul enregistrement attendu.")
    if flags & 0x20:
        raise TransferError("NDEF : enregistrement fragmenté refusé.")
    if flags & 0x08:
        raise TransferError("NDEF : identifiant non autorisé.")
    if flags & 0x10:
        payload_length, offset = message[2], 3
    else:
        if len(message) < 6:
            raise TransferError("NDEF : en-tête tronqué.")
        payload_length, offset = int.from_bytes(message[2:6], "big"), 6
    if not type_length:
        raise TransferError("NDEF : type MIME absent.")
    mime = bytes(message[offset:offset + type_length])
    payload = bytes(message[offset + type_length:])
    if len(mime) != type_length or len(payload) != payload_length:
        raise TransferError("NDEF : longueur incohérente ou données finales.")
    return mime, payload


def validate_ndef(protocol: int, message: bytes) -> None:
    """The message a reader of this protocol expects, or TransferError."""
    if protocol not in PROTOCOLS:
        raise TransferError("Protocole inconnu.")
    if not 1 <= len(message) <= MAX_NDEF_BYTES:
        raise TransferError(f"NDEF : 1 à {MAX_NDEF_BYTES} octets attendus.")
    mime, payload = parse_record(message)
    if mime != MIME[protocol]:
        raise TransferError("NDEF : type MIME incompatible avec le protocole.")
    if protocol == OPENTAG3D:
        try:
            opentag3d.decode(payload)
        except (ValueError, UnicodeDecodeError) as exc:
            raise TransferError("OpenTag3D : payload 2.004 de 224 octets attendu.") from exc
        return
    from . import core
    try:
        document = json.loads(payload.decode("utf-8"))
        core.validate_openspool(document)
    except (UnicodeDecodeError, ValueError) as exc:
        raise TransferError("OpenSpool : JSON UTF-8 valide attendu.") from exc


def envelope(protocol: int, message: bytes, codec: int) -> str:
    """Transfer text for one codec; the message is validated first."""
    validate_ndef(protocol, message)
    if codec == RAW:
        data = bytes(message)
    elif codec == ZLIB:
        data = zlib.compress(bytes(message), 9)
    else:
        raise TransferError("Codec inconnu.")
    body = bytes([protocol, codec]) + len(message).to_bytes(2, "big") + hashlib.sha256(message).digest() + data
    text = PREFIX + b45encode(body)
    if len(text) > MAX_TEXT_CHARS:
        raise TextTooLong("Texte de transfert trop long pour un QR Code.")
    return text


@dataclass(frozen=True)
class Transfer:
    protocol: int
    codec: int
    ndef: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.ndef).hexdigest()


def decode(text: str) -> Transfer:
    """Bounded, strict reading of a transfer text; returns the exact NDEF."""
    if not isinstance(text, str):
        raise TransferError("Texte de transfert attendu.")
    if len(text) > MAX_TEXT_CHARS:
        raise TransferError("Texte de transfert trop long.")
    if not text.startswith(PREFIX):
        raise TransferError("Préfixe SSQR1: attendu.")
    body = b45decode(text[len(PREFIX):])
    if len(body) <= HEADER_BYTES:
        raise TransferError("En-tête de transfert incomplet.")
    protocol, codec, length = body[0], body[1], int.from_bytes(body[2:4], "big")
    if protocol not in PROTOCOLS:
        raise TransferError("Protocole inconnu.")
    if codec not in (RAW, ZLIB):
        raise TransferError("Codec inconnu.")
    if not 1 <= length <= MAX_NDEF_BYTES:
        raise TransferError("Longueur NDEF annoncée hors bornes.")
    digest, data = body[4:HEADER_BYTES], body[HEADER_BYTES:]
    if codec == RAW:
        message = data
    else:
        stream = zlib.decompressobj()
        try:
            # At most the announced length + 1 byte is ever produced.
            message = stream.decompress(data, length + 1)
        except zlib.error as exc:
            raise TransferError("Flux zlib invalide.") from exc
        if not stream.eof or stream.unused_data or stream.unconsumed_tail:
            raise TransferError("Flux zlib tronqué, trop long ou suivi de données.")
    if len(message) != length:
        raise TransferError("Longueur NDEF incohérente.")
    if hashlib.sha256(message).digest() != digest:
        raise TransferError("Empreinte SHA-256 incorrecte.")
    validate_ndef(protocol, message)
    return Transfer(protocol, codec, bytes(message))
