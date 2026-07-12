# omedosef.proxmox

Ansible collection to manage [Proxmox VE](https://www.proxmox.com/en/proxmox-virtual-environment/overview)
through its API, plus a companion dynamic inventory plugin.

> **Status:** early scaffolding. Modules and the inventory plugin are not
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

## Content

| Type      | Name | Description |
|-----------|------|-------------|
| Inventory | _tbd_ | Dynamic inventory plugin for Proxmox VE (not implemented yet) |
| Module    | _tbd_ | QEMU VM management (not implemented yet) |
| Module    | _tbd_ | LXC container management (not implemented yet) |

## Roadmap

Development proceeds incrementally, one functional area at a time:

1. Dynamic inventory plugin
2. QEMU VM modules
3. LXC container modules
4. Node / cluster modules
5. User / permission modules

## Development

This repository ships a [dev container](.devcontainer/devcontainer.json)
with Python, `ansible-core`, `ansible-lint`, `proxmoxer` and related tooling
preinstalled. Open the repo in VS Code and reopen in container, or use the
[Dev Containers CLI](https://github.com/devcontainers/cli). The container
also installs the [pre-commit](.pre-commit-config.yaml) git hook automatically.

```bash
ansible-lint
ansible-test sanity --docker default

# outside the dev container:
pip install -r requirements-dev.txt
pre-commit install
pre-commit run --all-files
```

## License

GPL-3.0-only. See [LICENSE](LICENSE).
