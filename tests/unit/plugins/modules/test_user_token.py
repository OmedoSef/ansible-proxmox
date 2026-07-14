# -*- coding: utf-8 -*-
# Copyright (c) 2026, Romain VOLPI <romain.volpi@omedo.net>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

import pytest
from ansible_collections.omedosef.proxmox.plugins.modules.user_token import (
    ProxmoxUserTokenAnsible,
    compute_changes,
    main,
)
from proxmoxer.core import ResourceException

MODULE_UTILS = "ansible_collections.omedosef.proxmox.plugins.module_utils.proxmox"


class FakeModule:
    def __init__(self, params):
        self.params = params
        self.check_mode = params.get("_check_mode", False)
        self.exited = None
        self.failed = None

    def exit_json(self, **kwargs):
        self.exited = kwargs
        raise SystemExit(0)

    def fail_json(self, **kwargs):
        self.failed = kwargs
        raise SystemExit(1)


BASE_PARAMS = {
    "api_host": None,
    "api_port": None,
    "api_backend": "local",
    "api_user": None,
    "api_password": None,
    "api_token_id": None,
    "api_token_secret": None,
    "api_ssh_private_key_file": None,
    "api_sudo": False,
    "validate_certs": True,
    "userid": "automation@pve",
    "tokenid": "ansible",
    "state": "present",
    "comment": None,
    "expire": None,
    "privsep": None,
    "regenerate": False,
}


@pytest.fixture
def proxmox(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    return ProxmoxUserTokenAnsible(FakeModule(dict(BASE_PARAMS)))


# --- compute_changes -------------------------------------------------------


def test_compute_changes_ignores_unset_desired_fields():
    current = {"comment": "old", "privsep": 1}
    desired = {"comment": None, "expire": None}
    assert compute_changes(current, desired) == {}


def test_compute_changes_detects_comment_diff():
    current = {"comment": "old"}
    desired = {"comment": "new"}
    assert compute_changes(current, desired) == {"comment": "new"}


def test_compute_changes_normalizes_privsep_as_bool():
    current = {"privsep": 1}
    desired = {"privsep": True}
    assert compute_changes(current, desired) == {}

    current = {"privsep": 0}
    desired = {"privsep": True}
    assert compute_changes(current, desired) == {"privsep": True}


def test_compute_changes_defaults_missing_privsep_to_true():
    current = {}
    desired = {"privsep": True}
    assert compute_changes(current, desired) == {}

    desired = {"privsep": False}
    assert compute_changes(current, desired) == {"privsep": False}


def test_compute_changes_defaults_missing_expire_to_zero():
    current = {}
    desired = {"expire": 0}
    assert compute_changes(current, desired) == {}

    desired = {"expire": 12345}
    assert compute_changes(current, desired) == {"expire": 12345}


# --- ProxmoxUserTokenAnsible ------------------------------------------------


def test_get_token_returns_none_when_not_found(proxmox):
    proxmox.proxmox_api.access.users.return_value.token.return_value.get.side_effect = (
        ResourceException(500, "Internal Server Error", "no such token")
    )

    assert proxmox.get_token("automation@pve", "ansible") is None


def test_get_token_injects_identifiers(proxmox):
    proxmox.proxmox_api.access.users.return_value.token.return_value.get.return_value = {
        "comment": "hi",
        "expire": 0,
        "privsep": 1,
    }

    token = proxmox.get_token("automation@pve", "ansible")

    assert token == {
        "comment": "hi",
        "expire": 0,
        "privsep": 1,
        "userid": "automation@pve",
        "tokenid": "ansible",
        "full_tokenid": "automation@pve!ansible",
    }


def test_create_token_filters_none_and_returns_api_response(proxmox):
    proxmox.proxmox_api.access.users.return_value.token.return_value.post.return_value = {
        "value": "secret-value",
        "full-tokenid": "automation@pve!ansible",
    }

    result = proxmox.create_token(
        "automation@pve", "ansible", {"comment": "hi", "expire": None}
    )

    proxmox.proxmox_api.access.users.return_value.token.return_value.post.assert_called_once_with(
        comment="hi"
    )
    assert result["value"] == "secret-value"


def test_update_token_filters_none_and_returns_api_response(proxmox):
    proxmox.proxmox_api.access.users.return_value.token.return_value.put.return_value = {
        "value": "new-secret"
    }

    result = proxmox.update_token(
        "automation@pve", "ansible", {"comment": "hi", "regenerate": True}
    )

    proxmox.proxmox_api.access.users.return_value.token.return_value.put.assert_called_once_with(
        comment="hi", regenerate=True
    )
    assert result["value"] == "new-secret"


def test_delete_token_calls_delete(proxmox):
    proxmox.delete_token("automation@pve", "ansible")

    proxmox.proxmox_api.access.users.return_value.token.return_value.delete.assert_called_once_with()


def test_create_token_fails_cleanly_on_api_error(proxmox):
    proxmox.proxmox_api.access.users.return_value.token.return_value.post.side_effect = ResourceException(
        500, "Internal Server Error", "boom"
    )

    with pytest.raises(SystemExit):
        proxmox.create_token("automation@pve", "ansible", {"comment": "hi"})

    assert (
        "Failed to create token ansible for user automation@pve"
        in proxmox.module.failed["msg"]
    )


def test_delete_token_fails_cleanly_on_api_error(proxmox):
    proxmox.proxmox_api.access.users.return_value.token.return_value.delete.side_effect = ResourceException(
        500, "Internal Server Error", "boom"
    )

    with pytest.raises(SystemExit):
        proxmox.delete_token("automation@pve", "ansible")

    assert (
        "Failed to delete token ansible for user automation@pve"
        in proxmox.module.failed["msg"]
    )


# --- main() end-to-end -------------------------------------------------


def test_main_creates_token_when_absent(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.user_token.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "comment": "hi"})
    module_cls.return_value = fake

    get_mock = mocker.patch.object(
        ProxmoxUserTokenAnsible,
        "get_token",
        side_effect=[
            None,
            {
                "userid": "automation@pve",
                "tokenid": "ansible",
                "full_tokenid": "automation@pve!ansible",
                "comment": "hi",
            },
        ],
    )
    create_mock = mocker.patch.object(
        ProxmoxUserTokenAnsible, "create_token", return_value={"value": "s3cret"}
    )

    with pytest.raises(SystemExit):
        main()

    create_mock.assert_called_once_with(
        "automation@pve", "ansible", {"comment": "hi", "expire": None, "privsep": None}
    )
    assert fake.exited["changed"] is True
    assert fake.exited["token"]["value"] == "s3cret"
    assert get_mock.call_count == 2


