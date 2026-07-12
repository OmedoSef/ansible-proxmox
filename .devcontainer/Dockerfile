# Built on top of OmedoSef's own devcontainer base images:
# https://github.com/OmedoSef/DevContainers (ghcr.io/omedosef/python -> ghcr.io/omedosef/debian:13)
# That image already ships a non-root "vscode" user (uid/gid 1000, zsh, passwordless sudo).
FROM ghcr.io/omedosef/python:3.14

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        openssh-client \
        sshpass \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt /tmp/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements-dev.txt

# The base image's Python prefix (e.g. /opt/python/3.14.3/bin) is only on PATH
# via an image ENV var, which Debian's /etc/profile resets for login shells
# (zsh is the default shell here). Symlink installed console scripts into
# /usr/local/bin, same convention the base image already uses for python/pip.
RUN scripts_dir="$(python -c 'import sysconfig; print(sysconfig.get_path("scripts"))')" \
    && for f in "${scripts_dir}"/*; do ln -sf "$f" "/usr/local/bin/$(basename "$f")"; done

USER vscode
