# Interface translations

SpoolScribe 0.3.5 provides English (`en`), French (`fr`), Spanish (`es`) and
Simplified Chinese (`zh_CN`). This selection extends the existing French interface;
it is not a claim that these are the four most spoken languages by every measure.

`src/spoolscribe/i18n.py` resolves the operating system's preferred UI languages: native
CoreFoundation preferences on macOS, Qt elsewhere. An explicit saved choice wins;
unsupported locales fall back to English. Traditional Chinese is not labelled as
supported. Settings → Interface shows the effective automatic language.

After saving or importing a different language, the app offers Restart now / Later.
Restart now is disabled during an update. The new process is launched after the
data-folder lock is released, using the same executable or source interpreter.
The preference is included in settings export/import.

`messages.json` contains French source messages and their three translations.
French uses the source message directly. A missing language entry falls back to
English, then the original message for unknown technical diagnostics. Normal UI
messages must have all three translations; `tests/test_v035.py` checks literal
`tr()` calls, complete language coverage and matching named placeholders.

- Translate display text through `tr()`; never translate dictionary keys, source
  identities, SKU numbers, commercial product/colour names or saved favourite IDs.
- Translate templates before interpolation, e.g. `tr('Teinte {v0}', v0=number)`.
  Preserve placeholder names, conversion flags and format specifications.
- Keep externally supplied technical logs verbatim. Printer specifications remain
  in their source catalogue; translate their presentation at the UI boundary.
- The CLI and OpenSpool encoder keep their existing behaviour. Interface language
  does not change JSON keys, values, encoding, capacity calculations or catalogues.
- `src/spoolscribe/packaging_rules.py` includes this JSON in all three native bundles. The frozen
  catalogue probe renders the actual main window in all four languages offline.

Translations are maintained with the code and need native-speaker review. No
online translation service is called by the application.


The macOS bundle declares `en`, `fr`, `es`, `zh-Hans` localizations with English
as its development fallback. Native UI preferences avoid confusing regional/POSIX
locale (`C`, or an English locale in a launcher) with the chosen macOS UI language.
Read-only native detection falls back to Qt if unavailable.

The relaunch helper sets `PYINSTALLER_RESET_ENVIRONMENT=1` in frozen builds so the
new process does not depend on the old onefile extraction directory. If spawning
fails, the current window is reopened only after reacquiring its data-folder lock;
settings remain saved. No network refresh is interrupted to apply a language.
