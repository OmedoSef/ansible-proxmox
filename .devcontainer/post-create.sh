#!/usr/bin/env bash
# The workspace is bind-mounted directly at
# ~/.ansible/collections/ansible_collections/omedosef/proxmox (see
# workspaceMount/workspaceFolder in devcontainer.json), which is the physical
# path ansible-test and the Ansible collection loader require. No symlink
# juggling needed here.
set -euo pipefail

WORKSPACE_DIR="$(pwd)"

git config --global --add safe.directory "${WORKSPACE_DIR}"

pre-commit install --install-hooks

echo "Collection ready at: ${WORKSPACE_DIR}"
