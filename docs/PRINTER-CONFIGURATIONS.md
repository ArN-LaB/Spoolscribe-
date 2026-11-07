# Choose a printer and reader setup

[Documentation](README.md) · [OpenTag3D](OPENTAG3D.md) · [Historical validation](validation/v0.8.0.md)

**The printer, reader and software must work together.** A USB port or NFC chip
alone is insufficient. The list documents specific setups, not every available
model. These choices are available in the
[current stable release](https://github.com/ArN-LaB/Spoolscribe-/releases/latest).
Software stability does not certify every hardware combination; see the
[release policy](RELEASE_POLICY.md).

## Evidence and feedback

Automated tests cover software and exported data. The entries below come from
the cited documentation, not a physical test of each printer. Exhaustive testing
would require every printer, reader, firmware and plugin version. No physical
NFC writing or printer read-back is claimed for these additions.

Both successful tests and reproducible problems are useful. Open a
[compatibility issue](https://github.com/ArN-LaB/Spoolscribe-/issues/new?template=printer_compatibility.yml)
with the exact model, reader/connection, software versions, tag, exported format
and observed result. Findings apply to that setup, not automatically an entire
family. Do not include personal data or network credentials.

## Build the setup in three steps

Choose the **printer model** first, without looking for a duplicate model named
after an external reader. Compose the setup using the built-in/USB/network
reader, original/modified/additional software and specific integration buttons.
These choices complement each other: a network reader does not prove SpoolSense
is installed. Even a sole remaining option needs explicit confirmation.

Then choose the compatible label format and the purchased tag. The summary stays
visible below the choices while scrolling. Current OpenTag3D GUI exports default
to raw NDEF; legacy phone/desktop writer containers remain in CLI/API and imported
settings. Technical lists remain internal for preference/API compatibility.

**Requirements and details** groups versions, drivers, CAN/MQTT/UART connections,
documentary sources and NFC settings. An example configuration is **U1 → built-in
reader → modified software → paxx12 / OpenRFID → OpenTag3D → NTAG216**. The summary
distinguishes data sent to the printer, external inventory only and standalone
readers. Experimental/unverified setups are labelled. Documentation opens only
on a click; no personal service is contacted to detect your equipment.

## Connections are not interchangeable

| Setup | Requirements | What it does not establish |
| --- | --- | --- |
| Built-in reader | Firmware decoder supporting the tag format | Community firmware alone does not guarantee every detection mode/format |
| USB reader on printer or host | Compatible reader, driver and integration software for that system | An ACR122U recognised by macOS is not necessarily recognised by the printer |
| Network scanner | Reader, network and compatible API/automation | USB power is not a printer data connection |
| Manufacturer accessory | Explicitly supported model, bus and firmware | Prusa's CAN OpenPrintTag accessory is not a universal USB reader |
| USB reader on the Mac | Writing application and reader recognised by macOS | Writing a tag does not give the printer firmware a decoder |

## Documented setups

Documentation reviewed **1 November 2026**. These additions have **no claimed
SpoolScribe physical acceptance test**.

| Printer | Selected integration | Printer firmware | Offered SpoolScribe outputs | Result and limits |
| --- | --- | --- | --- | --- |
| U1 | Built-in, Snapmaker mode | paxx12 | OpenSpool | Identification through the built-in reader |
| U1 | Built-in, OpenRFID or OpenRFID Generic | Same paxx12 | OpenSpool and OpenTag3D | Generic changes brand identification, not the accepted formats |
| U1 | Original built-in reader | Stock | None | Native Snapmaker tags are not generated here |
| U1 | SpoolSense network scanner, External mode | paxx12 + Moonraker API; scanner 1.7.5+ | OpenSpool and OpenTag3D | Sends to the configured channel; do not select internal OpenRFID mode for this scanner |
| U1 | wasikuss or baze ESP32/PN532 remote reader | paxx12, External mode | OpenSpool | OpenTag3D support not established for these two specific readers |
| Flashforge AD5X / Creator 5 | ACR122U or PN532 USB with FF_NFC | Zmod | OpenSpool and OpenTag3D | Plugin required; material/colour assignment. Upstream hardware reports do not establish our OpenTag3D acceptance |
| Flashforge AD5X only | USB + FF_NFC | Kiln OS | OpenSpool and OpenTag3D | Early integration; complete physical workflow not established |
| Flashforge AD5X / Creator 5 | LaneTag Wi-Fi + FF_NFC | Zmod | OpenSpool and OpenTag3D | Network connection with upstream modules and limits |
| Bambu Lab | OpenSpool ESP32/PN532 over MQTT | Stock, LAN access allowed | OpenSpool | Check model and firmware restrictions; AMS does not directly decode this tag |
| Bambu Lab | SpoolSense + Home Assistant | Stock, LAN Only + Developer Mode | OpenSpool and OpenTag3D | Scanner 1.7.0+, TFT, MQTT, Bambu integration, automation and Spoolman required |
| Klipper / Moonraker | SpoolSense network + middleware | Klipper with configured macros | OpenSpool and OpenTag3D | Middleware sends data to the machine; Klipper or Spoolman alone is insufficient |
| Klipper / Moonraker | nfc2klipper on host; PN532 UART in the documented example | Klipper + nfc2klipper service | None for this workflow | Spoolman/UID references and experimental OpenTag3D v0.12; 2.004 support unconfirmed |
| Prusa CORE One / L | Official OpenPrintTag accessory | Stock 8.0+ | None | CAN xBuddy bus; OpenPrintTag not exported here; manufacturer INDX/MMU3 exclusions |
| Prusa MK4 / MK4S / MMU3 | SpoolSense + PrusaLink / Home Assistant | Stock | OpenSpool and OpenTag3D for scanner | Experimental external inventory/control; no filament on the Prusa display or firmware slot assignment |
| Creality K1 / K1 Max | SpoolSense with stock firmware | Stock | OpenSpool and OpenTag3D for scanner | External inventory only; no spool data sent to firmware |
| Creality K1 / K1 Max | SpoolSense + root/Moonraker + middleware | Modified | OpenSpool and OpenTag3D | Configured machine integration; no stock USB plug-in guarantee |

Existing stock entries (Anycubic, Creality CFS, Elegoo, QIDI, UltiMaker, Raise3D,
MakerBot, XYZprinting) remain browsable. They have not been converted into USB
extension promises: unverified information is labelled and enables no export.
Generic OpenSpool/OpenTag3D readers prepare a tag for an explicitly compatible
reader, without guaranteeing a connection to a particular printer.

## Version limits

The SpoolSense decoder reviewed at
`6070713488b45e51d2dc81124882775253dee2f0` declares OpenTag3D **2.003**.
It correctly decoded 100 SpoolScribe **2.004** payloads, each with a minor-version
warning. This validates the checked fields in software, not radio operation,
slot assignment or complete tag rewriting. The general SpoolSense description
of CBOR conflicts with its binary v2 decoder; the review examined that code
without redistributing it.

FF_NFC declares OpenTag3D 2.x; its published hardware tests remain separate from
our software tests. BambuTagger and OpenSpool firmware variants limited to
OpenTag3D v1 are not enabled merely because they mention the standard.
No OpenPrintTag or proprietary manufacturer encoder is added.

## Preserved preferences and structured data

The historical `firmwares` field in `data/printers.json` remains readable by old
clients. Entries now describe complete setups: `connection`, `firmware_kind`,
`reader`, `reader_formats`, `formats`, `effect`, `evidence`, `url`, `choice_label`
and documentary date. `formats` is limited to implemented encoders; an unverified
setup cannot enable an export in this schema.

Old U1/paxx12 and stock U1 choices are preserved. The separate legacy Bambu +
OpenSpool reader entry maps to **Bambu → OpenSpool network reader**, preserving
the chosen reader. A combined legacy Prusa entry becomes **model to specify**,
never an automatic CORE One/CAN selection. Generic Klipper no longer implies
OpenSpool decoding without an identified integration: nfc2klipper reference
linking/old v0.12 decoding remains distinct from 2.004 reading. Filament data,
personal corrections and Orca profiles are unaffected by this reorganisation.

## Primary references

- [paxx12 modes and RFID formats](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware/blob/develop/docs/design/rfid.md).
- [FF_NFC readers, platforms and limits](https://github.com/DIEHARDave/FF_NFC), revision `fea14b226f09ab3537c326a6cbbc4c97954ba8a0`; replaces zmod_nfc.
- [SpoolSense compatibility](https://spoolsense.org/resources/compatibility/), [U1](https://spoolsense.org/installation/snapmaker-u1/), [Bambu](https://spoolsense.org/installation/bambu-ams/), [Prusa limits](https://spoolsense.org/installation/prusa/), [Klipper middleware](https://spoolsense.org/installation/middleware/).
- [Pinned SpoolSense binary decoder](https://github.com/SpoolSense/spoolsense_scanner/blob/6070713488b45e51d2dc81124882775253dee2f0/lib/opentag3d/opentag3d_lib.c).
- [OpenSpool external reader and MQTT](https://github.com/spuder/OpenSpool).
- [nfc2klipper Spoolman references](https://github.com/bofh69/nfc2klipper).
- [Prusa accessory, models, CAN and exclusions](https://www.prusa3d.com/product/openprinttag-upgrade/), [required firmware](https://help.prusa3d.com/article/prusa-openprinttag-upgrade-for-core-one-l_1246289).
