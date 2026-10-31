# FAQ

## Is this an official app of a filament manufacturer or of Snapmaker?

No. SpoolScribe is an **unofficial hobby project**, not affiliated with, endorsed
by, or connected to any filament manufacturer (Polymaker, Bambu Lab, Prusa
Research, SUNLU, eSUN…) or to Snapmaker. See
[TRADEMARKS.md](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/TRADEMARKS.md).

## Does it send my data anywhere?

No. There is **no telemetry, no tracking, no account**. The network is used for
three things only, all listed before you agree: the first download of the
catalogue, the refresh of the sources you selected (at the cadence you choose,
daily by default, or when you click **Mettre à jour**), and the release check
when you click **⋯ → Vérifier une mise à jour de l'application**. Servers see
your IP and the User-Agent, nothing about your catalogue or printer. See
[PRIVACY.md](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/PRIVACY.md).

## Why is the app empty after installation?

The installer contains no catalogue. Choose your sources in the first dialog
and click **Télécharger et enregistrer**. Offline, nothing can be shown until a
first download has succeeded; afterwards the cached catalogue works offline.

## Is the data free to use?

The code is MIT. Open Filament Database and SpoolmanDB are MIT;
[TheFilamentDB](https://thefilamentdb.issou.best/) is CC-BY 4.0 (attribution
provided); manufacturer pages provide factual values only. Logos remain the
trademarks of their owners. Full details:
[DATA_SOURCES.md](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/DATA_SOURCES.md).

## Do I need the paxx12 firmware?

To have the **[Snapmaker U1](https://snapmaker.com/snapmaker-u1) read tags
automatically**, yes — the
[paxx12 fork](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware)
exposes the RFID reader. SpoolScribe itself only generates the tag payloads and
works on any machine. Other OpenSpool-capable readers can use the same files.

## A reference is missing, has no colour, or is marked « À vérifier »

- **Missing colour**: the GUI and the CLI ask for an explicit representative HEX
  at export time; cancelling the colour cancels the export.
- **Missing temperatures / density / diameter**: use **Compléter / corriger les
  caractéristiques…**; the values apply to every variant of that product.
- **« À vérifier »**: the source published a value that contradicts itself
  (for example a black HEX for a "White" filament, or a density of 7 g/cm³).
  Open the card, correct the value explicitly, and the record becomes exportable.
- **Missing reference**: the CLI can add an unknown reference against an existing
  product. Contributions upstream (to Open Filament Database or SpoolmanDB)
  benefit everyone.

Your corrections are saved locally and survive every refresh.

## What does « Export possible » mean?

Only that the fields OpenSpool needs are filled in. It says nothing about the
filament's quality, nor that every printer recognizes the tag.

## Which tag and which profile?

NTAG215 (504 bytes) or NTAG216 (888 bytes). The recommended *essential* profile
(material, colours, temperatures, diameter, density) fits every reference on
both. The *full* profile adds names and brand metadata and is an explicit choice.
See [[Writing RFID Tags|Writing-RFID-Tags]].

## Which tag hardware do I need?

Any NFC writer able to write an NDEF MIME `application/json` record, for example
SpoolFlux on iPhone. See [[Writing RFID Tags|Writing-RFID-Tags]].

## Can I remove a manufacturer logo?

Logos are bundled in the application; the packaged app shows the brand name when
a logo is absent. To build your own copy without a logo, remove its file from
`data/brand_logos/` and its entry in `manifest.json` (or list the brand in
`.github/catalogue-logo-exclusions.json`). Trademark holders can also ask for
removal by opening an issue.

## Where are my files?

Database, settings and exports are in your user folder, never next to the
application: `%APPDATA%\SpoolScribe` (Windows), `~/Library/Application
Support/SpoolScribe` (macOS), `~/.config/SpoolScribe` (Linux). Backups
(`polymaker_db.json.bak`, `.pre-update.bak`) sit next to the database.
