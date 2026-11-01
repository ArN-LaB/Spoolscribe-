# Develop and build SpoolScribe v0.3.5

[Documentation](README.md) · [Contributing](../.github/CONTRIBUTING.md) · [Repository layout](REPOSITORY.md)

Run commands from the repository root. Python 3.10 and 3.12 are tested; use
Python 3.12 for PyInstaller builds.

## Run from an editable checkout

```sh
python -m venv .venv
# Windows:       .venv\Scripts\activate
# macOS / Linux: source .venv/bin/activate
python -m pip install -r requirements/requirements.txt
python -m pip install --no-deps -e .
python -m spoolscribe
```

The installed GUI command is `spoolscribe`. For the CLI, use `spoolscribe-cli`
or `python -m spoolscribe.convert_profile`.
`python packaging/gui_entry.py` also launches an uninstalled checkout.
The editable checkout supplies the resources and workers; a wheel is not a
supported standalone distribution. End users should use the PyInstaller archives.

## Tests and repository checks

```sh
python -B -m unittest discover -s tests -t . -v
python .github/scripts/check_repository.py
git diff --check
```

Set `QT_QPA_PLATFORM=offscreen` on a headless machine. GUI tests require PySide6;
CI installs it and runs the full suite. Tests block network connections and use
temporary data. They include the 1,008 historical export contract and protections
of local data, without contacting printers or personal services.

## Build a standalone app

Build on the target operating system:

```sh
python -m pip install -r requirements/requirements-build.txt
python -B -m unittest discover -s tests -t . -v
python .github/scripts/check_repository.py
pyinstaller packaging/spoolscribe.spec --noconfirm
python .github/scripts/check_frozen_tls.py
python .github/scripts/check_frozen_catalogue.py
```

Output stays `dist/SpoolScribe.exe` (Windows), `dist/SpoolScribe` (Linux) and
`dist/SpoolScribe.app` (macOS). Each ZIP contains one native executable or one
`.app`, with a companion SHA-256 file. macOS builds are ad hoc signed, not notarised.

The [workflow](../.github/workflows/build.yml) runs four test configurations before
three builds, then checks TLS, the frozen UI in four languages, resource integrity
and NTAG215/216 exports offline. Only a version tag can publish a release, after
all six assets are verified. The existing `v0.3.5` tag identifies the published
binaries: maintenance on `main` does not silently replace them or move the tag.

## Data and resources

`src/spoolscribe/core.py` is the version authority. Source resources are grouped in
`data/`; workers remain in `scripts/`. frozen resources use `sys._MEIPASS`.
The read-only catalogues, audits and all 48 `tests/fixtures/orca/` files are regression fixtures,
excluded from installers. Workers write to the user folder.

Before importing the package, isolate QA with `SPOOLSCRIBE_DATA_HOME` and
`SPOOLSCRIBE_CONFIG_PATH`. Do not run live updates against repository fixtures.
See [the data contract](DATA_FORMAT.md) for backups and restoration.
For personal macOS installation, use [the shared installer](LOCAL_MACOS_INSTALL.md);
Gatekeeper stays enabled.

## Documentation and Wiki

`docs/wiki/` is the reviewed source of the public GitHub Wiki. Preview and copy
to a separate, clean wiki checkout:

```sh
python .github/scripts/sync_wiki.py --checkout /path/to/Spoolscribe-.wiki
python .github/scripts/sync_wiki.py --checkout /path/to/Spoolscribe-.wiki --apply
```

The default is a dry run. Applying adjusts internal links for the Wiki and
preserves extra pages. Neither command commits, pushes or deletes files.
Review the diff and commit/push the separate Wiki repository explicitly.

Historical evidence lives in `docs/archive/`; current release evidence lives in
`docs/validation/`. Historical campaigns retain their original measured results.
