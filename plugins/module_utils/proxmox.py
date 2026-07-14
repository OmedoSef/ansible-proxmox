# -*- coding: utf-8 -*-
# Copyright (c) 2026, Romain VOLPI <romain.volpi@omedo.net>
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

import traceback

from ansible.module_utils.basic import env_fallback, missing_required_lib

PROXMOXER_IMP_ERR = None
try:
    from proxmoxer import ProxmoxAPI

    HAS_PROXMOXER = True
except ImportError:
    HAS_PROXMOXER = False
    PROXMOXER_IMP_ERR = traceback.format_exc()

# proxmoxer also ships an "openssh" backend (backend="openssh"), but it depends
# on the openssh_wrapper package, which imports the "pipes" stdlib module
# removed in Python 3.13. ssh_paramiko (pure-Python, via paramiko) is the
# supported SSH backend here.
#
# Checked eagerly (rather than left to proxmoxer/ProxmoxAPI) because
# proxmoxer.backends.ssh_paramiko calls sys.exit(1) at import time when
# paramiko is missing instead of raising, which would otherwise kill the
# module process before we get a chance to fail_json() a clean error.
PARAMIKO_IMP_ERR = None
try:
    import paramiko  # pylint: disable=unused-import  # presence check only, see comment above

    HAS_PARAMIKO = True
except ImportError:
    HAS_PARAMIKO = False
    PARAMIKO_IMP_ERR = traceback.format_exc()

DEFAULT_HTTPS_PORT = 8006
DEFAULT_SSH_PORT = 22


def proxmox_auth_argument_spec():
    """Argument spec shared by every module authenticating against the Proxmox VE API.

    Every option falls back to a PROXMOX_* environment variable when neither
    set directly on the task nor via module_defaults, letting CI/CD runners
    inject credentials without touching playbooks. Precedence (highest to
    lowest): task argument > module_defaults > environment variable > spec
    default.
    """
    return dict(
        api_host=dict(type="str", fallback=(env_fallback, ["PROXMOX_API_HOST"])),
        api_port=dict(type="int", fallback=(env_fallback, ["PROXMOX_API_PORT"])),
        api_backend=dict(
            type="str",
            choices=["https", "ssh_paramiko", "local"],
            default="https",
            fallback=(env_fallback, ["PROXMOX_API_BACKEND"]),
        ),
        api_user=dict(type="str", fallback=(env_fallback, ["PROXMOX_API_USER"])),
        api_password=dict(
            type="str", no_log=True, fallback=(env_fallback, ["PROXMOX_API_PASSWORD"])
        ),
        api_token_id=dict(
            type="str", fallback=(env_fallback, ["PROXMOX_API_TOKEN_ID"])
        ),
        api_token_secret=dict(
            type="str",
            no_log=True,
            fallback=(env_fallback, ["PROXMOX_API_TOKEN_SECRET"]),
        ),
        api_ssh_private_key_file=dict(
            type="path", fallback=(env_fallback, ["PROXMOX_API_SSH_PRIVATE_KEY_FILE"])
        ),
        api_sudo=dict(
            type="bool", default=False, fallback=(env_fallback, ["PROXMOX_API_SUDO"])
        ),
        validate_certs=dict(
            type="bool",
            default=True,
            fallback=(env_fallback, ["PROXMOX_VALIDATE_CERTS"]),
        ),
    )


def proxmox_required_together():
    return [("api_token_id", "api_token_secret")]


def proxmox_required_if():
    return [
        # https and ssh_paramiko reach a Proxmox node over the network, so
        # they need to know where/who to connect as. local runs pvesh
        # directly in the current process - typically because the play
        # already targets the Proxmox node over Ansible's own SSH connection
        # - so neither applies.
        ("api_backend", "https", ("api_host", "api_user"), False),
        ("api_backend", "ssh_paramiko", ("api_host", "api_user"), False),
        # Password/token authentication is mandatory for the REST API
        # (https) backend. ssh_paramiko can fall back to an SSH agent or the
        # user's default keys, and local needs no credentials at all.
        ("api_backend", "https", ("api_password", "api_token_id"), True),
    ]


class ProxmoxAnsible:
    """Base class providing an authenticated proxmoxer client to Proxmox modules."""

    def __init__(self, module):
        self.module = module

        if not HAS_PROXMOXER:
            module.fail_json(
                msg=missing_required_lib("proxmoxer"), exception=PROXMOXER_IMP_ERR
            )

        if module.params["api_backend"] == "ssh_paramiko" and not HAS_PARAMIKO:
            module.fail_json(
                msg=missing_required_lib("paramiko"), exception=PARAMIKO_IMP_ERR
            )

        self.proxmox_api = self._connect()

    def _connect(self):
        params = self.module.params
        backend = params["api_backend"]
        build_kwargs = {
            "https": self._https_kwargs,
            "ssh_paramiko": self._ssh_paramiko_kwargs,
            "local": self._local_kwargs,
        }[backend]

        try:
            return ProxmoxAPI(
                params.get("api_host"), backend=backend, **build_kwargs(params)
            )
        except (
            Exception
        ) as exc:  # noqa: BLE001 - surface any connection/auth failure to the user
            target = params.get("api_host") or "localhost"
            self.module.fail_json(
                msg=f"Failed to connect to the Proxmox API at {target} (backend={backend}): {exc}"
            )

    @staticmethod
    def _https_kwargs(params):
        kwargs = {
            "user": params["api_user"],
            "port": params["api_port"] or DEFAULT_HTTPS_PORT,
            "verify_ssl": params["validate_certs"],
        }
        if params.get("api_token_id"):
            kwargs["token_name"] = params["api_token_id"]
            kwargs["token_value"] = params["api_token_secret"]
        else:
            kwargs["password"] = params["api_password"]
        return kwargs

    @staticmethod
    def _ssh_paramiko_kwargs(params):
        # Proxmox VE's equivalent of Ansible's "become": prefixes every pvesh
        # command run over SSH with sudo. validate_certs/tokens don't apply
        # to this backend (there's no TLS handshake or REST auth involved).
        return {
            "user": params["api_user"],
            "port": params["api_port"] or DEFAULT_SSH_PORT,
            "password": params.get("api_password"),
            "private_key_file": params.get("api_ssh_private_key_file"),
            "sudo": params["api_sudo"],
        }

    @staticmethod
    def _local_kwargs(params):
        # Runs pvesh directly on the current host via subprocess: no network
        # connection and no credentials of any kind. Meant for plays that
        # already target the Proxmox node itself over Ansible's own
        # connection (normal inventory + become), rather than reaching a
        # remote node from the control node.
        return {"sudo": params["api_sudo"]}

    @staticmethod
    def _filter_none_values(params):
        """Drop unset (None) entries, so callers only send fields the user
        actually specified rather than clobbering the rest with nulls.
        """
        return {key: value for key, value in params.items() if value is not None}

    @staticmethod
    def compute_changes(current, desired, fields, normalize=None):
        """Return only the fields that differ, keyed by field name -> desired raw value.

        Fields left unset (None) in desired are skipped, so callers only
        compare/apply what the user actually specified. normalize(field,
        value), when given, lets a caller reconcile representations that
        differ between the API and the module's own input (int vs bool,
        comma string vs list, unordered list, ...) before comparing.
        """
        if normalize is None:

            def normalize(field, value):
                return value

        changes = {}
        for field in fields:
            if desired.get(field) is None:
                continue
            if normalize(field, current.get(field)) != normalize(field, desired[field]):
                changes[field] = desired[field]
        return changes
