# Contributing to SpoolScribe

Small contributions are welcome: a reproducible bug, a clearer instruction or a
well-sourced filament correction can be useful without writing application code.

| You want to… | Start here |
|---|---|
| Report a bug | [Bug report](https://github.com/ArN-LaB/Spoolscribe-/issues/new?template=bug_report.yml) — app version, OS and steps; Python only if running from source. |
| Suggest an improvement | [Feature request](https://github.com/ArN-LaB/Spoolscribe-/issues/new?template=feature_request.yml) — explain the problem you want to solve. |
| Improve a source or translation | Open a focused PR and include the source/evidence. See the requirements below. |
| Report a vulnerability | Use the [private security channel](SECURITY.md). |

Please follow the [code of conduct](CODE_OF_CONDUCT.md).
For source setup, CLI examples and packaging, see [development](../docs/DEVELOPMENT.md).

## Dev setup

```sh
python -m venv .venv
# Windows:        .venv\Scripts\activate
# macOS / Linux:  source .venv/bin/activate
pip install -r requirements.txt
```

Quick checks before opening a PR:

```sh
python -B -m unittest discover -s tests -t . -v
python -c "import core, app_gui, convert_profile; print('imports OK')"
python convert_profile.py   # smoke-test the CLI
python app_gui.py           # smoke-test the GUI
```

Core tests need Python 3.10+ and `certifi`; GUI tests need PySide6 and are
skipped otherwise (set `QT_QPA_PLATFORM=offscreen` on a headless machine). The
tests block network connections, use temporary user data, and never contact a
printer or a personal Spoolman instance. Build with Python 3.12 and
`requirements-build.txt` for the recorded dependency snapshot.

Packaged QA can isolate its data with `SPOOLSCRIBE_DATA_HOME` and its consent
settings with `SPOOLSCRIBE_CONFIG_PATH`, both pointing inside a temporary folder.
Never run acquisition scripts against a real database during tests; run directly,
the workers write to the user data folder, never to the repository fixture.

## Commits and pull requests

1. Fork and create a feature branch.
2. Keep changes focused and small; one logical change per commit.
3. Commit messages are in French and follow the conventional prefixes used in
   the history: `feat:`, `fix:`, `build:`, `ci:`, `docs:`, `test:` — for example
   `fix(sync): cadence et annulation`.
4. Add the change to the *Unreleased* section of [CHANGELOG.md](../CHANGELOG.md);
   that text becomes the release notes.
5. Describe **what** changed and **why** in the PR, and confirm no new
   un-consented network access was introduced.

## Reporting bugs / ideas

Use the issue templates under **New issue**. Include your OS, Python version,
and steps to reproduce. See also [SECURITY.md](SECURITY.md) for private reports.

<details>
<summary><strong>Requirements for catalogue, network, logo and printer changes</strong></summary>

## Data and network requirements

- Be respectful — see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
- Keep the project **honest about licensing**. Any new data source **must**:
  - have a clearly compatible licence (MIT / CC-BY / public-domain facts),
  - be added as a group in `core.SOURCE_GROUPS` (name, hosts, worker scripts),
    which feeds the consent dialog and `core.NETWORK_SOURCES`, and
  - be documented in [DATA_SOURCES.md](../docs/DATA_SOURCES.md) and
    [PRIVACY.md](../docs/PRIVACY.md); bump `core.NETWORK_SOURCES_REVISION` so
    existing users are asked again.
- Never add silent network calls. **All** network access stays behind the
  explicit consent gate, goes through a bounded same-host fetcher
  (`scripts/official_sources.fetch` or an equivalent with size limit, declared
  User-Agent and redirect check), and sends `If-None-Match` when the server
  supports it.
- Don't bundle new trademarked assets without noting them in
  [TRADEMARKS.md](../docs/TRADEMARKS.md).
- Never guess a value: unknown stays `null`, user corrections (provenance
  `Utilisateur`) are never overwritten, identities are never merged on
  material/colour alone. A manufacturer source may correct fields of unknown
  provenance; a community source may only complete them.
- A new manufacturer logo needs a transparent background and a recorded origin:
  add it through `.github/scripts/import_brand_logos.py` (review file + files),
  never by copying an image into `data/brand_logos/`; `tests/test_logos.py`
  checks the result. Note the mark in [TRADEMARKS.md](../docs/TRADEMARKS.md).
- A new printer or reader is a `data/printers.json` entry (group, reader,
  firmwares with the `openspool` flag, help), not code; cite a primary source
  and list what is unverified.


</details>

## Architecture

- `core.py` — **pure logic, no `print`/`input`**. Put business logic here.
- `app_gui.py`, `ui_catalogue.py` — Qt UI only (sidebar, card, **Mon matériel**,
  sources and report dialogs).
- `printer_profiles.py` + `data/printers.json` — printers/readers catalogue.
- `convert_profile.py` — terminal UI only.
- `scripts/` — source adapters (`catalogue_sources.py`, `official_sources.py`,
  `catalogue_merge.py`), update workers (`sync_*.py`, standard library only)
  and legacy scrapers kept for reference.

If you add a feature, prefer putting the logic in `core.py` so both the CLI and
GUI benefit.

## Universal catalogue changes

See [the data contract](../docs/DATA_FORMAT.md). Keep source adapters pure and
standard-library-only, preserve unknowns and local corrections, and add offline
fixtures for each source/schema edge case. Never run live requests from the test
suite. Review snapshot audit reports and logo contact sheets; do not overwrite
the historical catalogue or Orca profiles to update a supplement. The 1,008
historical exports are checked byte for byte: a deliberate change to the export
format must be verified and recorded in `tests/fixtures/legacy_catalogue_contract.json`.
