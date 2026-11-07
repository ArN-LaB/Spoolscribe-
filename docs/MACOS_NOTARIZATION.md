# Sign and notarise SpoolScribe for macOS locally

[Development](DEVELOPMENT.md) · [Release policy](RELEASE_POLICY.md) · [Personal installation](LOCAL_MACOS_INSTALL.md)

This procedure creates a macOS distribution **outside the Mac App Store**:
Developer ID signature, Hardened Runtime, Apple notarisation, a stapled ticket
and `SpoolScribe-macos.zip`. It runs **locally first**, using the standard-library
[`packaging/macos_notarize.py`](../packaging/macos_notarize.py) tool.

The historical v0.8.0 archive remains ad hoc signed and **not notarised**.
v0.8.1 uses a new local Developer ID build, notarised and stapled; exact results
are recorded in [v0.8.1 validation](validation/v0.8.1.md).
The [workflow](../.github/workflows/build.yml) does not apply Developer ID signing
or notarisation. This local tool publishes nothing, creates no tag/release and
replaces no existing file. Its pilot covers **arm64 only**; Intel/universal2 and
macOS versions below the measured minOS are not promised.

## Prerequisites supplied by the account holder

Use Xcode, `notarytool`, `stapler` and an explicit arm64 **Python 3.12** interpreter.
A valid **Developer ID Application** identity and its private key must be in the
keychain. Apple Development, Apple Distribution, Developer ID Installer and ad
hoc identities are refused. An individual-account certificate may expose the
holder's **legal name** in every distributed signed binary: review the subject
privately and accept that consequence before distribution.

The account holder creates a `notarytool` profile interactively, without putting
a password in a command argument:

```sh
xcrun notarytool store-credentials "spoolscribe-notary-local"
```

The tool creates no certificate, exports no key and changes neither the keychain
nor the Apple account. It receives only the selected identity's SHA-1 fingerprint
and the profile **name**.

## Procedure

Run from the reviewed checkout. `WS` must be a **new absolute folder**, outside
the checkout and synchronised storage (iCloud, Proton Drive, File Provider).
It is created with mode 0700 and an ownership marker. Later steps refuse another
folder, a symlink or a moved copy.

```sh
PY312=/path/python3.12
WS=/private/path/spoolscribe-notarisation-YYYYMMDD
python3 -B packaging/macos_notarize.py preflight --python "$PY312" [--identity SHA1] [--profile PROFILE]
python3 -B packaging/macos_notarize.py prepare --workspace "$WS" --commit FULL_SHA --python "$PY312"
python3 -B packaging/macos_notarize.py build    --workspace "$WS"
python3 -B packaging/macos_notarize.py inspect  --workspace "$WS"
python3 -B packaging/macos_notarize.py probes   --workspace "$WS"
python3 -B packaging/macos_notarize.py sanitize --workspace "$WS"
# Each signing/Apple/network step needs explicit pilot authorisation and its confirmation.
python3 -B packaging/macos_notarize.py sign     --workspace "$WS" --identity SHA1 --confirm-signing
python3 -B packaging/macos_notarize.py probes   --workspace "$WS"
python3 -B packaging/macos_notarize.py notarize --workspace "$WS" --profile PROFILE --confirm-submission
python3 -B packaging/macos_notarize.py staple   --workspace "$WS" --confirm-stapling
python3 -B packaging/macos_notarize.py package  --workspace "$WS"
python3 -B packaging/macos_notarize.py assess   --workspace "$WS" --confirm-assessment
python3 -B packaging/macos_notarize.py status   --workspace "$WS"
```

Exit codes: **0** success; **1** blocked; **2** usage error; **3** tooling ready
but human identity/profile prerequisites missing; **4 PENDING**. The tool may
print its historical French wording for some statuses; the numeric contract is unchanged.

