#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2026, Romain VOLPI <romain.volpi@omedo.net>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

DOCUMENTATION = r"""
---
module: acl
short_description: Manage Proxmox VE ACL entries
description:
  - Grant or revoke Proxmox VE roles for a user, group, or token on a given
    path (C(/access/acl)).
  - Unlike C(role) privileges or C(user) group membership, an ACL entry is
    not a single resource identified by one ID - the same
    path/user/group/token combination can hold several independent role
    grants at once. This module therefore only ever touches the exact roles
    listed in O(roles); any other role already granted on the same
    O(path)/O(type)/O(ugid) is left untouched.
version_added: "0.3.0"
author:
  - Romain VOLPI (@OmedoSef)
options:
  path:
    description:
      - The ACL path the roles apply to (for example C(/), C(/vms/100), or
        C(/pool/mypool)).
    type: str
    required: true
  type:
    description:
      - Kind of entity O(ugid) refers to.
    type: str
    choices: [user, group, token]
    required: true
  ugid:
    description:
      - Identifier of the user, group, or token (depending on O(type)) the
        roles are granted to or revoked from. For example C(jdoe@pve) for a
        user, C(admins) for a group, or C(jdoe@pve!ansible) for a token.
    type: str
    required: true
  roles:
    description:
      - Roles to grant (O(state=present)) or revoke (O(state=absent)) for
        O(ugid) on O(path).
      - Only the listed roles are touched; any other role already assigned
        to the same O(path)/O(type)/O(ugid) combination is left as-is.
    type: list
    elements: str
    required: true
  propagate:
    description:
      - Whether the granted roles propagate to sub-paths.
      - Only meaningful for O(state=present); ignored for O(state=absent).
    type: bool
    default: true
  state:
    description:
      - Whether O(roles) should be granted or revoked.
    type: str
    choices: [present, absent]
    default: present
extends_documentation_fragment:
  - omedosef.proxmox.proxmox
"""

EXAMPLES = r"""
- name: Grant a role to a user on a VM path
  omedosef.proxmox.acl:
    api_backend: local
    path: /vms/100
    type: user
    ugid: jdoe@pve
    roles:
      - PVEVMUser
  register: granted

- name: Grant a role without propagating it to sub-paths
  omedosef.proxmox.acl:
    api_backend: local
    path: /
    type: group
    ugid: admins
    roles:
      - PVEAuditor
    propagate: false

- name: Revoke a role, leaving any other role on the same path/user untouched
  omedosef.proxmox.acl:
    api_backend: local
    path: /vms/100
    type: user
    ugid: jdoe@pve
    roles:
      - PVEVMUser
    state: absent
"""

RETURN = r"""
acl:
  description: >-
    Current roles granted to O(ugid) on O(path), as returned by the Proxmox
    VE API.
  returned: success
  type: dict
  contains:
    path:
      description: The ACL path.
      type: str
      returned: success
    type:
      description: Kind of entity O(ugid) refers to.
      type: str
      returned: success
    ugid:
      description: Identifier of the user, group, or token.
      type: str
      returned: success
    roles:
      description: Roles currently granted to O(ugid) on O(path).
      type: list
      elements: dict
      returned: success
      contains:
        roleid:
          description: The granted role.
          type: str
          returned: success
        propagate:
          description: Whether the role propagates to sub-paths.
          type: bool
          returned: success
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


UGID_PARAM_BY_TYPE = {"user": "users", "group": "groups", "token": "tokens"}


def _format_acl(path, ugid_type, ugid, current_roles):
    return {
        "path": path,
        "type": ugid_type,
        "ugid": ugid,
        "roles": [
            {"roleid": roleid, "propagate": propagate}
            for roleid, propagate in sorted(current_roles.items())
        ],
    }


class ProxmoxAclAnsible(ProxmoxAnsible):
    def get_entries(self, path, ugid_type, ugid):
        try:
            acl = self.proxmox_api.access.acl.get()
        except ResourceException as exc:
            self.module.fail_json(msg=f"Failed to list ACL entries: {exc}")
        return {
            entry["roleid"]: bool(int(entry["propagate"]))
            for entry in acl
            if entry["path"] == path
            and entry["type"] == ugid_type
            and entry["ugid"] == ugid
        }

    def grant_roles(self, path, ugid_type, ugid, roles, propagate):
        payload = {
            "path": path,
            "roles": ",".join(sorted(roles)),
            "propagate": int(propagate),
            UGID_PARAM_BY_TYPE[ugid_type]: ugid,
        }
        try:
            self.proxmox_api.access.acl.put(**payload)
        except ResourceException as exc:
            self.module.fail_json(
                msg=f"Failed to grant role(s) {', '.join(sorted(roles))} to "
                f"{ugid_type} {ugid} on path {path}: {exc}"
            )

    def revoke_roles(self, path, ugid_type, ugid, roles):
        payload = {
            "path": path,
            "roles": ",".join(sorted(roles)),
            "delete": 1,
            UGID_PARAM_BY_TYPE[ugid_type]: ugid,
        }
        try:
            self.proxmox_api.access.acl.put(**payload)
        except ResourceException as exc:
            self.module.fail_json(
                msg=f"Failed to revoke role(s) {', '.join(sorted(roles))} from "
                f"{ugid_type} {ugid} on path {path}: {exc}"
            )


def main():
    argument_spec = proxmox_auth_argument_spec()
    argument_spec.update(
        path=dict(type="str", required=True),
        type=dict(type="str", choices=["user", "group", "token"], required=True),
        ugid=dict(type="str", required=True),
        roles=dict(type="list", elements="str", required=True),
        propagate=dict(type="bool", default=True),
        state=dict(type="str", choices=["present", "absent"], default="present"),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=proxmox_required_if(),
        required_together=proxmox_required_together(),
    )

    proxmox = ProxmoxAclAnsible(module)
    path = module.params["path"]
    ugid_type = module.params["type"]
    ugid = module.params["ugid"]
    roles = set(module.params["roles"])
    state = module.params["state"]

    current = proxmox.get_entries(path, ugid_type, ugid)

    if state == "absent":
        to_revoke = sorted(role for role in roles if role in current)
        if to_revoke:
            if not module.check_mode:
                proxmox.revoke_roles(path, ugid_type, ugid, to_revoke)
                current = proxmox.get_entries(path, ugid_type, ugid)
            module.exit_json(
                changed=True, acl=_format_acl(path, ugid_type, ugid, current)
            )
        module.exit_json(changed=False, acl=_format_acl(path, ugid_type, ugid, current))

    propagate = module.params["propagate"]
    to_grant = sorted(role for role in roles if current.get(role) != propagate)

    if to_grant:
        if not module.check_mode:
            proxmox.grant_roles(path, ugid_type, ugid, to_grant, propagate)
            current = proxmox.get_entries(path, ugid_type, ugid)
        module.exit_json(changed=True, acl=_format_acl(path, ugid_type, ugid, current))

    module.exit_json(changed=False, acl=_format_acl(path, ugid_type, ugid, current))


if __name__ == "__main__":
    main()