def test_main_reports_no_change_when_already_matching_and_not_regenerating(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.user_token.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "comment": "hi"})
    module_cls.return_value = fake

    mocker.patch.object(
        ProxmoxUserTokenAnsible,
        "get_token",
        return_value={
            "userid": "automation@pve",
            "tokenid": "ansible",
            "comment": "hi",
        },
    )
    update_mock = mocker.patch.object(ProxmoxUserTokenAnsible, "update_token")

    with pytest.raises(SystemExit):
        main()

    update_mock.assert_not_called()
    assert fake.exited["changed"] is False
    assert "value" not in fake.exited["token"]


def test_main_updates_only_changed_fields(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.user_token.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "comment": "new comment"})
    module_cls.return_value = fake

    mocker.patch.object(
        ProxmoxUserTokenAnsible,
        "get_token",
        side_effect=[
            {
                "userid": "automation@pve",
                "tokenid": "ansible",
                "comment": "old comment",
            },
            {
                "userid": "automation@pve",
                "tokenid": "ansible",
                "comment": "new comment",
            },
        ],
    )
    update_mock = mocker.patch.object(
        ProxmoxUserTokenAnsible, "update_token", return_value={}
    )

    with pytest.raises(SystemExit):
        main()

    update_mock.assert_called_once_with(
        "automation@pve", "ansible", {"comment": "new comment"}
    )
    assert fake.exited["changed"] is True
    assert "value" not in fake.exited["token"]


def test_main_regenerate_forces_change_and_surfaces_value(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.user_token.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "regenerate": True})
    module_cls.return_value = fake

    mocker.patch.object(
        ProxmoxUserTokenAnsible,
        "get_token",
        return_value={
            "userid": "automation@pve",
            "tokenid": "ansible",
            "comment": "hi",
        },
    )
    update_mock = mocker.patch.object(
        ProxmoxUserTokenAnsible,
        "update_token",
        return_value={"value": "rotated-secret"},
    )

    with pytest.raises(SystemExit):
        main()

    update_mock.assert_called_once_with(
        "automation@pve", "ansible", {"regenerate": True}
    )
    assert fake.exited["changed"] is True
    assert fake.exited["token"]["value"] == "rotated-secret"


def test_main_deletes_token_when_state_absent(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.user_token.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "state": "absent"})
    module_cls.return_value = fake

    mocker.patch.object(
        ProxmoxUserTokenAnsible,
        "get_token",
        return_value={"userid": "automation@pve", "tokenid": "ansible"},
    )
    delete_mock = mocker.patch.object(ProxmoxUserTokenAnsible, "delete_token")

    with pytest.raises(SystemExit):
        main()

    delete_mock.assert_called_once_with("automation@pve", "ansible")
    assert fake.exited["changed"] is True


def test_main_absent_is_noop_when_already_gone(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.user_token.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "state": "absent"})
    module_cls.return_value = fake

    mocker.patch.object(ProxmoxUserTokenAnsible, "get_token", return_value=None)
    delete_mock = mocker.patch.object(ProxmoxUserTokenAnsible, "delete_token")

    with pytest.raises(SystemExit):
        main()

    delete_mock.assert_not_called()
    assert fake.exited["changed"] is False


def test_main_check_mode_does_not_call_the_api(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.user_token.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "comment": "new comment", "_check_mode": True})
    fake.check_mode = True
    module_cls.return_value = fake

    mocker.patch.object(
        ProxmoxUserTokenAnsible,
        "get_token",
        return_value={
            "userid": "automation@pve",
            "tokenid": "ansible",
            "comment": "old",
        },
    )
    update_mock = mocker.patch.object(ProxmoxUserTokenAnsible, "update_token")

    with pytest.raises(SystemExit):
        main()

    update_mock.assert_not_called()
    assert fake.exited["changed"] is True
