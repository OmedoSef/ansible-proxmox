# -*- coding: utf-8 -*-
# Copyright (c) 2026, Romain VOLPI <romain.volpi@omedo.net>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

import pytest
from ansible_collections.omedosef.proxmox.plugins.modules.version_info import (
    ProxmoxVersionInfoAnsible,
)
from proxmoxer.core import ResourceException


class FakeModule:
    def __init__(self, params):
        self.params = params
        self.exited = None
        self.failed = None

    def exit_json(self, **kwargs):
        self.exited = kwargs
        raise SystemExit(0)

    def fail_json(self, **kwargs):
        self.failed = kwargs
        raise SystemExit(1)


@pytest.fixture
def module_params():
    return {
        "api_host": "proxmox.example.com",
        "api_port": None,
        "api_backend": "https",
        "api_user": "root@pam",
        "api_password": "s3cret",
        "api_token_id": None,
        "api_token_secret": None,
        "api_ssh_private_key_file": None,
        "api_sudo": False,
        "validate_certs": True,
    }


@pytest.fixture
def proxmox(mocker, module_params):
    mocker.patch(
        "ansible_collections.omedosef.proxmox.plugins.module_utils.proxmox.ProxmoxAPI"
    )
    return ProxmoxVersionInfoAnsible(FakeModule(module_params))


def test_get_version_returns_api_payload(proxmox):
    proxmox.proxmox_api.version.get.return_value = {
        "version": "8.3.2",
        "release": "8.3",
        "repoid": "3e76eec21c4a14a3",
    }

    result = proxmox.get_version()

    assert result["version"] == "8.3.2"
    proxmox.proxmox_api.version.get.assert_called_once_with()


def test_get_version_failure_calls_fail_json(proxmox):
    proxmox.proxmox_api.version.get.side_effect = ResourceException(
        500, "Internal Server Error", "boom"
    )

    with pytest.raises(SystemExit):
        proxmox.get_version()

    assert "Failed to retrieve the Proxmox VE version" in proxmox.module.failed["msg"]
