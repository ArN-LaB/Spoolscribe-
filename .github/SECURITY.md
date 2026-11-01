# Security policy

SpoolScribe runs locally, but downloaded data and exported files still need care.
Security reports are welcome; please keep vulnerability details private.

## Supported versions

Current stable release: [v0.3.5](https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.3.5).

The [latest stable GitHub Release](https://github.com/ArN-LaB/Spoolscribe-/releases/latest)
is the supported version. `main` may include changes for the next release.

## Report privately

Use **[Report a vulnerability](https://github.com/ArN-LaB/Spoolscribe-/security/advisories/new)**
or open the repository's **Security** tab and select that option. Private
vulnerability reporting is enabled for this repository.

Please include what happened, its impact, your app version and OS, and minimal
steps to reproduce. Redact credentials, personal catalogue contents and private
network details. A small synthetic example is preferable to a personal database.

If the private form is unavailable, open an issue titled `SECURITY` to request a
private channel, without disclosing the vulnerability. This is a hobby project
without a response-time guarantee; confirmed security issues take priority.

## Scope

| Area | Behaviour and relevant concerns |
|---|---|
| Network | Outbound HTTPS GET after explicit consent; downloaded data, redirects, size limits and source validation matter. No server or inbound listening port. |
| Local storage | The app stores a catalogue, preferences, backups and exports in the user folder. Safe paths, atomic writes and preservation of local changes matter. |
| Update workers | Bundled scripts process external data. Script allowlisting and avoidance of command injection matter. |
| NFC exports | The app prepares JSON; it does not program tag memory, modify firmware or associate hardware UIDs. |

See [network transparency](../docs/PRIVACY.md), [data sources](../docs/DATA_SOURCES.md)
and [storage/data format](../docs/DATA_FORMAT.md).

The security of third-party source services, printer firmware and RFID hardware
is outside this repository's control. Report vulnerabilities in those projects
to their respective maintainers.
