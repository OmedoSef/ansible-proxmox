#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2026, Romain VOLPI <romain.volpi@omedo.net>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

DOCUMENTATION = r"""
---
module: user_token
short_description: Manage Proxmox VE API tokens for a user
description:
  - Create, update, or delete a Proxmox VE API token belonging to a user
    (C(/access/users/{userid}/token/{tokenid})).
version_added: "0.3.0"
author:
  - Romain VOLPI (@OmedoSef)
options:
  userid:
    description:
      - Full user ID the token belongs to, in the C(user@realm) format (for
        example C(automation@pve)).
    type: str
    required: true
  tokenid:
    description:
      - Identifier of the token itself (without the C(user@realm!) prefix).
    type: str
    required: true
  state:
    description:
      - Whether the token should exist.
    type: str
    choices: [present, absent]
    default: present
  comment:
    description:
      - Free-form description of the token.
      - Only applied/compared when set; omit to leave the current value
        untouched on update.
    type: str
  expire:
    description:
      - Token expiration date, as a Unix timestamp. V(0) means the token
        never expires.
      - Only applied/compared when set; omit to leave the current value
        untouched on update.
    type: int
  privsep:
    description:
      - Whether privilege separation is enabled for this token.
      - When V(true) (Proxmox's own default for new tokens), the token can
        only use privileges also explicitly granted to it via its own ACLs -
        it does not automatically inherit everything O(userid) can do. When
        V(false), the token has the full privileges of O(userid).
      - Only applied/compared when set; omit to leave the current value
        untouched on update.
    type: bool
  regenerate:
    description:
      - Generate a new secret value for an already-existing token,
        invalidating the previous one. Ignored when the token is being
        created (creating a token always generates a fresh secret).
      - Proxmox never returns the current secret, so this module cannot
        detect drift in it - this must be requested explicitly every time a
        rotation is wanted.
    type: bool
    default: false
extends_documentation_fragment:
  - omedosef.proxmox.proxmox
"""

EXAMPLES = r"""
- name: Create a token, capturing its one-time secret value
  omedosef.proxmox.user_token:
    api_backend: local
    userid: automation@pve
    tokenid: ansible
    comment: Used by the ansible-proxmox CI pipeline
    privsep: true
  register: token

- name: Show the secret (only present right after creation/regeneration)
  ansible.builtin.debug:
    msg: "{{ token.token.full_tokenid }} = {{ token.token.value }}"
  when: token.token.value is defined

- name: Update just the comment, leaving the secret and everything else untouched
  omedosef.proxmox.user_token:
    api_backend: local
    userid: automation@pve
    tokenid: ansible
    comment: Rotated quarterly

- name: Rotate the secret
  omedosef.proxmox.user_token:
    api_backend: local
    userid: automation@pve
    tokenid: ansible
    regenerate: true
  register: rotated

- name: Remove a token
  omedosef.proxmox.user_token:
    api_backend: local
    userid: automation@pve
    tokenid: ansible
    state: absent
"""

RETURN = r"""
token:
  description: >-
    Current state of the token as returned by the Proxmox VE API, or
    V(none) if it does not exist (or was just removed).
  returned: success
  type: dict
  contains:
    userid:
      description: The user the token belongs to.
      type: str
      returned: success
    tokenid:
      description: The token's own identifier.
      type: str
      returned: success
    full_tokenid:
      description: The full identifier used to authenticate with this token.
      type: str
      returned: success
      sample: "automation@pve!ansible"
    comment:
      description: Free-form description of the token.
      type: str
      returned: success
    expire:
      description: Expiration date as a Unix timestamp, V(0) if it never expires.
      type: int
      returned: success
    privsep:
      description: Whether privilege separation is enabled.
      type: bool
      returned: success
    value:
      description: >-
        The token's secret value. Proxmox only ever returns this once - it
        is only present here right after the token was created or its
        secret was regenerated, never on an unrelated create/update/no-op
        call, and never retrievable again afterwards.
      type: str
      returned: when the token was just created, or O(regenerate=true) applied
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


COMPARABLE_FIELDS = ("comment", "expire", "privsep")


def _normalize(field, value):
    if field == "privsep":
        return bool(int(value)) if value is not None else True
    if field == "expire":
        return int(value) if value is not None else 0
    return value


def compute_changes(current, desired):
    return ProxmoxAnsible.compute_changes(
        current, desired, COMPARABLE_FIELDS, _normalize
    )


class ProxmoxUserTokenAnsible(ProxmoxAnsible):
    def get_token(self, userid, tokenid):
        try:
            token = self.proxmox_api.access.users(userid).token(tokenid).get()
        except ResourceException:
            # Proxmox reports a missing token as a generic 500 rather than a
            # 404, so any error here is treated as "does not exist". By this
            # point _connect() has already succeeded, so a genuine
            # auth/connectivity failure is unlikely to surface only now.
            return None
        token["userid"] = userid
        token["tokenid"] = tokenid
        token["full_tokenid"] = f"{userid}!{tokenid}"
        return token

    def create_token(self, userid, tokenid, params):
        payload = self._filter_none_values(params)
        try:
            return self.proxmox_api.access.users(userid).token(tokenid).post(**payload)
        except ResourceException as exc:
            self.module.fail_json(
                msg=f"Failed to create token {tokenid} for user {userid}: {exc}"
            )

    def update_token(self, userid, tokenid, changes):
        payload = self._filter_none_values(changes)
        try:
            return self.proxmox_api.access.users(userid).token(tokenid).put(**payload)
        except ResourceException as exc:
            self.module.fail_json(
                msg=f"Failed to update token {tokenid} for user {userid}: {exc}"
            )

    def delete_token(self, userid, tokenid):
        try:
            self.proxmox_api.access.users(userid).token(tokenid).delete()
        except ResourceException as exc:
            self.module.fail_json(
                msg=f"Failed to delete token {tokenid} for user {userid}: {exc}"
            )


def main():
    argument_spec = proxmox_auth_argument_spec()
    argument_spec.update(
        userid=dict(type="str", required=True),
        tokenid=dict(type="str", required=True, no_log=False),
        state=dict(type="str", choices=["present", "absent"], default="present"),
        comment=dict(type="str"),
        expire=dict(type="int"),
        privsep=dict(type="bool"),
        regenerate=dict(type="bool", default=False),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=proxmox_required_if(),
        required_together=proxmox_required_together(),
    )

    proxmox = ProxmoxUserTokenAnsible(module)
    userid = module.params["userid"]
    tokenid = module.params["tokenid"]
    state = module.params["state"]
    current = proxmox.get_token(userid, tokenid)

    if state == "absent":
        if current is None:
            module.exit_json(changed=False, token=None)
        if not module.check_mode:
            proxmox.delete_token(userid, tokenid)
        module.exit_json(changed=True, token=None)

    desired = {field: module.params[field] for field in COMPARABLE_FIELDS}

    if current is None:
        if not module.check_mode:
            result = proxmox.create_token(userid, tokenid, desired)
            current = proxmox.get_token(userid, tokenid)
            current["value"] = result.get("value")
        module.exit_json(changed=True, token=current)

    changes = compute_changes(current, desired)
    regenerate = module.params["regenerate"]

    if not changes and not regenerate:
        module.exit_json(changed=False, token=current)

    if not module.check_mode:
        payload = dict(changes)
        if regenerate:
            payload["regenerate"] = True
        result = proxmox.update_token(userid, tokenid, payload)
        current = proxmox.get_token(userid, tokenid)
        if regenerate:
            current["value"] = result.get("value")

    module.exit_json(changed=True, token=current)


if __name__ == "__main__":
    main()
