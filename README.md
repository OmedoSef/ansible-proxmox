# omedosef.proxmox

Ansible collection to manage [Proxmox VE](https://www.proxmox.com/en/proxmox-virtual-environment/overview)
through its API, plus a companion dynamic inventory plugin.

> **Status:** early development. Most modules and the inventory plugin are not
> implemented yet — see [Roadmap](#roadmap).

## Requirements

- Ansible-core >= 2.16
- Python >= 3.10 on the control node
- [`proxmoxer`](https://pypi.org/project/proxmoxer/) and `requests` Python
  packages on the control node (see `requirements.txt`)
- A Proxmox VE API token or user credentials with sufficient privileges for
  the resources you manage

## Installation

```bash
ansible-galaxy collection install omedosef.proxmox
pip install -r ~/.ansible/collections/ansible_collections/omedosef/proxmox/requirements.txt
```

## Connecting to Proxmox

Every module in this collection shares the same `api_backend` option to reach
a Proxmox VE node:

- **`local`** (recommended when possible) — runs `pvesh` directly on the
  current host. No `api_host`, `api_user`, or credentials needed at all: use
  this when the play already targets the Proxmox node itself through
  Ansible's normal connection (inventory, `ansible_user`, SSH keys, `become`).
  Even though it never makes an HTTP call, the module still imports
  `proxmoxer`, so that package must be installed on **the Proxmox node's own
  Python interpreter** (not the control node) - see the `pip` pre-task in
  [playbooks/examples/version_info_local.yml](playbooks/examples/version_info_local.yml).
- **`https`** (default) — calls the REST API of a remote node directly, with
  `api_password` or an `api_token_id`/`api_token_secret` pair. Use this when
  driving a Proxmox node from a play targeting something else (typically
  `localhost`).
- **`ssh_paramiko`** — opens its own SSH connection to a remote node (separate
  from Ansible's own connection handling) and runs `pvesh` there. Mainly
  useful when you specifically want the module to manage its own SSH session
  rather than adding the node to your inventory; prefer `local` when you can.

For `https`/`ssh_paramiko`, set these options once instead of repeating them
on every task with a
[`module_defaults`](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_module_defaults.html)
group — every module in this collection belongs to
`group/omedosef.proxmox.proxmox` (declared in
[meta/runtime.yml](meta/runtime.yml)). Any option still set directly on a
task overrides the group default:

```yaml
- module_defaults:
    group/omedosef.proxmox.proxmox:
      api_host: proxmox.example.com
      api_user: root@pam
      api_password: "{{ vault_proxmox_password }}"
  block:
    - omedosef.proxmox.version_info: {}
      register: proxmox_version

    - omedosef.proxmox.version_info:
        api_host: other-proxmox.example.com   # overrides just this task
      register: other_proxmox_version
```

Every option also falls back to a `PROXMOX_*` environment variable
(`PROXMOX_API_HOST`, `PROXMOX_API_USER`, `PROXMOX_API_PASSWORD`,
`PROXMOX_API_TOKEN_ID`, `PROXMOX_API_TOKEN_SECRET`,
`PROXMOX_API_SSH_PRIVATE_KEY_FILE`, `PROXMOX_API_BACKEND`,
`PROXMOX_API_SUDO`, `PROXMOX_VALIDATE_CERTS`) — handy for injecting
credentials from a CI/CD runner's own secret store without touching the
playbook at all:

```bash
export PROXMOX_API_HOST=proxmox.example.com
export PROXMOX_API_USER=root@pam
export PROXMOX_API_PASSWORD=... # e.g. from your CI/CD secret store
ansible-playbook site.yml
```

Precedence (highest to lowest): the task's own arguments, then
`module_defaults`, then the environment variable, then the option's default.

## Content

| Type      | Name | Description |
|-----------|------|-------------|
| Module    | [version_info](plugins/modules/version_info.py) | Retrieve Proxmox VE API version information |
| Module    | _tbd_ | QEMU VM management (not implemented yet) |
| Module    | _tbd_ | LXC container management (not implemented yet) |
| Inventory | _tbd_ | Dynamic inventory plugin for Proxmox VE (not implemented yet) |

## Roadmap

Development proceeds incrementally, one functional area at a time:

1. ~~First module (`version_info`) to validate the API auth pattern~~
2. QEMU VM modules
3. LXC container modules
4. Node / cluster modules
5. User / permission modules
6. Dynamic inventory plugin

## Development

This repository ships a [dev container](.devcontainer/devcontainer.json)
with Python, `ansible-core`, `ansible-lint`, `proxmoxer` and related tooling
preinstalled. Open the repo in VS Code and reopen in container, or use the
[Dev Containers CLI](https://github.com/devcontainers/cli). The workspace is
bind-mounted directly at the path that `ansible-test` and the Ansible
collection loader expect
(`~/.ansible/collections/ansible_collections/omedosef/proxmox`), so FQCN
imports (`ansible_collections.omedosef.proxmox...`) resolve without any extra
setup. The container also installs the
[pre-commit](.pre-commit-config.yaml) git hook automatically
(`pre-commit run --all-files` for lint/formatting).

Outside the dev container, `pip install -r requirements-dev.txt` gets you the
same tooling, but FQCN-based imports/tests will only work if this checkout is
itself placed at (or symlinked to) that same
`ansible_collections/omedosef/proxmox` path.

## Testing

All commands below are meant to be run **inside the dev container**, from the
collection root (the integrated terminal already starts there).

### Unit tests

Unit tests live under `tests/unit/`, mirroring the `plugins/` layout
(`tests/unit/plugins/modules/test_<module>.py`,
`tests/unit/plugins/module_utils/test_<name>.py`). They never talk to a real
Proxmox server: `proxmoxer.ProxmoxAPI` is mocked with `pytest-mock`, and
`AnsibleModule` is replaced by a small `FakeModule` stub (see the existing
tests) that captures `exit_json`/`fail_json` calls instead of exiting the
process.

```bash
# via ansible-test (matches what CI/sanity expects, slower)
ansible-test units --python 3.14

# via pytest directly (faster feedback loop while writing a test)
pytest tests/unit -v
pytest tests/unit/plugins/modules/test_version_info.py -v   # single file
```

When adding a new module, add its test next to the existing ones, reusing the
`FakeModule` pattern to assert on `module.exited["..."]` /
`module.failed["msg"]` rather than asserting on real process exit codes.

### Integration tests

Unit tests mock the Proxmox API entirely, so they can't catch things like a
wrong endpoint path or a response shape that changed between Proxmox VE
versions. Integration tests under `tests/integration/targets/` run real
modules against a **real Proxmox VE instance** to cover that gap. Each
supported authentication method has its own target, since a single module
call only ever exercises one of them:

- `version_info` — password authentication over the REST API
  (`proxmox_api_user` + `proxmox_api_password`, always required)
- `version_info_token_auth` — API token authentication over the REST API
  (`proxmox_api_token_id` + `proxmox_api_token_secret`); skipped automatically
  if those aren't set
- `version_info_ssh_auth` — SSH backend (`api_backend: ssh_paramiko`, running
  `pvesh` remotely instead of calling the REST API), via `proxmox_ssh_user`;
  skipped automatically if that isn't set
- `version_info_local_auth` — `api_backend: local`, the recommended pattern
  (see [Connecting to Proxmox](#connecting-to-proxmox)). Since this only
  makes sense when the *task itself* runs on the Proxmox node, this target
  `delegate_to`s `proxmox_local_host` over SSH instead of using
  `ansible-test`'s default local target; skipped automatically if that
  variable isn't set

All four are tagged `unsupported` in their `aliases` file (`ansible-test`
only recognizes a fixed list of built-in `cloud/*` providers for automated
credential handling, and Proxmox isn't one of them) so they're excluded from
a bare `ansible-test integration` run and require
`--allow-unsupported` to run explicitly, as shown below.

Don't have a Proxmox VE host to spare for testing?
[OmedoSef/ansible-proxmox-qemu-install](https://github.com/OmedoSef/ansible-proxmox-qemu-install)
provisions a disposable one inside a local QEMU/KVM VM (requires nested
virtualization) and ships a `destroy.yml` playbook to tear it down afterwards.

```bash
cp tests/integration/integration_config.yml.template \
   tests/integration/integration_config.yml
# edit tests/integration/integration_config.yml with your Proxmox VE
# host/credentials (this file is gitignored, never commit real credentials)

ansible-test integration version_info version_info_token_auth version_info_ssh_auth \
  version_info_local_auth --python 3.14 --allow-unsupported
```

These tests are **not** run in CI (no network access to a real Proxmox host
from GitHub Actions runners) — run them manually, e.g. before cutting a
release, against a throwaway host.

### Sanity tests

`ansible-test sanity` runs Ansible's own static checks (pylint, docs
validation, yamllint, license headers, etc.) against the collection:

```bash
ansible-test sanity --python 3.14
```

### Lint

```bash
ansible-lint
pre-commit run --all-files
```

## Releasing

Releases are cut in two steps, split across two workflows because a git tag
is immutable and can't be amended after the fact:

1. **[Prepare Release](.github/workflows/prepare-release.yml)** (manual —
   Actions tab → "Prepare Release" → Run workflow, enter the new version,
   e.g. `0.2.0`). Bumps `galaxy.yml`, turns the accumulated
   `changelogs/fragments/*.yml` into a `CHANGELOG.rst` entry via
   `antsibull-changelog release`, and opens a PR. Review the generated
   changelog, then merge it.
2. **Tag the merge commit**: `git tag v0.2.0 <commit> && git push origin v0.2.0`
   (the `v` prefix is required; the version after it must match `galaxy.yml`
   exactly). This triggers **[Release](.github/workflows/release.yml)**:
   runs the full CI suite (lint, units, sanity), builds the collection,
   creates a GitHub release (notes taken from the matching `CHANGELOG.rst`
   section, tarball attached), then - after manual approval - publishes to
   Ansible Galaxy.

One-time repository setup required for this to work:

- A `galaxy-publish` environment (Settings → Environments) with at least one
  required reviewer, so a human confirms the one irreversible step (Galaxy
  publishes can't be deleted or overwritten) even though everything before
  it is fully automated. Create this first.
- A `GALAXY_API_KEY` secret **scoped to that `galaxy-publish` environment**
  (Settings → Environments → galaxy-publish → Environment secrets - not the
  repository-level "Secrets and variables → Actions" page), from your
  [Galaxy profile preferences](https://galaxy.ansible.com/ui/me/preferences)
  now that your account is linked to GitHub. Scoping it to the environment
  means only the `publish` job can ever see it, and GitHub won't inject it
  until the required reviewer approves.
- "Allow GitHub Actions to create pull requests" enabled (Settings → Actions
  → General), needed by `prepare-release.yml`.

## License

GPL-3.0-only. See [LICENSE](LICENSE).
