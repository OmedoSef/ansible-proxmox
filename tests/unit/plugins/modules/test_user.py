# -*- coding: utf-8 -*-
# Copyright (c) 2026, Romain VOLPI <romain.volpi@omedo.net>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

import pytest
from ansible_collections.omedosef.proxmox.plugins.modules.user import (
    ProxmoxUserAnsible,
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
    "userid": "jdoe@pve",
    "state": "present",
    "comment": None,
    "email": None,
    "enable": None,
    "expire": None,
    "firstname": None,
    "lastname": None,
    "groups": None,
    "password": None,
    "update_password": "on_create",
}


@pytest.fixture
def proxmox(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    return ProxmoxUserAnsible(FakeModule(dict(BASE_PARAMS)))


# --- compute_changes -------------------------------------------------------


def test_compute_changes_ignores_unset_desired_fields():
    current = {"comment": "old", "enable": 1}
    desired = {"comment": None, "email": None}
    assert compute_changes(current, desired) == {}


def test_compute_changes_detects_comment_diff():
    current = {"comment": "old"}
    desired = {"comment": "new"}
    assert compute_changes(current, desired) == {"comment": "new"}


def test_compute_changes_normalizes_enable_as_bool():
    current = {"enable": 1}
    desired = {"enable": True}
    assert compute_changes(current, desired) == {}

    current = {"enable": 0}
    desired = {"enable": True}
    assert compute_changes(current, desired) == {"enable": True}


def test_compute_changes_defaults_missing_enable_to_true():
    current = {}
    desired = {"enable": True}
    assert compute_changes(current, desired) == {}

    desired = {"enable": False}
    assert compute_changes(current, desired) == {"enable": False}


def test_compute_changes_defaults_missing_expire_to_zero():
    current = {}
    desired = {"expire": 0}
    assert compute_changes(current, desired) == {}

    desired = {"expire": 12345}
    assert compute_changes(current, desired) == {"expire": 12345}


def test_compute_changes_compares_groups_regardless_of_order():
    current = {"groups": ["b", "a"]}
    desired = {"groups": ["a", "b"]}
    assert compute_changes(current, desired) == {}

    desired = {"groups": ["a", "c"]}
    assert compute_changes(current, desired) == {"groups": ["a", "c"]}


def test_compute_changes_handles_comma_string_groups_from_api():
    current = {"groups": "a,b"}
    desired = {"groups": ["b", "a"]}
    assert compute_changes(current, desired) == {}


# --- ProxmoxUserAnsible ------------------------------------------------


def test_get_user_returns_none_when_not_found(proxmox):
    proxmox.proxmox_api.access.users.return_value.get.side_effect = ResourceException(
        500, "Internal Server Error", "no such user"
    )

    assert proxmox.get_user("jdoe@pve") is None


def test_get_user_injects_userid(proxmox):
    proxmox.proxmox_api.access.users.return_value.get.return_value = {
        "enable": 1,
        "groups": [],
    }

    user = proxmox.get_user("jdoe@pve")

    assert user == {"enable": 1, "groups": [], "userid": "jdoe@pve"}


def test_create_user_filters_none_and_joins_groups(proxmox):
    proxmox.create_user(
        "jdoe@pve",
        {"comment": "hi", "email": None, "groups": ["a", "b"], "password": "secret"},
    )

    proxmox.proxmox_api.access.users.post.assert_called_once_with(
        userid="jdoe@pve", comment="hi", groups="a,b", password="secret"
    )


def test_update_user_filters_none_and_joins_groups(proxmox):
    proxmox.update_user("jdoe@pve", {"comment": "hi", "groups": ["a"]})

    proxmox.proxmox_api.access.users.return_value.put.assert_called_once_with(
        comment="hi", groups="a"
    )


def test_set_password_calls_password_endpoint(proxmox):
    proxmox.set_password("jdoe@pve", "s3cret")

    proxmox.proxmox_api.access.password.put.assert_called_once_with(
        userid="jdoe@pve", password="s3cret"
    )


def test_delete_user_calls_delete(proxmox):
    proxmox.delete_user("jdoe@pve")

    proxmox.proxmox_api.access.users.return_value.delete.assert_called_once_with()


# --- main() end-to-end -------------------------------------------------


def test_main_creates_user_when_absent(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.user.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "firstname": "Jane", "password": "s3cret"})
    module_cls.return_value = fake
    fake.proxmox_api_get_user_calls = 0

    get_mock = mocker.patch.object(
        ProxmoxUserAnsible,
        "get_user",
        side_effect=[None, {"userid": "jdoe@pve", "firstname": "Jane"}],
    )
    create_mock = mocker.patch.object(ProxmoxUserAnsible, "create_user")

    with pytest.raises(SystemExit):
        main()

    create_mock.assert_called_once()
    assert create_mock.call_args.args[0] == "jdoe@pve"
    assert create_mock.call_args.args[1]["firstname"] == "Jane"
    assert create_mock.call_args.args[1]["password"] == "s3cret"
    assert fake.exited["changed"] is True
    assert get_mock.call_count == 2


