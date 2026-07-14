# -*- coding: utf-8 -*-
# Copyright (c) 2026, Romain VOLPI <romain.volpi@omedo.net>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

import pytest
from ansible_collections.omedosef.proxmox.plugins.modules.group import (
    ProxmoxGroupAnsible,
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
    "groupid": "admins",
    "state": "present",
    "comment": None,
}


@pytest.fixture
def proxmox(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    return ProxmoxGroupAnsible(FakeModule(dict(BASE_PARAMS)))


# --- compute_changes -----------------------------------------------------


def test_compute_changes_ignores_unset_desired_fields():
    current = {"comment": "old"}
    desired = {"comment": None}
    assert compute_changes(current, desired) == {}


def test_compute_changes_detects_comment_diff():
    current = {"comment": "old"}
    desired = {"comment": "new"}
    assert compute_changes(current, desired) == {"comment": "new"}


def test_compute_changes_no_diff_when_equal():
    current = {"comment": "same"}
    desired = {"comment": "same"}
    assert compute_changes(current, desired) == {}


# --- ProxmoxGroupAnsible ---------------------------------------------------


def test_get_group_returns_none_when_not_found(proxmox):
    proxmox.proxmox_api.access.groups.return_value.get.side_effect = ResourceException(
        500, "Internal Server Error", "no such group"
    )

    assert proxmox.get_group("admins") is None


def test_get_group_injects_groupid(proxmox):
    proxmox.proxmox_api.access.groups.return_value.get.return_value = {
        "comment": "Admins group",
        "members": [],
    }

    group = proxmox.get_group("admins")

    assert group == {"comment": "Admins group", "members": [], "groupid": "admins"}


def test_create_group_filters_none(proxmox):
    proxmox.create_group("admins", {"comment": "hi", "extra": None})

    proxmox.proxmox_api.access.groups.post.assert_called_once_with(
        groupid="admins", comment="hi"
    )


def test_update_group_filters_none(proxmox):
    proxmox.update_group("admins", {"comment": "hi", "extra": None})

    proxmox.proxmox_api.access.groups.return_value.put.assert_called_once_with(
        comment="hi"
    )


def test_delete_group_calls_delete(proxmox):
    proxmox.delete_group("admins")

    proxmox.proxmox_api.access.groups.return_value.delete.assert_called_once_with()


def test_create_group_fails_cleanly_on_api_error(proxmox):
    proxmox.proxmox_api.access.groups.post.side_effect = ResourceException(
        500, "Internal Server Error", "boom"
    )

    with pytest.raises(SystemExit):
        proxmox.create_group("admins", {"comment": "hi"})

    assert "Failed to create group admins" in proxmox.module.failed["msg"]


def test_update_group_fails_cleanly_on_api_error(proxmox):
    proxmox.proxmox_api.access.groups.return_value.put.side_effect = ResourceException(
        500, "Internal Server Error", "boom"
    )

    with pytest.raises(SystemExit):
        proxmox.update_group("admins", {"comment": "hi"})

    assert "Failed to update group admins" in proxmox.module.failed["msg"]


def test_delete_group_fails_cleanly_on_api_error(proxmox):
    proxmox.proxmox_api.access.groups.return_value.delete.side_effect = (
        ResourceException(500, "Internal Server Error", "boom")
    )

    with pytest.raises(SystemExit):
        proxmox.delete_group("admins")

    assert "Failed to delete group admins" in proxmox.module.failed["msg"]


# --- main() end-to-end ----------------------------------------------------


def test_main_creates_group_when_absent(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.group.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "comment": "Admins group"})
    module_cls.return_value = fake

    get_mock = mocker.patch.object(
        ProxmoxGroupAnsible,
        "get_group",
        side_effect=[None, {"groupid": "admins", "comment": "Admins group"}],
    )
    create_mock = mocker.patch.object(ProxmoxGroupAnsible, "create_group")

    with pytest.raises(SystemExit):
        main()

    create_mock.assert_called_once_with("admins", {"comment": "Admins group"})
    assert fake.exited["changed"] is True
    assert get_mock.call_count == 2


def test_main_reports_no_change_when_already_matching(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.group.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "comment": "hi"})
    module_cls.return_value = fake

    mocker.patch.object(
        ProxmoxGroupAnsible,
        "get_group",
        return_value={"groupid": "admins", "comment": "hi"},
    )
    update_mock = mocker.patch.object(ProxmoxGroupAnsible, "update_group")

    with pytest.raises(SystemExit):
        main()

    update_mock.assert_not_called()
    assert fake.exited["changed"] is False


def test_main_updates_only_when_changed(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.group.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "comment": "new comment"})
    module_cls.return_value = fake

    mocker.patch.object(
        ProxmoxGroupAnsible,
        "get_group",
        side_effect=[
            {"groupid": "admins", "comment": "old comment"},
            {"groupid": "admins", "comment": "new comment"},
        ],
    )
    update_mock = mocker.patch.object(ProxmoxGroupAnsible, "update_group")

    with pytest.raises(SystemExit):
        main()

    update_mock.assert_called_once_with("admins", {"comment": "new comment"})
    assert fake.exited["changed"] is True


def test_main_deletes_group_when_state_absent(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.group.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "state": "absent"})
    module_cls.return_value = fake

    mocker.patch.object(
        ProxmoxGroupAnsible, "get_group", return_value={"groupid": "admins"}
    )
    delete_mock = mocker.patch.object(ProxmoxGroupAnsible, "delete_group")

    with pytest.raises(SystemExit):
        main()

    delete_mock.assert_called_once_with("admins")
    assert fake.exited["changed"] is True


def test_main_absent_is_noop_when_already_gone(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.group.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "state": "absent"})
    module_cls.return_value = fake

    mocker.patch.object(ProxmoxGroupAnsible, "get_group", return_value=None)
    delete_mock = mocker.patch.object(ProxmoxGroupAnsible, "delete_group")

    with pytest.raises(SystemExit):
        main()

    delete_mock.assert_not_called()
    assert fake.exited["changed"] is False


def test_main_check_mode_does_not_call_the_api(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.group.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "comment": "new comment", "_check_mode": True})
    fake.check_mode = True
    module_cls.return_value = fake

    mocker.patch.object(
        ProxmoxGroupAnsible,
        "get_group",
        return_value={"groupid": "admins", "comment": "old"},
    )
    update_mock = mocker.patch.object(ProxmoxGroupAnsible, "update_group")

    with pytest.raises(SystemExit):
        main()

    update_mock.assert_not_called()
    assert fake.exited["changed"] is True
