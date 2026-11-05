# QR Code transfer format (SSQR1)

[Documentation](README.md) · [Data format](DATA_FORMAT.md) · [Writing tags](wiki/Writing-RFID-Tags.md)

**Introduced in v0.6.0; retained unchanged in v0.8.0 Pre-release: validated digital SSQR1 contract.** One standard QR Code
carries the **whole NDEF message** of an NFC export, with no server, link or
file transfer. SpoolScribe Desktop shows and saves it (PNG, SVG). Existing system-printing
controls remain outside this digital validation; printing and Bluetooth
are deferred. A
future **SpoolScribe Companion** app is meant to scan it, then write and read
back the tag; that app does not exist yet. An ordinary QR reader only shows the
transfer text: it does not program a chip.

## Content

`SSQR1:` followed by the [Base45 (RFC 9285)](https://datatracker.ietf.org/doc/html/rfc9285)
encoding of this body:

| Bytes | Field |
| --- | --- |
| 0 | Protocol: `01` OpenSpool 1.0, `02` OpenTag3D 2.004 |
| 1 | Codec: `00` raw NDEF, `01` zlib (RFC 1950, DEFLATE, no preset dictionary) |
| 2–3 | Length of the original NDEF message, unsigned 16-bit big-endian |
| 4–35 | SHA-256 of the original NDEF message (binary digest) |
| 36… | Raw NDEF message, or one complete zlib stream of it |

The NDEF message is exactly the one the NFC export would write:

- **OpenSpool 1.0**: one MIME record `application/json`, TNF 2, MB/ME set, no
  ID. Header `D2 10 LL` for a payload below 256 bytes, otherwise `C2 10` and a
  4-byte big-endian length. The payload is the exact UTF-8 JSON of the selected
  NFC profile (essential or full), not re-serialised.
- **OpenTag3D 2.004**: `opentag3d.ndef(payload)`, MIME `application/opentag3d`,
  224-byte payload, 248-byte message starting with `D2 15 E0`. The NFC Tools
  profile files are writer containers and are never put in the QR.

The QR never contains a Type 2 TLV, terminator, capability container, UID or
password. A writer still checks the tag capacity: the QR bounds below do not
replace the NTAG215/NTAG216 checks of the export.

SHA-256 detects accidental changes. **It is not an authenticity signature**:
anyone can build a valid SSQR1 text. Nothing found in a decoded message (URL,
file name, command) is opened, downloaded or executed.

## Emission

- zlib level 9 is tried next to the raw message; the smaller **QR version**
  wins at the chosen error level, the raw message on a tie. Compression can make
  incompressible data larger, so both codecs stay possible. Each candidate is
  evaluated on its own: a raw text above 4 296 characters does not prevent a
  compressed one that fits. The NDEF message is validated first, and its errors
  are never treated as a size problem.
- Standard QR only: one alphanumeric segment, no ECI, Micro QR or Structured
  Append. Error correction **M** by default, **Q** on explicit choice; no
  automatic boost and no downgrade to L to make a label fit.
- Generation uses [Segno 1.6.6](https://github.com/heuer/segno/) (BSD 3-Clause,
  [notice](../data/licenses/Segno-LICENSE.txt)). Base45 is implemented locally
  from the RFC.

## Decoding rules

A decoder refuses, with nothing partial returned:

- another prefix (`SSQR2:`, lower case…), a text above 4 296 characters, any
  character outside the Base45 alphabet; no trimming, case change or space
  normalisation (the space belongs to the alphabet);
- a final single character, a triplet above 65 535 or a pair above 255;
- an unknown protocol or codec, an announced length outside 1–4 096 bytes;
- a zlib stream that is truncated, followed by data, concatenated, needs a
  dictionary or produces more than the announced length + 1 byte (bounded
  output, no unlimited decompression);
- a length or SHA-256 mismatch;
- an NDEF message that is not exactly one MIME record of the protocol's type:
  chunked or several records, ID present, other TNF, trailing data, invalid
  UTF-8 or JSON, an OpenSpool document refused by the export validation, an
  OpenTag3D payload that is not a 224-byte 2.004 payload.

Any valid zlib stream is accepted: the normative identity is the decompressed
NDEF, not the compressed bytes. Reference vectors (five NDEF messages and one
transfer text) are in [`tests/fixtures/qr/ssqr1_vectors.json`](../tests/fixtures/qr/ssqr1_vectors.json).

## Printed size (existing geometry; physical validation deferred)

A QR of version *v* has `17 + 4v` modules per side, plus four white modules on
each side. Printing uses **whole printer dots per module**, from the paper,
margins and resolution accepted by the driver, never from the screen zoom:

| Rule | Result |
| --- | --- |
| At least 4 dots per module | Ready for a test print |
| Exactly 3 dots per module | Only with **Small format — reading test required** |
| Fewer than 3 dots, or no printable area | Printing refused; viewing and saving stay available |

The printer brand is not the sizing rule: printable width, margins, QR version
and resolution decide whether a specific symbol fits. Paper sizes are not a
universal QR label standard. See [paper and printer choices](PRINTING_GUIDE.md)
for documented examples and the geometry calculation.

**Since v0.8.0:** new transfers start with no
paper selected. Error correction M/Q is available outside technical details;
message, symbol, NFC tag and optional paper geometry are shown separately.
An old paper preference retains its dimensions but does not force a paper
workflow on a new transfer. No NDEF field, SSQR1 envelope or QR decoding rule changes.

These are geometric limits, not a reading guarantee. Paper, print head,
contrast and the scanner decide; no physical print/scan is claimed.

## Future QR link

A later HTTPS link could carry this text in a URL fragment, with its own size
overhead. No domain or universal QR link is configured, and the QR does not
depend on one. The separate [Companion availability page](COMPANION.md) is an
information link in the desktop UI; it is never encoded into SSQR1.
