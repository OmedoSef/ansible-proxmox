# -*- coding: utf-8 -*-
# Copyright (c) 2026, Romain VOLPI <romain.volpi@omedo.net>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

import pytest
from ansible_collections.omedosef.proxmox.plugins.modules.acl import (
    ProxmoxAclAnsible,
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
    "path": "/vms/100",
    "type": "user",
    "ugid": "jdoe@pve",
    "roles": ["PVEVMUser"],
    "propagate": True,
    "state": "present",
}

ACL_LIST = [
    {
        "path": "/vms/100",
        "type": "user",
        "ugid": "jdoe@pve",
        "roleid": "PVEVMUser",
        "propagate": 1,
    },
    {
        "path": "/vms/100",
        "type": "user",
        "ugid": "jdoe@pve",
        "roleid": "PVEAuditor",
        "propagate": 0,
    },
    {
        "path": "/vms/100",
        "type": "group",
        "ugid": "jdoe@pve",
        "roleid": "PVEVMUser",
        "propagate": 1,
    },
    {
        "path": "/vms/200",
        "type": "user",
        "ugid": "jdoe@pve",
        "roleid": "PVEVMUser",
        "propagate": 1,
    },
]


@pytest.fixture
def proxmox(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    return ProxmoxAclAnsible(FakeModule(dict(BASE_PARAMS)))


# --- ProxmoxAclAnsible.get_entries ------------------------------------------


def test_get_entries_filters_by_path_type_and_ugid(proxmox):
    proxmox.proxmox_api.access.acl.get.return_value = ACL_LIST

    entries = proxmox.get_entries("/vms/100", "user", "jdoe@pve")

    assert entries == {"PVEVMUser": True, "PVEAuditor": False}


def test_get_entries_returns_empty_dict_when_no_match(proxmox):
    proxmox.proxmox_api.access.acl.get.return_value = ACL_LIST

    entries = proxmox.get_entries("/vms/999", "user", "jdoe@pve")

    assert entries == {}


def test_get_entries_fails_cleanly_on_api_error(proxmox):
    proxmox.proxmox_api.access.acl.get.side_effect = ResourceException(
        500, "Internal Server Error", "boom"
    )

    with pytest.raises(SystemExit):
        proxmox.get_entries("/vms/100", "user", "jdoe@pve")

    assert "Failed to list ACL entries" in proxmox.module.failed["msg"]


# --- ProxmoxAclAnsible.grant_roles / revoke_roles ---------------------------


def test_grant_roles_maps_type_to_the_right_ugid_param(proxmox):
    proxmox.grant_roles("/vms/100", "user", "jdoe@pve", ["PVEVMUser"], True)

    proxmox.proxmox_api.access.acl.put.assert_called_once_with(
        path="/vms/100", roles="PVEVMUser", propagate=1, users="jdoe@pve"
    )


def test_grant_roles_group_type(proxmox):
    proxmox.grant_roles("/", "group", "admins", ["PVEAuditor"], False)

    proxmox.proxmox_api.access.acl.put.assert_called_once_with(
        path="/", roles="PVEAuditor", propagate=0, groups="admins"
    )


def test_grant_roles_token_type(proxmox):
    proxmox.grant_roles("/vms/100", "token", "jdoe@pve!ansible", ["PVEVMUser"], True)

    proxmox.proxmox_api.access.acl.put.assert_called_once_with(
        path="/vms/100", roles="PVEVMUser", propagate=1, tokens="jdoe@pve!ansible"
    )


def test_revoke_roles_sends_delete_flag(proxmox):
    proxmox.revoke_roles("/vms/100", "user", "jdoe@pve", ["PVEVMUser"])

    proxmox.proxmox_api.access.acl.put.assert_called_once_with(
        path="/vms/100", roles="PVEVMUser", delete=1, users="jdoe@pve"
    )


def test_grant_roles_fails_cleanly_on_api_error(proxmox):
    proxmox.proxmox_api.access.acl.put.side_effect = ResourceException(
        500, "Internal Server Error", "boom"
    )

    with pytest.raises(SystemExit):
        proxmox.grant_roles("/vms/100", "user", "jdoe@pve", ["PVEVMUser"], True)

    assert "Failed to grant role(s) PVEVMUser to user jdoe@pve on path /vms/100" in (
        proxmox.module.failed["msg"]
    )


def test_revoke_roles_fails_cleanly_on_api_error(proxmox):
    proxmox.proxmox_api.access.acl.put.side_effect = ResourceException(
        500, "Internal Server Error", "boom"
    )

    with pytest.raises(SystemExit):
        proxmox.revoke_roles("/vms/100", "user", "jdoe@pve", ["PVEVMUser"])

    assert "Failed to revoke role(s) PVEVMUser from user jdoe@pve on path /vms/100" in (
        proxmox.module.failed["msg"]
    )


# --- main() end-to-end -------------------------------------------------


def test_main_grants_missing_role(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.acl.AnsibleModule"
    )
    fake = FakeModule(dict(BASE_PARAMS))
    module_cls.return_value = fake

    get_mock = mocker.patch.object(
        ProxmoxAclAnsible,
        "get_entries",
        side_effect=[{}, {"PVEVMUser": True}],
    )
    grant_mock = mocker.patch.object(ProxmoxAclAnsible, "grant_roles")

    with pytest.raises(SystemExit):
        main()

    grant_mock.assert_called_once_with(
        "/vms/100", "user", "jdoe@pve", ["PVEVMUser"], True
    )
    assert fake.exited["changed"] is True
    assert fake.exited["acl"] == {
        "path": "/vms/100",
        "type": "user",
        "ugid": "jdoe@pve",
        "roles": [{"roleid": "PVEVMUser", "propagate": True}],
    }
    assert get_mock.call_count == 2


def test_main_reports_no_change_when_role_already_granted_with_same_propagate(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.acl.AnsibleModule"
    )
    fake = FakeModule(dict(BASE_PARAMS))
    module_cls.return_value = fake

    mocker.patch.object(
        ProxmoxAclAnsible, "get_entries", return_value={"PVEVMUser": True}
    )
    grant_mock = mocker.patch.object(ProxmoxAclAnsible, "grant_roles")

    with pytest.raises(SystemExit):
        main()

    grant_mock.assert_not_called()
    assert fake.exited["changed"] is False


def test_main_regrants_when_propagate_differs(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.acl.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "propagate": False})
    module_cls.return_value = fake

    mocker.patch.object(
        ProxmoxAclAnsible,
        "get_entries",
        side_effect=[
            {"PVEVMUser": True},
            {"PVEVMUser": False},
        ],
    )
    grant_mock = mocker.patch.object(ProxmoxAclAnsible, "grant_roles")

    with pytest.raises(SystemExit):
        main()

    grant_mock.assert_called_once_with(
        "/vms/100", "user", "jdoe@pve", ["PVEVMUser"], False
    )
    assert fake.exited["changed"] is True


