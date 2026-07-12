#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2026, Romain VOLPI <romain.volpi@omedo.net>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

DOCUMENTATION = r"""
---
module: version_info
short_description: Retrieve Proxmox VE API version information
description:
  - Retrieve version information exposed by the Proxmox VE API C(/version)
    endpoint, such as the running Proxmox VE version and release.
version_added: "0.1.0"
author:
  - Romain VOLPI (@OmedoSef)
extends_documentation_fragment:
  - omedosef.proxmox.proxmox
"""

EXAMPLES = r"""
# Recommended when the play already targets the Proxmox node itself (e.g. a
# "hosts: proxmox_nodes" play with "become: true"): no api_host/api_user/
# credentials needed, Ansible's own connection does all the work.
- name: Get the Proxmox VE version by running pvesh locally on the node
  omedosef.proxmox.version_info:
    api_backend: local
  register: proxmox_version

# The examples below drive a remote Proxmox node from a play targeting
# something else (typically localhost), opening a dedicated connection to it.
- name: Get the Proxmox VE version using password authentication
  omedosef.proxmox.version_info:
    api_host: proxmox.example.com
    api_user: root@pam
    api_password: "{{ vault_proxmox_password }}"
    validate_certs: false
  register: proxmox_version

- name: Get the Proxmox VE version using an API token
  omedosef.proxmox.version_info:
    api_host: proxmox.example.com
    api_user: automation@pve
    api_token_id: ansible
    api_token_secret: "{{ vault_proxmox_token_secret }}"
  register: proxmox_version

- name: Get the Proxmox VE version over a dedicated SSH connection
  omedosef.proxmox.version_info:
    api_host: proxmox.example.com
    api_backend: ssh_paramiko
    api_user: root
    api_ssh_private_key_file: ~/.ssh/id_ed25519
    api_sudo: true
  register: proxmox_version

- name: Show the Proxmox VE version
  ansible.builtin.debug:
    msg: "Running Proxmox VE {{ proxmox_version.version.version }}"

# Set connection/auth options once instead of repeating them on every task.
# Any option still set directly on a task overrides the group default.
- module_defaults:
    group/omedosef.proxmox.proxmox:
      api_host: proxmox.example.com
      api_user: root@pam
      api_password: "{{ vault_proxmox_password }}"
  block:
    - name: Get the Proxmox VE version (uses the module_defaults above)
      omedosef.proxmox.version_info:
      register: proxmox_version

    - name: Same, but override just the host for this one task
      omedosef.proxmox.version_info:
        api_host: other-proxmox.example.com
      register: other_proxmox_version

# Every option also falls back to a PROXMOX_* environment variable (see
# extends_documentation_fragment above), handy for injecting credentials from
# a CI/CD runner without touching the playbook at all:
#   export PROXMOX_API_HOST=proxmox.example.com
#   export PROXMOX_API_USER=root@pam
#   export PROXMOX_API_PASSWORD=...
- name: Get the Proxmox VE version (host/user/password read from the environment)
  omedosef.proxmox.version_info:
  register: proxmox_version
"""

RETURN = r"""
version:
  description: Version information as returned by the Proxmox VE API.
  returned: success
  type: dict
  contains:
    version:
      description: Proxmox VE version string.
      type: str
      returned: success
      sample: "8.3.2"
    release:
      description: Release codename or number.
      type: str
      returned: success
      sample: "8.3"
    repoid:
      description: Short repository/git commit ID of the running build.
      type: str
      returned: success
      sample: "3e76eec21c4a14a3"
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.omedosef.proxmox.plugins.module_utils.proxmox import (
    ProxmoxAnsible,
    proxmox_auth_argument_spec,
    proxmox_required_if,
    proxmox_required_together,
)

try:
    from proxmoxer.core import ResourceException
except ImportError:
    # Handled by ProxmoxAnsible.__init__ via HAS_PROXMOXER; module_utils.basic
    # requires this import to fail gracefully rather than raise at import time.
    ResourceException = Exception


class ProxmoxVersionInfoAnsible(ProxmoxAnsible):
    def get_version(self):
        try:
            return self.proxmox_api.version.get()
        except ResourceException as exc:
            self.module.fail_json(
                msg=f"Failed to retrieve the Proxmox VE version: {exc}"
            )


def main():
    module = AnsibleModule(
        argument_spec=proxmox_auth_argument_spec(),
        supports_check_mode=True,
        required_if=proxmox_required_if(),
        required_together=proxmox_required_together(),
    )

    proxmox = ProxmoxVersionInfoAnsible(module)
    version = proxmox.get_version()

    module.exit_json(changed=False, version=version)


if __name__ == "__main__":
    main()
