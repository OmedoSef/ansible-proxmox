# Contributing to omedosef.proxmox

Thanks for considering a contribution. This collection follows standard
Ansible/Galaxy conventions; this doc covers the project-specific parts.

## Getting started

Use the [dev container](README.md#development) — it ships Python,
`ansible-core`, `ansible-lint`, `proxmoxer` and `pre-commit` preinstalled,
and mounts the repo at the exact path `ansible-test` expects. Outside the
container, `pip install -r requirements-dev.txt` gets you the same tooling,
but FQCN-based imports/tests only work if the checkout sits at (or is
symlinked to) `ansible_collections/omedosef/proxmox`.

## Branching and pull requests

- `main` is protected: all changes land via a pull request, never a direct
  push.
- Branch off `main`, name the branch after what it does (`fix/...`,
  `feature/...`), and open a PR back into `main`.
- CI (lint, unit tests, sanity tests — see [Testing](README.md#testing))
  runs automatically on every PR and must pass before merging.
- Keep PRs scoped to one change. Large, unrelated changes bundled together
  are harder to review and to write a changelog fragment for.

## Commit messages

This repo follows [Conventional Commits](https://www.conventionalcommits.org/)
(`feat:`, `fix:`, `chore:`, `docs:`, `test:`, ...) for the subject line, with
the body explaining *why* rather than restating the diff. Match the existing
`git log` style.

## Language

**All documentation, code comments, and commit messages must be in
English** — module `DOCUMENTATION`/`EXAMPLES`/`RETURN` blocks, docstrings,
README/CONTRIBUTING updates, changelog fragments, everything. This project
is intended for public/international reuse.

## Changelog fragments

User-facing changes need a fragment in `changelogs/fragments/` (consumed by
`antsibull-changelog` at release time — see
[changelogs/config.yaml](changelogs/config.yaml)). Create a YAML file there
named after the change (e.g. `changelogs/fragments/fix-ssh-port-default.yml`):

```yaml
---
bugfixes:
  - version_info - fixed the default SSH port for the ssh_paramiko backend (https://github.com/OmedoSef/ansible-proxmox/pull/123).
```

Common top-level keys: `bugfixes`, `minor_changes`, `breaking_changes`,
`deprecated_features`, `removed_features`, `security_fixes`. **New
modules/plugins don't need a fragment** — `antsibull-changelog` picks them up
automatically from their `DOCUMENTATION` at release time. Skip the fragment
for changes with no user-visible effect (CI, devcontainer, internal
refactors).

## Adding or changing a module

- Every module shares the connection/auth options documented in
  [plugins/doc_fragments/proxmox.py](plugins/doc_fragments/proxmox.py)
  (`extends_documentation_fragment: - omedosef.proxmox.proxmox`) and the
  three `api_backend` values (`https`, `ssh_paramiko`, `local` — see
  [Connecting to Proxmox](README.md#connecting-to-proxmox) for when to use
  which). Reuse
  [plugins/module_utils/proxmox.py](plugins/module_utils/proxmox.py)'s
  `ProxmoxAnsible` base class rather than reimplementing connection logic.
- `DOCUMENTATION`, `EXAMPLES`, and `RETURN` are required and must be valid
  RST-safe YAML — watch for a bare `: ` inside a plain (unquoted) multi-line
  scalar, which breaks the parser in a way that's easy to miss locally (seen
  more than once in this repo's history).
- Add unit tests under `tests/unit/plugins/modules/test_<module>.py`, mocking
  `proxmoxer.ProxmoxAPI` (see existing tests for the `FakeModule` pattern
  used instead of a real `AnsibleModule`).
- Consider an integration test target under `tests/integration/targets/` if
  the change is meaningfully different to exercise against a real Proxmox VE
  instance (see [Integration tests](README.md#testing)). These aren't run in
  CI (no network access to a real Proxmox host) — expect the maintainer to
  run them manually before a release.
- Run `ansible-lint` and `ansible-test sanity` locally before opening the PR;
  both run in CI too, but the sanity venv setup is slow — catching issues
  locally first saves round-trips.

## Reporting issues

Bugs and feature requests go on
[GitHub Issues](https://github.com/OmedoSef/ansible-proxmox/issues) — not
Ansible Galaxy. Include the collection version, Ansible/Python versions, and
(for bugs) the `api_backend` in use.