def test_main_leaves_other_roles_untouched_when_granting(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.acl.AnsibleModule"
    )
    fake = FakeModule(dict(BASE_PARAMS))
    module_cls.return_value = fake

    mocker.patch.object(
        ProxmoxAclAnsible,
        "get_entries",
        side_effect=[
            {"PVEAuditor": True},
            {"PVEAuditor": True, "PVEVMUser": True},
        ],
    )
    grant_mock = mocker.patch.object(ProxmoxAclAnsible, "grant_roles")

    with pytest.raises(SystemExit):
        main()

    grant_mock.assert_called_once_with(
        "/vms/100", "user", "jdoe@pve", ["PVEVMUser"], True
    )
    assert fake.exited["acl"]["roles"] == [
        {"roleid": "PVEAuditor", "propagate": True},
        {"roleid": "PVEVMUser", "propagate": True},
    ]


def test_main_revokes_role_when_state_absent(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.acl.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "state": "absent"})
    module_cls.return_value = fake

    mocker.patch.object(
        ProxmoxAclAnsible,
        "get_entries",
        side_effect=[{"PVEVMUser": True}, {}],
    )
    revoke_mock = mocker.patch.object(ProxmoxAclAnsible, "revoke_roles")

    with pytest.raises(SystemExit):
        main()

    revoke_mock.assert_called_once_with("/vms/100", "user", "jdoe@pve", ["PVEVMUser"])
    assert fake.exited["changed"] is True
    assert fake.exited["acl"]["roles"] == []


def test_main_absent_is_noop_when_role_not_granted(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.acl.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "state": "absent"})
    module_cls.return_value = fake

    mocker.patch.object(ProxmoxAclAnsible, "get_entries", return_value={})
    revoke_mock = mocker.patch.object(ProxmoxAclAnsible, "revoke_roles")

    with pytest.raises(SystemExit):
        main()

    revoke_mock.assert_not_called()
    assert fake.exited["changed"] is False


def test_main_absent_leaves_other_roles_untouched(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.acl.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "state": "absent"})
    module_cls.return_value = fake

    mocker.patch.object(
        ProxmoxAclAnsible,
        "get_entries",
        side_effect=[
            {"PVEVMUser": True, "PVEAuditor": True},
            {"PVEAuditor": True},
        ],
    )
    revoke_mock = mocker.patch.object(ProxmoxAclAnsible, "revoke_roles")

    with pytest.raises(SystemExit):
        main()

    revoke_mock.assert_called_once_with("/vms/100", "user", "jdoe@pve", ["PVEVMUser"])
    assert fake.exited["acl"]["roles"] == [{"roleid": "PVEAuditor", "propagate": True}]


def test_main_check_mode_does_not_call_the_api(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.acl.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "_check_mode": True})
    fake.check_mode = True
    module_cls.return_value = fake

    mocker.patch.object(ProxmoxAclAnsible, "get_entries", return_value={})
    grant_mock = mocker.patch.object(ProxmoxAclAnsible, "grant_roles")

    with pytest.raises(SystemExit):
        main()

    grant_mock.assert_not_called()
    assert fake.exited["changed"] is True
