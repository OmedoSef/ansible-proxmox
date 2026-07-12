# -*- coding: utf-8 -*-
# Copyright (c) 2026, Romain VOLPI <romain.volpi@omedo.net>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

import pytest
from ansible.module_utils.basic import env_fallback
from ansible_collections.omedosef.proxmox.plugins.module_utils.proxmox import (
    ProxmoxAnsible,
    proxmox_auth_argument_spec,
    proxmox_required_if,
    proxmox_required_together,
)

MODULE_UTILS = "ansible_collections.omedosef.proxmox.plugins.module_utils.proxmox"


class FakeModule:
    def __init__(self, params):
        self.params = params
        self.failed = None

    def fail_json(self, **kwargs):
        self.failed = kwargs
        raise SystemExit(1)


BASE_PARAMS = {
    "api_host": "proxmox.example.com",
    "api_port": None,
    "api_backend": "https",
    "api_user": "root@pam",
    "api_password": None,
    "api_token_id": None,
    "api_token_secret": None,
    "api_ssh_private_key_file": None,
    "api_sudo": False,
    "validate_certs": True,
}


def test_proxmox_auth_argument_spec_contains_expected_keys():
    spec = proxmox_auth_argument_spec()

    assert set(spec) == {
        "api_host",
        "api_port",
        "api_backend",
        "api_user",
        "api_password",
        "api_token_id",
        "api_token_secret",
        "api_ssh_private_key_file",
        "api_sudo",
        "validate_certs",
    }
    # api_host/api_user are not unconditionally required: api_backend=local
    # needs neither. See proxmox_required_if() for the conditional rules.
    assert "required" not in spec["api_host"]
    assert "required" not in spec["api_user"]
    assert spec["api_password"]["no_log"] is True
    assert spec["api_token_secret"]["no_log"] is True
    assert spec["api_backend"]["choices"] == ["https", "ssh_paramiko", "local"]
    assert spec["api_backend"]["default"] == "https"
    assert spec["api_sudo"]["default"] is False
    assert "default" not in spec["api_port"]


def test_proxmox_auth_argument_spec_env_fallbacks():
    spec = proxmox_auth_argument_spec()

    expected_env_vars = {
        "api_host": "PROXMOX_API_HOST",
        "api_port": "PROXMOX_API_PORT",
        "api_backend": "PROXMOX_API_BACKEND",
        "api_user": "PROXMOX_API_USER",
        "api_password": "PROXMOX_API_PASSWORD",
        "api_token_id": "PROXMOX_API_TOKEN_ID",
        "api_token_secret": "PROXMOX_API_TOKEN_SECRET",
        "api_ssh_private_key_file": "PROXMOX_API_SSH_PRIVATE_KEY_FILE",
        "api_sudo": "PROXMOX_API_SUDO",
        "validate_certs": "PROXMOX_VALIDATE_CERTS",
    }

    for option, env_var in expected_env_vars.items():
        fallback_fn, fallback_args = spec[option]["fallback"]
        assert fallback_fn is env_fallback
        assert fallback_args == [env_var]


def test_proxmox_required_together():
    assert proxmox_required_together() == [("api_token_id", "api_token_secret")]


def test_proxmox_required_if():
    assert proxmox_required_if() == [
        ("api_backend", "https", ("api_host", "api_user"), False),
        ("api_backend", "ssh_paramiko", ("api_host", "api_user"), False),
        ("api_backend", "https", ("api_password", "api_token_id"), True),
    ]


def test_connect_https_uses_password_auth(mocker):
    fake_api = mocker.Mock()
    api_cls = mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI", return_value=fake_api)
    module = FakeModule({**BASE_PARAMS, "api_password": "s3cret"})

    proxmox = ProxmoxAnsible(module)

    assert proxmox.proxmox_api is fake_api
    api_cls.assert_called_once_with(
        "proxmox.example.com",
        backend="https",
        user="root@pam",
        port=8006,
        verify_ssl=True,
        password="s3cret",
    )


