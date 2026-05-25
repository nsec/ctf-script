# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [5.0.0] - 2026-05-09

### Breaking changes

- **`ctf deploy` no longer passes `ansible_incus_remote` as an Ansible extra variable.**
  `ansible-playbook` with `-e ansible_incus_remote=<value>` overrides inventory on every host, which broke mixed containers / VMs deployments.

  **Migration:** Do not depend on `ansible_incus_remote` being injected by deploy for
  playbook-wide VM/cluster targeting.

  Use something like:
  ```
    vars:
      ansible_incus_remote: "{{ ansible_incus_container_remote if ansible_incus_container_remote else 'local' }}"
  ```

[5.0.0]: https://github.com/nsec/ctf-script/compare/v4.6.2...v5.0.0
