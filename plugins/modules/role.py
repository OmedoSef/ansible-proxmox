#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2026, Romain VOLPI <romain.volpi@omedo.net>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

DOCUMENTATION = r"""
---
module: role
short_description: Manage Proxmox VE roles
description:
  - Create, update, or delete a Proxmox VE role (C(/access/roles)).
  - Proxmox VE ships a set of built-in roles (for example C(Administrator) or
    C(PVEAdmin)) that cannot be modified or deleted; the API rejects such
    attempts with a clear error which this module simply surfaces.
version_added: "0.3.0"
author:
  - Romain VOLPI (@OmedoSef)
options:
  roleid:
    description:
      - Identifier of the role.
    type: str
    required: true
  state:
    description:
      - Whether the role should exist.
    type: str
    choices: [present, absent]
    default: present
  privs:
    description:
      - List of privileges granted by the role.
      - This replaces the full set of privileges; it is not additive. Only
        applied/compared when set; omit to leave the current privileges
        untouched on update. Set to an empty list to strip all privileges.
      - Ignored when creating a role without O(privs), the new role is
        created with no privileges.
    type: list
    elements: str
extends_documentation_fragment:
  - omedosef.proxmox.proxmox
"""

EXAMPLES = r"""
- name: Ensure a role exists with a specific set of privileges
  omedosef.proxmox.role:
    api_backend: local
    roleid: vm-operator
    privs:
      - VM.Audit
      - VM.PowerMgmt
  register: created

- name: Replace the privileges of an existing role
  omedosef.proxmox.role:
    api_backend: local
    roleid: vm-operator
    privs:
      - VM.Audit

- name: Remove a role
  omedosef.proxmox.role:
    api_backend: local
    roleid: vm-operator
    state: absent
"""

RETURN = r"""
role:
  description: >-
    Current state of the role as returned by the Proxmox VE API, or V(none)
    if it does not exist (or was just removed).
  returned: success
  type: dict
  sample:
    roleid: vm-operator
    privs: ["VM.Audit", "VM.PowerMgmt"]
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


COMPARABLE_FIELDS = ("privs",)


def _normalize(field, value):
    if field == "privs":
        return sorted(value) if value else []
    return value


def compute_changes(current, desired):
    """Return only the fields that differ, keyed by field name -> desired raw value."""
    changes = {}
    for field in COMPARABLE_FIELDS:
        if desired.get(field) is None:
            continue
        if _normalize(field, current.get(field)) != _normalize(field, desired[field]):
            changes[field] = desired[field]
    return changes


class ProxmoxRoleAnsible(ProxmoxAnsible):
    def get_role(self, roleid):
        try:
            privs = self.proxmox_api.access.roles(roleid).get()
        except ResourceException:
            # Proxmox reports a missing role as a generic 500 rather than a
            # 404, so any error here is treated as "does not exist". By this
            # point _connect() has already succeeded, so a genuine
            # auth/connectivity failure is unlikely to surface only now.
            return None
        return {"roleid": roleid, "privs": sorted(privs.keys())}

    def create_role(self, roleid, params):
        payload = self._prepare_payload(params)
        try:
            self.proxmox_api.access.roles.post(roleid=roleid, **payload)
        except ResourceException as exc:
            self.module.fail_json(msg=f"Failed to create role {roleid}: {exc}")

    def update_role(self, roleid, changes):
        payload = self._prepare_payload(changes)
        try:
            self.proxmox_api.access.roles(roleid).put(**payload)
        except ResourceException as exc:
            self.module.fail_json(msg=f"Failed to update role {roleid}: {exc}")

    def delete_role(self, roleid):
        try:
            self.proxmox_api.access.roles(roleid).delete()
        except ResourceException as exc:
            self.module.fail_json(msg=f"Failed to delete role {roleid}: {exc}")

    @classmethod
    def _prepare_payload(cls, params):
        payload = cls._filter_none_values(params)
        if "privs" in payload:
            payload["privs"] = ",".join(payload["privs"])
        return payload


def main():
    argument_spec = proxmox_auth_argument_spec()
    argument_spec.update(
        roleid=dict(type="str", required=True),
        state=dict(type="str", choices=["present", "absent"], default="present"),
        privs=dict(type="list", elements="str"),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=proxmox_required_if(),
        required_together=proxmox_required_together(),
    )

    proxmox = ProxmoxRoleAnsible(module)
    roleid = module.params["roleid"]
    state = module.params["state"]
    current = proxmox.get_role(roleid)

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, role=None)
        if not module.check_mode:
            proxmox.delete_role(roleid)
        module.exit_json(changed=True, role=None)

    desired = {field: module.params[field] for field in COMPARABLE_FIELDS}

    if current is None:
        if not module.check_mode:
            create_payload = dict(desired)
            proxmox.create_role(roleid, create_payload)
            current = proxmox.get_role(roleid)
        module.exit_json(changed=True, role=current)

    changes = compute_changes(current, desired)

    if not changes:
        module.exit_json(changed=False, role=current)

    if not module.check_mode:
        proxmox.update_role(roleid, changes)
        current = proxmox.get_role(roleid)

    module.exit_json(changed=True, role=current)


if __name__ == "__main__":
    main()
