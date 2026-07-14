==============================
omedosef.proxmox Release Notes
==============================

.. contents:: Topics

v0.4.0
======

Breaking Changes / Porting Guide
--------------------------------

- all modules - C(api_backend) now defaults to C(local) instead of C(https), since running C(pvesh) on a Proxmox node the play already targets is the recommended pattern and needs no C(api_host), C(api_user), or credentials at all. Playbooks relying on the previous implicit C(https) default must now set C(api_backend=https) explicitly.

Bugfixes
--------

- acl - drop the M() cross-module references in the description, the only place in the collection using that macro, since it was suspected of breaking documentation rendering on the Galaxy website; replaced with plain C() text.

v0.3.0
======

New Modules
-----------

- omedosef.proxmox.acl - Manage Proxmox VE ACL entries.
- omedosef.proxmox.group - Manage Proxmox VE groups.
- omedosef.proxmox.role - Manage Proxmox VE roles.
- omedosef.proxmox.user_token - Manage Proxmox VE API tokens for a user.

v0.2.1
======

Minor Changes
-------------

- user - clarify in the documentation that C(password) is forwarded to the realm's own password mechanism for non-C(pve) realms rather than being ignored.

Bugfixes
--------

- user - surface a clear, actionable error when setting a password for a non-C(pve)-realm user (for example C(pam)) fails because the underlying system/LDAP/AD account does not exist yet, instead of only the raw Proxmox API error.

v0.2.0
======

New Modules
-----------

- omedosef.proxmox.user - Manage Proxmox VE users.

v0.1.3
======

v0.1.2
======

v0.1.1
======

v0.1.0
======

New Modules
-----------

- omedosef.proxmox.version_info - Retrieve Proxmox VE API version information.