def test_connect_https_uses_token_auth(mocker):
    fake_api = mocker.Mock()
    api_cls = mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI", return_value=fake_api)
    module = FakeModule(
        {
            **BASE_PARAMS,
            "api_user": "automation@pve",
            "api_token_id": "ansible",
            "api_token_secret": "t0ken",
            "validate_certs": False,
        }
    )

    proxmox = ProxmoxAnsible(module)

    assert proxmox.proxmox_api is fake_api
    api_cls.assert_called_once_with(
        "proxmox.example.com",
        backend="https",
        user="automation@pve",
        port=8006,
        verify_ssl=False,
        token_name="ansible",
        token_value="t0ken",
    )


def test_connect_https_honors_explicit_port(mocker):
    api_cls = mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module = FakeModule({**BASE_PARAMS, "api_password": "s3cret", "api_port": 9006})

    ProxmoxAnsible(module)

    assert api_cls.call_args.kwargs["port"] == 9006


def test_connect_ssh_paramiko_uses_key_file(mocker):
    fake_api = mocker.Mock()
    api_cls = mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI", return_value=fake_api)
    module = FakeModule(
        {
            **BASE_PARAMS,
            "api_backend": "ssh_paramiko",
            "api_user": "root",
            "api_ssh_private_key_file": "/home/user/.ssh/id_ed25519",
            "api_sudo": True,
        }
    )

    proxmox = ProxmoxAnsible(module)

    assert proxmox.proxmox_api is fake_api
    api_cls.assert_called_once_with(
        "proxmox.example.com",
        backend="ssh_paramiko",
        user="root",
        port=22,
        password=None,
        private_key_file="/home/user/.ssh/id_ed25519",
        sudo=True,
    )


def test_connect_ssh_paramiko_defaults_to_port_22(mocker):
    api_cls = mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module = FakeModule(
        {**BASE_PARAMS, "api_backend": "ssh_paramiko", "api_user": "root"}
    )

    ProxmoxAnsible(module)

    assert api_cls.call_args.kwargs["port"] == 22


def test_connect_local_needs_no_host_or_credentials(mocker):
    fake_api = mocker.Mock()
    api_cls = mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI", return_value=fake_api)
    module = FakeModule(
        {
            **BASE_PARAMS,
            "api_backend": "local",
            "api_host": None,
            "api_user": None,
            "api_sudo": True,
        }
    )

    proxmox = ProxmoxAnsible(module)

    assert proxmox.proxmox_api is fake_api
    api_cls.assert_called_once_with(None, backend="local", sudo=True)


def test_connect_local_ignores_paramiko_availability(mocker):
    mocker.patch(f"{MODULE_UTILS}.HAS_PARAMIKO", False)
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module = FakeModule(
        {**BASE_PARAMS, "api_backend": "local", "api_host": None, "api_user": None}
    )

    ProxmoxAnsible(module)  # must not raise

    assert module.failed is None


def test_connect_failure_calls_fail_json(mocker):
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI", side_effect=RuntimeError("boom"))
    module = FakeModule({**BASE_PARAMS, "api_password": "s3cret"})

    with pytest.raises(SystemExit):
        ProxmoxAnsible(module)

    assert "Failed to connect" in module.failed["msg"]


def test_missing_proxmoxer_dependency_fails(mocker):
    mocker.patch(f"{MODULE_UTILS}.HAS_PROXMOXER", False)
    module = FakeModule({**BASE_PARAMS, "api_password": "s3cret"})

    with pytest.raises(SystemExit):
        ProxmoxAnsible(module)

    assert "proxmoxer" in module.failed["msg"]


def test_missing_paramiko_dependency_fails_for_ssh_backend(mocker):
    mocker.patch(f"{MODULE_UTILS}.HAS_PARAMIKO", False)
    module = FakeModule(
        {**BASE_PARAMS, "api_backend": "ssh_paramiko", "api_user": "root"}
    )

    with pytest.raises(SystemExit):
        ProxmoxAnsible(module)

    assert "paramiko" in module.failed["msg"]


def test_missing_paramiko_dependency_is_ignored_for_https_backend(mocker):
    mocker.patch(f"{MODULE_UTILS}.HAS_PARAMIKO", False)
    mocker.patch(f"{MODULE_UTILS}.ProxmoxAPI")
    module = FakeModule({**BASE_PARAMS, "api_password": "s3cret"})

    ProxmoxAnsible(module)  # must not raise

    assert module.failed is None
