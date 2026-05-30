# Security Policy

SpoolScribe is a small hobby project, but security reports are taken seriously.

## Supported versions

The latest release on the `main` branch is the only supported version.

## Reporting a vulnerability

Please **do not open a public issue** for security-sensitive reports.

Instead, use GitHub's private reporting:

1. Go to the repository's **Security** tab.
2. Click **"Report a vulnerability"** (GitHub Private Vulnerability Reporting).

If that is unavailable, open a regular issue titled `SECURITY` **without
technical details** and ask for a private channel.

Please include, when possible:

- A description of the issue and its impact.
- Steps to reproduce.
- The affected file(s) / version.

You can expect an initial response within a reasonable time. Fixes for
confirmed issues are prioritized.

## Scope & threat model

SpoolScribe:

- Runs locally as a desktop app.
- Makes **outbound HTTPS GET requests only**, and only after explicit user
  consent (see [PRIVACY.md](../docs/PRIVACY.md)).
- Does **not** run a server, open ports, or accept inbound connections.
- Stores only a small local config file (consent + preferences).

Relevant concerns include: unsafe handling of downloaded data, path traversal
when writing output files, or command injection in the update pipeline. Reports
in these areas are especially welcome.

## Out of scope

- The security of third-party data sources (see ../docs/DATA_SOURCES.md).
- The Snapmaker U1 firmware fork and any RFID hardware.