| Step | Performs | Never performs |
| --- | --- | --- |
| `preflight` | Tools, interpreter and identity counts by type | Build, signing, Apple request or guessing a profile |
| `prepare` | Approved `git archive`, blob-by-blob verification and private pinned build venv | Moving a ref or including uncommitted changes |
| `build` | PyInstaller with the unchanged spec and private cache | Reusing the checkout's `dist/` |
| `inspect` | Mach-O headers, `lipo`, `otool` (minOS/SDK, rpaths, dependencies), symlinks, Info.plist, resources and signing plan | Modifying the candidate |
| `probes` | QA oracles installed after PyInstaller; four offline frozen checks; candidate unchanged | Running on an already stapled candidate |
| `sanitize` | Removes `com.apple.FinderInfo` / `com.apple.ResourceFork` from the fresh copy | Touching the checkout or quarantine |
| `sign` | Nested code then bundles, inside out, with `--options runtime --timestamp` | Signing with `--deep`, ad hoc identity or default entitlements |
| `notarize` | Private submission ZIP, upload, bounded wait, `info` and log examination | Password arguments or automatic resubmission |
| `staple` | `stapler staple`, `validate`, `codesign --verify --deep --strict` | Stapling a ZIP or re-signing afterwards |
| `package` | `ditto -c -k --norsrc --noextattr --keepParent`, checksum and verified fresh extraction | Changing the workflow if a ticket is lost |
| `assess` | `spctl --assess --type execute -vvv` on a fresh extraction | Claiming a standard-user walkthrough was measured |

## Signing and notarisation safeguards

Inventory follows the Mach-O format, not filename extensions. Qt frameworks are
signed by version (`Versions/A`, etc.); symlinks (`Versions/Current`, root aliases)
are preserved and never signed. Broken, absolute, cyclic or escaping links block
progress, as does a non-system absolute dependency.

QtQml/QtQuick frameworks bundled by the virtual-keyboard plugin are retained.
Their presence does not justify a JIT exception. No entitlements are added by
default. An exception (`allow-jit`, `allow-unsigned-executable-memory`,
`disable-library-validation`) needs a reproduced, documented and approved failure
and applies only to the app. `get-task-allow` is forbidden.

Every object is checked for Developer ID Application type, Developer ID chain,
a single team, the `runtime` flag, a secure `Timestamp` (a mere `Signed Time` is
refused) and embedded entitlements. Every read must succeed before interpretation:
a failed, timed-out or partial entitlement extraction blocks progress; it never
means “no entitlements”. An approved app exception covers only the app and its
main executable. Detailed outputs stay private.

Only Apple **Accepted**, with the log examined for submission identifier,
submitted-ZIP digest, issues and `ticketContents` coverage, permits stapling.
Log types are validated before normalisation: absent or `null` is allowed where
documented; deceptive values (`{}`, `false`, `0`, `""`) are schema errors.
`Invalid`, unknown status, unexpected JSON or authentication failure blocks the
procedure. `--acknowledge-log-warnings` acknowledges reviewed warnings, never errors.

An interrupted or expired wait remains **PENDING**. Resume the retained submission
without uploading again:

```sh
python3 -B packaging/macos_notarize.py notary-status --workspace "$WS" --profile PROFILE \
    --confirm-apple-query [--wait-timeout 30m]
```

Any candidate modification after signing invalidates subsequent steps. Rebuild
in a new private workspace.

## Gatekeeper and standard-user walkthrough

An accepted `spctl` assessment does not prove the real first-launch journey.
On a Mac or **standard account** that has never approved SpoolScribe, keep
Gatekeeper enabled, download the ZIP in a browser (effective quarantine), extract
it and launch from Finder. Record the dialogs and repeat a launch offline.
Isolate data before any test launch:

```sh
export SPOOLSCRIBE_DATA_HOME=/test/path/data
export SPOOLSCRIBE_CONFIG_PATH=/test/path/config.json
```

Without that environment, record **NOT MEASURED**. Never remove quarantine to
obtain a PASS.

## Evidence and privacy

`WS/logs/` and `WS/private/` contain command logs, the notarisation log, certificate
subject, `codesign -dvvv` and `spctl` details. They stay private, outside the
repository, Pages and archives. Shareable output (terminal, `status`,
`WS/summary.md`) uses closed-vocabulary categories, counts and a private-detail
location. It must not expose Apple diagnostics, identity, team or personal paths.
An unexpected internal error prints only its type; its traceback stays in
`WS/private/`.

## Future CI integration — not implemented

A separately authorised follow-up after the local pilot could add a trusted
macOS signing step before packaging/checksums, a protected GitHub environment,
no secrets on PRs/forks, and a temporary keychain deleted at job end. No key may
enter the repository, logs or artifacts; base64 is not encryption. Keep global
`contents: read`. Signing or notarisation failure must prevent a partial release.
A notarised distribution needs a new version: never rerun an old tag to replace
its files.

Apple references: [notarisation](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution),
[custom workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow),
[common issues](https://developer.apple.com/documentation/security/resolving-common-notarization-issues),
[TN2206](https://developer.apple.com/library/archive/technotes/tn2206/_index.html),
[QA1940](https://developer.apple.com/library/archive/qa/qa1940/_index.html).
