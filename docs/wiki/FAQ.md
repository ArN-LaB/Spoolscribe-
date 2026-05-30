# FAQ

## Is this an official Polymaker or Snapmaker app?

No. SpoolScribe is an **unofficial hobby project**, not affiliated with, endorsed
by, or connected to Polymaker or Snapmaker. See `TRADEMARKS.md`.

## Does it send my data anywhere?

No. There is **no telemetry, no tracking, no account**. The only network access
is the optional, consent-gated database update. See `PRIVACY.md`.

## Is the data free to use?

The code is MIT. Most data sources are MIT; [TheFilamentDB](https://thefilamentdb.issou.best/) is CC-BY 4.0
(attribution provided). Some factual values come from Polymaker's public pages.
Full details: `DATA_SOURCES.md`.

## Do I need the paxx12 firmware?

To have the **[Snapmaker U1](https://snapmaker.com/snapmaker-u1) read tags automatically**, yes — the [paxx12 fork](https://github.com/paxx12) exposes the
RFID reader. SpoolScribe itself just generates the tag payloads and works on any
machine.

## A SKU is missing or has no color. Can I fix it?

Yes. You can add unknown SKUs and enter a hex value directly in the app; it's
saved to your local database. Contributions back upstream are welcome — see
`CONTRIBUTING.md`.

## Which tag hardware do I need?

Any NFC/RFID writer compatible with the tag format your reader expects. See
[[Writing RFID Tags|Writing-RFID-Tags]].

## Can I remove the Polymaker logo?

Yes — delete `data/polymaker_logo.svg`. The app works fine without it.
