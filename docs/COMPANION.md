# SpoolScribe Companion

[Desktop v0.8.0 stable](../README.md) · [QR help](wiki/Companion-and-QR.md) · [SSQR1 contract](QR_FORMAT.md)

**The mobile application is in development. Official downloads are not available yet.**
This is the common availability page for iOS and Android. Desktop opens this page
rather than guessing your phone from your computer's operating system.

| Platform | Availability |
| --- | --- |
| iOS | Development/testing in progress. The official App Store link will appear when published. |
| Android | No official public download link available. |

## What Desktop can already do

Display and save an **SSQR1 QR containing the complete NFC message**, without a
server. A generic scanner can read the transfer text; it does not program a chip
or necessarily open Companion. When available, use Companion's own scanner to
validate the transfer before proposing an NFC write.

QR protection M/Q is damage correction, not app exclusivity or encryption.
SHA-256 verifies integrity, not authenticity. No URL, store link or app-launch
instruction is inserted into the stable SSQR1 contract.

Future camera-to-app routing needs verified iOS Universal Links / Android App Links,
a controlled domain and the released mobile apps. It is not deployed here.
[Technical distinction and sources](wiki/Companion-and-QR.md#does-scanning-force-companion-to-open).

## Help and project information

[Desktop help centre](wiki/Home.md) · [Support / Issues](https://github.com/ArN-LaB/Spoolscribe-/issues/new/choose) · [Desktop privacy policy](PRIVACY.md).
The mobile privacy/support information must be checked against the actual mobile
implementation before its store submission; no mobile compliance is claimed here.
