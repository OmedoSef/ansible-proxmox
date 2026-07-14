# -*- coding: utf-8 -*-
# Copyright (c) 2026, Romain VOLPI <romain.volpi@omedo.net>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations


class ModuleDocFragment:
    DOCUMENTATION = r"""
options:
  api_host:
    description:
      - Hostname or IP address of the Proxmox VE endpoint.
      - Required for O(api_backend=https) and O(api_backend=ssh_paramiko).
        Not used by O(api_backend=local), which runs against the current
        host instead.
      - Falls back to the E(PROXMOX_API_HOST) environment variable.
    type: str
  api_port:
    description:
      - TCP port of the Proxmox VE endpoint.
      - Defaults to V(8006) for the O(api_backend=https) backend, or V(22) for
        O(api_backend=ssh_paramiko). Not used by O(api_backend=local).
      - Falls back to the E(PROXMOX_API_PORT) environment variable.
    type: int
  api_backend:
    description:
      - How to reach the Proxmox VE node.
      - V(https) talks to the REST API of a remote node directly.
      - V(ssh_paramiko) connects to a remote node over SSH (pure-Python, via
        C(paramiko)) and runs C(pvesh) commands there instead. This backend
        opens its own SSH connection, independent from Ansible's - see the
        notes below before reaching for it.
      - V(local) runs C(pvesh) directly on the current host, with no network
        connection or credentials at all. Use this when the play already
        targets the Proxmox node itself through Ansible's own connection
        (normal inventory, C(ansible_user), SSH keys, C(become), etc.)
        instead of reaching a remote node from the control node. Even though
        it makes no HTTP call, this backend still imports the C(proxmoxer)
        Python package, so it must be installed on that node's own Python
        interpreter (not the control node).
      - Falls back to the E(PROXMOX_API_BACKEND) environment variable.
    type: str
    choices: [https, ssh_paramiko, local]
    default: local
  api_user:
    description:
      - Proxmox VE user, in the C(user@realm) format (for example C(root@pam)).
      - Required for O(api_backend=https) and O(api_backend=ssh_paramiko).
        Not used by O(api_backend=local).
      - Falls back to the E(PROXMOX_API_USER) environment variable.
    type: str
  api_password:
    description:
      - Password of O(api_user).
      - For O(api_backend=https), required if O(api_token_id) and
        O(api_token_secret) are not set.
      - For O(api_backend=ssh_paramiko), optional; when unset, authentication
        falls back to an SSH agent or the control node's default SSH keys.
      - Not used by O(api_backend=local).
      - Falls back to the E(PROXMOX_API_PASSWORD) environment variable.
    type: str
  api_token_id:
    description:
      - API token ID belonging to O(api_user) (without the C(user@realm!) prefix).
      - Only used by O(api_backend=https). Required together with
        O(api_token_secret).
      - Falls back to the E(PROXMOX_API_TOKEN_ID) environment variable.
    type: str
  api_token_secret:
    description:
      - Secret value of the API token identified by O(api_token_id).
      - Only used by O(api_backend=https).
      - Falls back to the E(PROXMOX_API_TOKEN_SECRET) environment variable.
    type: str
  api_ssh_private_key_file:
    description:
      - Path to a private key file used to authenticate O(api_user) over SSH.
      - Only used by O(api_backend=ssh_paramiko).
      - Falls back to the E(PROXMOX_API_SSH_PRIVATE_KEY_FILE) environment
        variable.
    type: path
  api_sudo:
    description:
      - Prefix every C(pvesh) command with C(sudo). This is Proxmox VE's
        equivalent of Ansible's C(become).
      - Only used by O(api_backend=ssh_paramiko) and O(api_backend=local).
        For O(api_backend=local), this is usually unnecessary if the play
        already uses Ansible's own C(become) to run as C(root).
      - Falls back to the E(PROXMOX_API_SUDO) environment variable.
    type: bool
    default: false
  validate_certs:
    description:
      - Whether to validate the target node's SSL certificate.
      - Set to V(false) when the Proxmox VE API uses a self-signed certificate.
      - Only used by O(api_backend=https).
      - Falls back to the E(PROXMOX_VALIDATE_CERTS) environment variable.
    type: bool
    default: true
notes:
  - Prefer O(api_backend=local) when the play already targets the Proxmox
    node itself (SSH connection handled by Ansible as usual) - it needs no
    O(api_host), O(api_user), or credentials of any kind. Reach for
    O(api_backend=https) or O(api_backend=ssh_paramiko) when driving a
    Proxmox node from a play targeting something else (typically
    C(localhost)), since those open their own connection to it.
  - For O(api_backend=https), authenticate either with O(api_password), or
    with O(api_token_id) and O(api_token_secret). API tokens are recommended
    for automation.
  - For O(api_backend=ssh_paramiko), authenticate with O(api_password),
    O(api_ssh_private_key_file), an SSH agent, or the control node's default
    SSH keys (tried in that order).
  - Every option here can also be set once for several tasks via a
    C(module_defaults) C(group/omedosef.proxmox.proxmox) block, or globally
    via its C(PROXMOX_*) environment variable. From highest to lowest
    precedence - the task's own arguments, then C(module_defaults), then the
    environment variable, then the option's default.
"""
