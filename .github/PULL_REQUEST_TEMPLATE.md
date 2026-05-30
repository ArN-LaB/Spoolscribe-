## Summary

<!-- What does this PR change and why? -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation
- [ ] Refactor / chore

## Checklist

- [ ] Logic lives in `core.py` where it can be shared by CLI and GUI.
- [ ] No new **un-consented** network access was introduced
      (all network stays behind the consent gate — see ../docs/PRIVACY.md).
- [ ] Any new data source is documented in `docs/DATA_SOURCES.md` **and** added to
      `core.NETWORK_SOURCES`, with a compatible license.
- [ ] Any new trademarked asset is noted in `docs/TRADEMARKS.md`.
- [ ] I smoke-tested the CLI and/or GUI.

## Notes for reviewers

<!-- Anything else worth knowing. -->
