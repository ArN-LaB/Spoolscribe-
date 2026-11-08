# Software stability and hardware compatibility

[Download v0.8.1](https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.8.1) · [Printer and reader help](wiki/Printers-and-Readers.md) · [Validation](validation/v0.8.1.md)

The current stable desktop release supports the documented software workflow. It does not imply physical testing of every printer, reader or tag listed in the catalogue.

## Choose the complete setup

Compatibility depends on the printer model, reader, connection, firmware or plugin, NFC format and tag capacity. A USB port or an NFC chip alone does not establish support. Check the [configuration guide](PRINTER-CONFIGURATIONS.md) before exporting or writing a tag.

| Evidence | What it tells you |
| --- | --- |
| Documented setup | A cited source describes the model, reader, firmware/plugin and accepted format. |
| Software-validated export | Automated checks cover the exported bytes, size bounds and transfer contract. |
| Physically tested setup | A dated result identifies the exact printer, reader, firmware/plugin, tag and read-back. |
| Unsupported or unknown | The integration is not established; successful use is not promised. |

An untested setup is not automatically incompatible. Verify the result on the real hardware before relying on it. These descriptions explain evidence; they are not runtime certification badges.

## Desktop downloads

v0.8.1 provides Windows and Linux x86_64 builds and a macOS Apple Silicon arm64 build. macOS requires version 15.0 or later; its archive is Developer ID signed, Apple-notarised and stapled. Intel/universal2 is not supplied. Older operating systems and every Linux distribution are not qualified by the release's software checks.

The [dated validation](validation/v0.8.1.md) and [publication record](archive/releases/v0.8.1.md) identify actual tests, skips, source references and known limits. Historical downloads remain available with their own requirements and validation; availability does not confer current support or today's notarisation on an older build.

## Companion and physical results

Companion is a separate mobile application with its own availability and review process. Desktop validation or macOS notarisation does not establish Companion App Store approval. See [mobile availability](COMPANION.md), [Companion support](https://arn-lab.github.io/Spoolscribe-/support/) and [Companion privacy](https://arn-lab.github.io/Spoolscribe-/privacy/).

When [sharing a hardware result](https://github.com/ArN-LaB/Spoolscribe-/issues/new/choose), include the exact printer, reader, firmware/plugin, tag, exported format and observed result. Software tests do not replace physical NFC writing/read-back, paper printing or printer recognition.
