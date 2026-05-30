# Contributing to SpoolScribe

Thanks for your interest! SpoolScribe is a small, for-fun project, so contributing
is meant to be low-friction.

## Ground rules

- Be respectful — see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
- Keep the project **honest about licensing**. Any new data source **must**:
  - have a clearly compatible license (MIT/CC-BY/public-domain facts), and
  - be documented in [DATA_SOURCES.md](../docs/DATA_SOURCES.md), and
  - be added to `core.NETWORK_SOURCES` so it appears in the consent disclosure.
- Never add silent network calls. **All** network access must stay behind the
  explicit consent gate (see [PRIVACY.md](../docs/PRIVACY.md)).
- Don't bundle new trademarked assets without noting them in
  [TRADEMARKS.md](../docs/TRADEMARKS.md).

## Architecture

- `core.py` — **pure logic, no `print`/`input`**. Put business logic here.
- `app_gui.py` — Qt UI only.
- `convert_profile.py` — terminal UI only.
- `scripts/` — standalone scrapers (standard library; no heavy deps).

If you add a feature, prefer putting the logic in `core.py` so both the CLI and
GUI benefit.

## Dev setup

```sh
python -m venv .venv
# Windows:        .venv\Scripts\activate
# macOS / Linux:  source .venv/bin/activate
pip install -r requirements.txt
```

Quick checks before opening a PR:

```sh
python -c "import core, app_gui, convert_profile; print('imports OK')"
python convert_profile.py   # smoke-test the CLI
python app_gui.py           # smoke-test the GUI
```

## Pull requests

1. Fork and create a feature branch.
2. Keep changes focused and small.
3. Describe **what** changed and **why** in the PR.
4. Confirm no new un-consented network access was introduced.

## Reporting bugs / ideas

Use the issue templates under **New issue**. Include your OS, Python version,
and steps to reproduce. See also [SECURITY.md](SECURITY.md) for private reports.
