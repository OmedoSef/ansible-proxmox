#!/usr/bin/env bash
# Links the checked-out repo into the ansible_collections/<namespace>/<name>
# path that ansible-test and the Ansible collection loader require, since the
# repo is cloned under its own name rather than that nested path.
set -euo pipefail

NAMESPACE="omedosef"
COLLECTION="proxmox"
WORKSPACE_DIR="$(pwd)"
COLLECTIONS_ROOT="${HOME}/.ansible/collections/ansible_collections"
NAMESPACE_DIR="${COLLECTIONS_ROOT}/${NAMESPACE}"
COLLECTION_LINK="${NAMESPACE_DIR}/${COLLECTION}"

mkdir -p "${NAMESPACE_DIR}"

if [ ! -e "${COLLECTION_LINK}" ]; then
    ln -s "${WORKSPACE_DIR}" "${COLLECTION_LINK}"
fi

git config --global --add safe.directory "${WORKSPACE_DIR}"

pre-commit install --install-hooks

echo "Collection available at: ${COLLECTION_LINK}"
echo "Run ansible-test / ansible-lint from that path (or export ANSIBLE_COLLECTIONS_PATH as configured)."
