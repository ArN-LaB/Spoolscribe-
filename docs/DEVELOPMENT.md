# Develop and build SpoolScribe v0.8.1

[Documentation](README.md) · [Contributing](../.github/CONTRIBUTING.md) · [Repository layout](REPOSITORY.md)

Run commands from the repository root. Python 3.10 and 3.12 are tested; use
Python 3.12 for PyInstaller builds.

## Get the sources

For the complete test and repository checks, use a Git checkout:

```sh
git clone https://github.com/ArN-LaB/Spoolscribe-.git
cd Spoolscribe-
```

The checkout follows `main`. To reproduce a published version, check out its tag
and follow that version's instructions and dependency files.

GitHub also provides **Source code (zip)** and **Source code (tar.gz)** under each
release's **Assets**. These contain the tagged sources, not a ready-to-run app.
For the current source layout, extract one, install the build dependencies below
and run `pyinstaller packaging/spoolscribe.spec --noconfirm` from its root.
The repository checker and Git-dependent tests require the Git checkout instead.

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
python .github/scripts/check_frozen_measurements.py
```

Output stays `dist/SpoolScribe.exe` (Windows), `dist/SpoolScribe` (Linux) and
`dist/SpoolScribe.app` (macOS). Each ZIP contains one native executable or one
`.app`, with a companion SHA-256 file. CI macOS builds are ad hoc intermediates. The v0.8.1 release uses the separately
Developer ID signed, notarised and stapled build. `python packaging/macos_notarize.py --help` describes the signing tool; supplying valid signing credentials remains a maintainer responsibility.

The [workflow](../.github/workflows/build.yml) tests four Python/OS configurations and checks frozen application behaviour and resource integrity. Historical archives retain their own tagged sources and checksums; a new source build uses a new version rather than replacing an old download.

A local source build does not inherit the published archive's signature,
notarisation or validation record. You can build for your own use without signing
credentials; macOS distribution signing is a separate step.

## Data and resources

`src/spoolscribe/core.py` is the version authority. Source resources are grouped in
`data/`; workers remain in `scripts/`. frozen resources use `sys._MEIPASS`.
The read-only catalogues, audits and all 48 `tests/fixtures/orca/` files are regression fixtures,
excluded from installers. Workers write to the user folder.

Before importing the package, isolate QA with `SPOOLSCRIBE_DATA_HOME` and
`SPOOLSCRIBE_CONFIG_PATH`. Do not run live updates against repository fixtures.
See [the data contract](DATA_FORMAT.md) for backups and restoration.

## Documentation and Wiki

`docs/wiki/` contains the reviewed source of the public help centre. Keep changes portable between the source files and GitHub Wiki routes. The helper `.github/scripts/sync_wiki.py` previews/copies reviewed pages into a separate clean checkout; it does not commit, push or delete pages.

Public release evidence lives in `docs/validation/` and `docs/archive/releases/`. Their dates and measured outcomes describe the corresponding historical versions.

## Reproduce documentation captures

```sh
python .github/scripts/render_readme_screenshots.py
```

Real Qt captures and `docs/images/captures.json` use public regression fixtures,
a temporary database/configuration and a network-denying audit hook. This is a
documentation tool, not a runtime dependency or hardware test. The QR illustration
is the top of the real window through PNG/SVG actions; its printing band is omitted.
The animated logo is preserved. See [image provenance](images/README.md).

For native digital QR QA, CI installs Pillow and `zxing-cpp==2.3.0` only **after**
PyInstaller, then runs `.github/scripts/check_frozen_ssqr1.py`. They must stay out
of the application bundle. Independent scans verify exact SSQR1/NDEF restoration;
they do not certify a camera, printer or NFC reader.

## Linux desktop runtime

The native Linux archive is x64, built on `ubuntu-latest`. It needs a compatible
glibc, EGL, DBus and the Qt platform dependencies of the target desktop. For X11,
the release build reports these external library names (some repeat across plugins):

```text
libxcb-util.so.1        libxkbcommon-x11.so.0   libxcb-cursor.so.0
libxcb-shape.so.0       libxcb-xkb.so.1         libxcb-keysyms.so.1
libxcb-image.so.0       libxcb-render-util.so.0 libxcb-icccm.so.4
```

Install the corresponding Qt/X11 runtime packages for your distribution rather
than copying arbitrary shared libraries into the app. CI uses Qt offscreen:
passing those digital checks does not measure a native X11/Wayland desktop session.
[Exact release build log](https://github.com/ArN-LaB/Spoolscribe-/actions/runs/41650816610/job/125971039581).
