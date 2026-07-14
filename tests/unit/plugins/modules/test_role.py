# -*- coding: utf-8 -*-
# Copyright (c) 2026, Romain VOLPI <romain.volpi@omedo.net>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

import pytest
from ansible_collections.omedosef.proxmox.plugins.modules.role import (
    ProxmoxRoleAnsible,
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
    "roleid": "vm-operator",
    "state": "present",
    "privs": None,
}


@pytest.fixture
def proxmox(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    return ProxmoxRoleAnsible(FakeModule(dict(BASE_PARAMS)))


# --- compute_changes -----------------------------------------------------


def test_compute_changes_ignores_unset_desired_fields():
    current = {"privs": ["VM.Audit"]}
    desired = {"privs": None}
    assert compute_changes(current, desired) == {}


def test_compute_changes_detects_privs_diff():
    current = {"privs": ["VM.Audit"]}
    desired = {"privs": ["VM.Audit", "VM.PowerMgmt"]}
    assert compute_changes(current, desired) == {"privs": ["VM.Audit", "VM.PowerMgmt"]}


def test_compute_changes_ignores_privs_order():
    current = {"privs": ["VM.Audit", "VM.PowerMgmt"]}
    desired = {"privs": ["VM.PowerMgmt", "VM.Audit"]}
    assert compute_changes(current, desired) == {}


def test_compute_changes_detects_stripping_all_privs():
    current = {"privs": ["VM.Audit"]}
    desired = {"privs": []}
    assert compute_changes(current, desired) == {"privs": []}


# --- ProxmoxRoleAnsible -----------------------------------------------------


def test_get_role_returns_none_when_not_found(proxmox):
    proxmox.proxmox_api.access.roles.return_value.get.side_effect = ResourceException(
        500, "Internal Server Error", "no such role"
    )

    assert proxmox.get_role("vm-operator") is None


def test_get_role_normalizes_privs_dict_into_sorted_list(proxmox):
    proxmox.proxmox_api.access.roles.return_value.get.return_value = {
        "VM.PowerMgmt": 1,
        "VM.Audit": 1,
    }

    role = proxmox.get_role("vm-operator")

    assert role == {"roleid": "vm-operator", "privs": ["VM.Audit", "VM.PowerMgmt"]}


def test_get_role_handles_no_privileges(proxmox):
    proxmox.proxmox_api.access.roles.return_value.get.return_value = {}

    role = proxmox.get_role("vm-operator")

    assert role == {"roleid": "vm-operator", "privs": []}


def test_create_role_filters_none_and_joins_privs(proxmox):
    proxmox.create_role(
        "vm-operator", {"privs": ["VM.Audit", "VM.PowerMgmt"], "extra": None}
    )

    proxmox.proxmox_api.access.roles.post.assert_called_once_with(
        roleid="vm-operator", privs="VM.Audit,VM.PowerMgmt"
    )


def test_create_role_without_privs_sends_no_privs_field(proxmox):
    proxmox.create_role("vm-operator", {"privs": None})

    proxmox.proxmox_api.access.roles.post.assert_called_once_with(roleid="vm-operator")


def test_update_role_filters_none_and_joins_privs(proxmox):
    proxmox.update_role("vm-operator", {"privs": ["VM.Audit"]})

    proxmox.proxmox_api.access.roles.return_value.put.assert_called_once_with(
        privs="VM.Audit"
    )


def test_delete_role_calls_delete(proxmox):
    proxmox.delete_role("vm-operator")

    proxmox.proxmox_api.access.roles.return_value.delete.assert_called_once_with()


def test_create_role_fails_cleanly_on_api_error(proxmox):
    proxmox.proxmox_api.access.roles.post.side_effect = ResourceException(
        500, "Internal Server Error", "boom"
    )

    with pytest.raises(SystemExit):
        proxmox.create_role("vm-operator", {"privs": ["VM.Audit"]})

    assert "Failed to create role vm-operator" in proxmox.module.failed["msg"]


def test_update_role_fails_cleanly_on_api_error(proxmox):
    proxmox.proxmox_api.access.roles.return_value.put.side_effect = ResourceException(
        500, "Internal Server Error", "boom"
    )

    with pytest.raises(SystemExit):
        proxmox.update_role("vm-operator", {"privs": ["VM.Audit"]})

    assert "Failed to update role vm-operator" in proxmox.module.failed["msg"]


def test_delete_role_fails_cleanly_on_api_error(proxmox):
    proxmox.proxmox_api.access.roles.return_value.delete.side_effect = (
        ResourceException(500, "Internal Server Error", "boom")
    )

    with pytest.raises(SystemExit):
        proxmox.delete_role("vm-operator")

    assert "Failed to delete role vm-operator" in proxmox.module.failed["msg"]


# --- main() end-to-end ----------------------------------------------------


def test_main_creates_role_when_absent(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.role.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "privs": ["VM.Audit"]})
    module_cls.return_value = fake

    get_mock = mocker.patch.object(
        ProxmoxRoleAnsible,
        "get_role",
        side_effect=[None, {"roleid": "vm-operator", "privs": ["VM.Audit"]}],
    )
    create_mock = mocker.patch.object(ProxmoxRoleAnsible, "create_role")

    with pytest.raises(SystemExit):
        main()

    create_mock.assert_called_once_with("vm-operator", {"privs": ["VM.Audit"]})
    assert fake.exited["changed"] is True
    assert get_mock.call_count == 2


