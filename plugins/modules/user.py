#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2026, Romain VOLPI <romain.volpi@omedo.net>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

DOCUMENTATION = r"""
---
module: user
short_description: Manage Proxmox VE users
description:
  - Create, update, or delete a Proxmox VE user (C(/access/users)).
version_added: "0.2.0"
author:
  - Romain VOLPI (@OmedoSef)
options:
  userid:
    description:
      - Full user ID, in the C(user@realm) format (for example C(jdoe@pve) or
        C(jdoe@pam)).
    type: str
    required: true
  state:
    description:
      - Whether the user should exist.
    type: str
    choices: [present, absent]
    default: present
  comment:
    description:
      - Free-form description of the user.
      - Only applied/compared when set; omit to leave the current value
        untouched on update.
    type: str
  email:
    description:
      - Email address of the user.
      - Only applied/compared when set; omit to leave the current value
        untouched on update.
    type: str
  enable:
    description:
      - Whether the user account is enabled.
      - Only applied/compared when set; omit to leave the current value
        untouched on update.
    type: bool
  expire:
    description:
      - Account expiration date, as a Unix timestamp. V(0) means the account
        never expires.
      - Only applied/compared when set; omit to leave the current value
        untouched on update.
    type: int
  firstname:
    description:
      - First name of the user.
      - Only applied/compared when set; omit to leave the current value
        untouched on update.
    type: str
  lastname:
    description:
      - Last name of the user.
      - Only applied/compared when set; omit to leave the current value
        untouched on update.
    type: str
  groups:
    description:
      - List of groups the user belongs to. This replaces the full group
        membership; it is not additive.
      - Only applied/compared when set; omit to leave current group
        membership untouched on update. Set to an empty list to remove the
        user from all groups.
    type: list
    elements: str
  password:
    description:
      - Password for the user. Only meaningful for users in the C(pve)
        realm; other realms (C(pam), LDAP, AD, ...) authenticate externally
        and ignore this.
      - Proxmox never returns the current password, so this module cannot
        detect drift in it. It is always applied when creating a new user.
        For an existing user, it is only applied when
        O(update_password=always).
    type: str
  update_password:
    description:
      - Controls whether O(password) is (re)applied to an already-existing
        user.
      - V(on_create) only sets O(password) when the user is being created.
      - V(always) also sets it on every run where O(password) is provided,
        even though this module can never know whether it actually changed
        (see O(password)).
    type: str
    choices: [on_create, always]
    default: on_create
extends_documentation_fragment:
  - omedosef.proxmox.proxmox
"""

EXAMPLES = r"""
- name: Ensure a user exists
  omedosef.proxmox.user:
    api_backend: local
    userid: jdoe@pve
    password: "{{ vault_jdoe_password }}"
    firstname: Jane
    lastname: Doe
    email: jdoe@example.com
    groups:
      - admins
  register: jdoe

- name: Update just the comment and disable the account, leaving everything else untouched
  omedosef.proxmox.user:
    api_backend: local
    userid: jdoe@pve
    comment: "Temporarily disabled pending review"
    enable: false

- name: Reset the password of an existing user
  omedosef.proxmox.user:
    api_backend: local
    userid: jdoe@pve
    password: "{{ vault_jdoe_new_password }}"
    update_password: always

- name: Remove a user
  omedosef.proxmox.user:
    api_backend: local
    userid: jdoe@pve
    state: absent
"""

RETURN = r"""
user:
  description: >-
    Current state of the user as returned by the Proxmox VE API, or V(none)
    if it does not exist (or was just removed).
  returned: success
  type: dict
  sample:
    userid: jdoe@pve
    comment: "Jane Doe"
    email: jdoe@example.com
    enable: 1
    expire: 0
    firstname: Jane
    lastname: Doe
    groups: ["admins"]
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


COMPARABLE_FIELDS = (
    "comment",
    "email",
    "enable",
    "expire",
    "firstname",
    "lastname",
    "groups",
)


def _as_group_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return list(value)
    return [group for group in value.split(",") if group]


def _normalize(field, value):
    if field == "enable":
        return bool(int(value)) if value is not None else True
    if field == "expire":
        return int(value) if value is not None else 0
    if field == "groups":
        return sorted(_as_group_list(value))
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


class ProxmoxUserAnsible(ProxmoxAnsible):
    def get_user(self, userid):
        try:
            user = self.proxmox_api.access.users(userid).get()
        except ResourceException:
            # Proxmox reports a missing user as a generic 500 rather than a
            # 404, so any error here is treated as "does not exist". By this
            # point _connect() has already succeeded, so a genuine
            # auth/connectivity failure is unlikely to surface only now.
            return None
        user["userid"] = userid
        return user

    def create_user(self, userid, params):
        payload = self._prepare_payload(params)
        try:
            self.proxmox_api.access.users.post(userid=userid, **payload)
        except ResourceException as exc:
            self.module.fail_json(msg=f"Failed to create user {userid}: {exc}")

    def update_user(self, userid, changes):
        payload = self._prepare_payload(changes)
        try:
            self.proxmox_api.access.users(userid).put(**payload)
        except ResourceException as exc:
            self.module.fail_json(msg=f"Failed to update user {userid}: {exc}")

    def set_password(self, userid, password):
        try:
            self.proxmox_api.access.password.put(userid=userid, password=password)
        except ResourceException as exc:
            self.module.fail_json(
                msg=f"Failed to set the password for user {userid}: {exc}"
            )

    def delete_user(self, userid):
        try:
            self.proxmox_api.access.users(userid).delete()
        except ResourceException as exc:
            self.module.fail_json(msg=f"Failed to delete user {userid}: {exc}")

    @classmethod
    def _prepare_payload(cls, params):
        payload = cls._filter_none_values(params)
        if "groups" in payload:
            payload["groups"] = ",".join(payload["groups"])
        return payload


def main():
    argument_spec = proxmox_auth_argument_spec()
    argument_spec.update(
        userid=dict(type="str", required=True),
        state=dict(type="str", choices=["present", "absent"], default="present"),
        comment=dict(type="str"),
        email=dict(type="str"),
        enable=dict(type="bool"),
        expire=dict(type="int"),
        firstname=dict(type="str"),
        lastname=dict(type="str"),
        groups=dict(type="list", elements="str"),
        password=dict(type="str", no_log=True),
        update_password=dict(
            type="str",
            choices=["on_create", "always"],
            default="on_create",
            no_log=False,
        ),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=proxmox_required_if(),
        required_together=proxmox_required_together(),
    )

    proxmox = ProxmoxUserAnsible(module)
    userid = module.params["userid"]
    state = module.params["state"]
    current = proxmox.get_user(userid)

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, user=None)
        if not module.check_mode:
            proxmox.delete_user(userid)
        module.exit_json(changed=True, user=None)

    desired = {field: module.params[field] for field in COMPARABLE_FIELDS}

    if current is None:
        if not module.check_mode:
            create_payload = dict(desired)
            create_payload["password"] = module.params["password"]
            proxmox.create_user(userid, create_payload)
            current = proxmox.get_user(userid)
        module.exit_json(changed=True, user=current)

    changes = compute_changes(current, desired)
    password_changing = (
        module.params["password"] is not None
        and module.params["update_password"] == "always"
    )

    if not changes and not password_changing:
        module.exit_json(changed=False, user=current)

    if not module.check_mode:
        if changes:
            proxmox.update_user(userid, changes)
        if password_changing:
            proxmox.set_password(userid, module.params["password"])
        current = proxmox.get_user(userid)

    module.exit_json(changed=True, user=current)


if __name__ == "__main__":
    main()