def test_main_reports_no_change_when_already_matching(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.user.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "comment": "hi"})
    module_cls.return_value = fake

    mocker.patch.object(
        ProxmoxUserAnsible,
        "get_user",
        return_value={"userid": "jdoe@pve", "comment": "hi"},
    )
    update_mock = mocker.patch.object(ProxmoxUserAnsible, "update_user")

    with pytest.raises(SystemExit):
        main()

    update_mock.assert_not_called()
    assert fake.exited["changed"] is False


def test_main_updates_only_changed_fields(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.user.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "comment": "new comment"})
    module_cls.return_value = fake

    mocker.patch.object(
        ProxmoxUserAnsible,
        "get_user",
        side_effect=[
            {
                "userid": "jdoe@pve",
                "comment": "old comment",
                "email": "jdoe@example.com",
            },
            {
                "userid": "jdoe@pve",
                "comment": "new comment",
                "email": "jdoe@example.com",
            },
        ],
    )
    update_mock = mocker.patch.object(ProxmoxUserAnsible, "update_user")

    with pytest.raises(SystemExit):
        main()

    update_mock.assert_called_once_with("jdoe@pve", {"comment": "new comment"})
    assert fake.exited["changed"] is True


def test_main_does_not_touch_password_on_update_by_default(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.user.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "password": "new-pass"})
    module_cls.return_value = fake

    mocker.patch.object(
        ProxmoxUserAnsible, "get_user", return_value={"userid": "jdoe@pve"}
    )
    set_password_mock = mocker.patch.object(ProxmoxUserAnsible, "set_password")

    with pytest.raises(SystemExit):
        main()

    set_password_mock.assert_not_called()
    assert fake.exited["changed"] is False


def test_main_sets_password_on_update_when_always(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.user.AnsibleModule"
    )
    fake = FakeModule(
        {**BASE_PARAMS, "password": "new-pass", "update_password": "always"}
    )
    module_cls.return_value = fake

    mocker.patch.object(
        ProxmoxUserAnsible, "get_user", return_value={"userid": "jdoe@pve"}
    )
    set_password_mock = mocker.patch.object(ProxmoxUserAnsible, "set_password")

    with pytest.raises(SystemExit):
        main()

    set_password_mock.assert_called_once_with("jdoe@pve", "new-pass")
    assert fake.exited["changed"] is True


def test_main_deletes_user_when_state_absent(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.user.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "state": "absent"})
    module_cls.return_value = fake

    mocker.patch.object(
        ProxmoxUserAnsible, "get_user", return_value={"userid": "jdoe@pve"}
    )
    delete_mock = mocker.patch.object(ProxmoxUserAnsible, "delete_user")

    with pytest.raises(SystemExit):
        main()

    delete_mock.assert_called_once_with("jdoe@pve")
    assert fake.exited["changed"] is True


def test_main_absent_is_noop_when_already_gone(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.user.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "state": "absent"})
    module_cls.return_value = fake

    mocker.patch.object(ProxmoxUserAnsible, "get_user", return_value=None)
    delete_mock = mocker.patch.object(ProxmoxUserAnsible, "delete_user")

    with pytest.raises(SystemExit):
        main()

    delete_mock.assert_not_called()
    assert fake.exited["changed"] is False


def test_main_check_mode_does_not_call_the_api(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module_cls = mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.modules.user.AnsibleModule"
    )
    fake = FakeModule({**BASE_PARAMS, "comment": "new comment", "_check_mode": True})
    fake.check_mode = True
    module_cls.return_value = fake

    mocker.patch.object(
        ProxmoxUserAnsible,
        "get_user",
        return_value={"userid": "jdoe@pve", "comment": "old"},
    )
    update_mock = mocker.patch.object(ProxmoxUserAnsible, "update_user")

    with pytest.raises(SystemExit):
        main()

    update_mock.assert_not_called()
    assert fake.exited["changed"] is True