def test_main_reports_no_change_when_already_matching(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.role.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "privs": ["VM.Audit"]})
    module_cls.return_value = fake

    mocker.patch.object(
        ProxmoxRoleAnsible,
        "get_role",
        return_value={"roleid": "vm-operator", "privs": ["VM.Audit"]},
    )
    update_mock = mocker.patch.object(ProxmoxRoleAnsible, "update_role")

    with pytest.raises(SystemExit):
        main()

    update_mock.assert_not_called()
    assert fake.exited["changed"] is False


def test_main_updates_only_when_changed(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.role.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "privs": ["VM.Audit", "VM.PowerMgmt"]})
    module_cls.return_value = fake

    mocker.patch.object(
        ProxmoxRoleAnsible,
        "get_role",
        side_effect=[
            {"roleid": "vm-operator", "privs": ["VM.Audit"]},
            {"roleid": "vm-operator", "privs": ["VM.Audit", "VM.PowerMgmt"]},
        ],
    )
    update_mock = mocker.patch.object(ProxmoxRoleAnsible, "update_role")

    with pytest.raises(SystemExit):
        main()

    update_mock.assert_called_once_with(
        "vm-operator", {"privs": ["VM.Audit", "VM.PowerMgmt"]}
    )
    assert fake.exited["changed"] is True


def test_main_leaves_privs_untouched_when_omitted(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.role.AnsibleModule"
    )
    fake = FakeModule(dict(BASE_PARAMS))
    module_cls.return_value = fake

    mocker.patch.object(
        ProxmoxRoleAnsible,
        "get_role",
        return_value={"roleid": "vm-operator", "privs": ["VM.Audit"]},
    )
    update_mock = mocker.patch.object(ProxmoxRoleAnsible, "update_role")

    with pytest.raises(SystemExit):
        main()

    update_mock.assert_not_called()
    assert fake.exited["changed"] is False


def test_main_deletes_role_when_state_absent(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.role.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "state": "absent"})
    module_cls.return_value = fake

    mocker.patch.object(
        ProxmoxRoleAnsible, "get_role", return_value={"roleid": "vm-operator"}
    )
    delete_mock = mocker.patch.object(ProxmoxRoleAnsible, "delete_role")

    with pytest.raises(SystemExit):
        main()

    delete_mock.assert_called_once_with("vm-operator")
    assert fake.exited["changed"] is True


def test_main_absent_is_noop_when_already_gone(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.role.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "state": "absent"})
    module_cls.return_value = fake

    mocker.patch.object(ProxmoxRoleAnsible, "get_role", return_value=None)
    delete_mock = mocker.patch.object(ProxmoxRoleAnsible, "delete_role")

    with pytest.raises(SystemExit):
        main()

    delete_mock.assert_not_called()
    assert fake.exited["changed"] is False


def test_main_check_mode_does_not_call_the_api(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.role.AnsibleModule"
    )
    fake = FakeModule(
        {**BASE_PARAMS, "privs": ["VM.Audit", "VM.PowerMgmt"], "_check_mode": True}
    )
    fake.check_mode = True
    module_cls.return_value = fake

    mocker.patch.object(
        ProxmoxRoleAnsible,
        "get_role",
        return_value={"roleid": "vm-operator", "privs": ["VM.Audit"]},
    )
    update_mock = mocker.patch.object(ProxmoxRoleAnsible, "update_role")

    with pytest.raises(SystemExit):
        main()

    update_mock.assert_not_called()
    assert fake.exited["changed"] is True
