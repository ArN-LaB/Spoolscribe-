# Install a local macOS build on this Mac

This developer workflow builds committed sources and prepares a personal
installation with a backup. It is not part of the application and does not
change the public-download workflow. Gatekeeper remains enabled.

## Prepare the build

Use macOS, Git, an explicit Python 3.12 interpreter and the dependencies from
`requirements/requirements-build.txt` in that interpreter's environment
([development guide](DEVELOPMENT.md)). Review a checkout of
`ArN-LaB/homebrew-tap` containing `developer-tools/macos-local-installer`
**0.1.1**, published as `local-installer-v0.1.1`. In that component checkout, use
`git checkout local-installer-v0.1.1`. Preserve and commit your SpoolScribe changes
before building from a clean source tree.

```sh
export ARNLAB_PYTHON="$PWD/.venv/bin/python"
# Only if homebrew-tap is outside its usual ~/Documents/GitHub location:
export ARNLAB_INSTALLER_ROOT="/path/homebrew-tap/developer-tools/macos-local-installer"
./install-local.command --dry-run
./install-local.command --build-only
./install-local.command --build --simulate
./install-local.command
```

Double-clicking `install-local.command` opens the interactive workflow with
`python3`. Set `ARNLAB_PYTHON` in Terminal if that interpreter lacks dependencies.
The component version and SHA-256 are pinned in `.macos-local-install.json`;
no remote script is downloaded or executed automatically.

The build uses a Git export in a separate private folder. Existing `build/`,
`dist/`, personal data, preferences, catalogue and Orca profiles are not
overwritten. The manifest uses `packaging/spoolscribe.spec`; the output format
is unchanged. Its bundle is `dist/SpoolScribe.app` inside the export, with the
identifier `com.github.arn-lab.spoolscribe`.

## Install or roll back

The build prints a bundle path and a private receipt UUID. Reuse that build
without rebuilding:

```sh
./install-local.command --app /path/SpoolScribe.app --receipt RECEIPT_UUID
./install-local.command --rollback TRANSACTION_UUID
./install-local.command --list-backups
```

Quit the target application normally before installing or restoring. The engine
checks activity without stopping processes and refuses a Homebrew-managed target.
It requires the literal confirmation `INSTALLER`. If quarantine is detected,
removing it from the **prepared copy only** requires the separate literal
`RETIRER`. These are the installer's existing command tokens, not translated UI
instructions. Refusing cancels installation and preserves existing files.

An invalid signature, unexpected identifier or receipt mismatch is refused.
A GitHub ZIP or SHA-256 file does not replace a local receipt: rebuild from
source for this workflow. No valid signature is replaced.

An update retains the previous application in
`/Applications/.arnlab-local-installer/UUID/previous.app`. Rollback requires the
literal token `RESTAURER` and refuses copies changed since installation.
Backups and logs are retained; `--list-backups` reports sizes and states without
deleting them. There is no automatic purge: review them before manual cleanup.
No privilege escalation or automatic SpoolScribe launch is performed.

See the [shared component's contract and limits](https://github.com/ArN-LaB/homebrew-tap/tree/main/developer-tools/macos-local-installer).
The guide is available on `main`; the manifest remains pinned to the engine
version and SHA-256, never a moving branch. An ad hoc personal-build signature
is not notarisation. Actual launch and this Mac's administration policies still
require verification after approval.
