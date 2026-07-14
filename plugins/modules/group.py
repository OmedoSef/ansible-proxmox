#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2026, Romain VOLPI <romain.volpi@omedo.net>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)


from __future__ import annotations

DOCUMENTATION = r"""
---
module: group
short_description: Manage Proxmox VE groups
description:
  - Create, update, or delete a Proxmox VE group (C(/access/groups)).
version_added: "0.3.0"
author:
  - Romain VOLPI (@OmedoSef)
options:
  groupid:
    description:
      - Full group ID, in the C(group) format.
    type: str
    required: true
  state:
    description:
      - Whether the group should exist.
    type: str
    choices: [present, absent]
    default: present
  comment:
    description:
      - Free-form description of the group.
      - Only applied/compared when set; omit to leave the current value
        untouched on update.
    type: str
extends_documentation_fragment:
  - omedosef.proxmox.proxmox
"""

EXAMPLES = r"""
- name: Ensure a group exists
  omedosef.proxmox.group:
    groupid: admins
  register: jdoe

- name: Update just the comment leaving everything else untouched
  omedosef.proxmox.group:
    groupid: admins
    comment: "Admins group"

- name: Remove a group
  omedosef.proxmox.group:
    groupid: admins
    state: absent
"""

RETURN = r"""
group:
  description: >-
    Current state of the group as returned by the Proxmox VE API, or V(none)
    if it does not exist (or was just removed).
  returned: success
  type: dict
  sample:
    groupid: admins
    comment: "Admins group"
    members:
     - pve-jdoe
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


COMPARABLE_FIELDS = ("comment",)


def compute_changes(current, desired):
    return ProxmoxAnsible.compute_changes(current, desired, COMPARABLE_FIELDS)


class ProxmoxGroupAnsible(ProxmoxAnsible):
    def get_group(self, groupid):
        try:
            group = self.proxmox_api.access.groups(groupid).get()
        except ResourceException:
            # Proxmox reports a missing group as a generic 500 rather than a
            # 404, so any error here is treated as "does not exist". By this
            # point _connect() has already succeeded, so a genuine
            # auth/connectivity failure is unlikely to surface only now.
            return None
        group["groupid"] = groupid
        return group

    def create_group(self, groupid, params):
        payload = self._filter_none_values(params)
        try:
            self.proxmox_api.access.groups.post(groupid=groupid, **payload)
        except ResourceException as exc:
            self.module.fail_json(msg=f"Failed to create group {groupid}: {exc}")

    def update_group(self, groupid, changes):
        payload = self._filter_none_values(changes)
        try:
            self.proxmox_api.access.groups(groupid).put(**payload)
        except ResourceException as exc:
            self.module.fail_json(msg=f"Failed to update group {groupid}: {exc}")

    def delete_group(self, groupid):
        try:
            self.proxmox_api.access.groups(groupid).delete()
        except ResourceException as exc:
            self.module.fail_json(msg=f"Failed to delete group {groupid}: {exc}")


def main():
    argument_spec = proxmox_auth_argument_spec()
    argument_spec.update(
        groupid=dict(type="str", required=True),
        state=dict(type="str", choices=["present", "absent"], default="present"),
        comment=dict(type="str"),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=proxmox_required_if(),
        required_together=proxmox_required_together(),
    )

    proxmox = ProxmoxGroupAnsible(module)
    groupid = module.params["groupid"]
    state = module.params["state"]
    current = proxmox.get_group(groupid)

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, group=None)
        if not module.check_mode:
            proxmox.delete_group(groupid)
        module.exit_json(changed=True, group=None)

    desired = {field: module.params[field] for field in COMPARABLE_FIELDS}

    if current is None:
        if not module.check_mode:
            create_payload = dict(desired)
            proxmox.create_group(groupid, create_payload)
            current = proxmox.get_group(groupid)
        module.exit_json(changed=True, group=current)

    changes = compute_changes(current, desired)

    if not changes:
        module.exit_json(changed=False, group=current)

    if not module.check_mode:
        if changes:
            proxmox.update_group(groupid, changes)
        current = proxmox.get_group(groupid)

    module.exit_json(changed=True, group=current)


if __name__ == "__main__":
    main()
