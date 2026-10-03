# Testing the inventory in CI, with a JSON Schema and policy checks

Twenty-fifth entry, and the last, in the Ansible inventory from scratch series. [Item 6](inventory-checking-with-ansible-inventory.md) used `ansible-inventory` to look at what Ansible sees, by hand. This entry makes that look automatic: a test that runs on every change to the inventory and fails when a variable is missing, has the wrong type or value, holds a secret in clear, or when a host sits in the wrong groups. *CI*, continuous integration, means running such tests on every push or pull request, here with GitHub Actions, GitHub's CI service. Everything below ran with ansible-core 2.21.4 and check-jsonschema 0.38.2.

## The inventory under test

The series' stack: `app` and `db` are functional groups, named for what the hosts do, and `prod` and `staging` are environment groups, as in [item 5](inventory-environments-directories-or-groups.md). Four hosts, app1 and db1 in prod, stg-app1 and stg-db1 in staging. `group_vars/app/` sets `app_port` and `app_log_level`, `group_vars/db/` sets `postgresql_port`, `postgresql_max_connections` and `postgresql_password`, and each environment group sets `env`.

The password follows [item 10](inventory-secrets-vault-yml-aliases.md): `postgresql_password: "{{ vault_postgresql_password }}"` in a plaintext `vars.yml`, and the real value in `vault.yml`. One change: `vault.yml` isn't encrypted as a whole, each value in it is encrypted on its own with `ansible-vault encrypt_string`. The reason is the CI job, which shouldn't hold the vault password:

- with a `vault.yml` encrypted as a whole, `ansible-inventory --list` without the password failed: *Attempting to decrypt but no vault secrets found*;
- with values encrypted one by one, it loaded, and printed each one as an object, `{"__ansible_vault": "$ANSIBLE_VAULT;1.1;AES256\n…"}`.

`ansible-inventory --list` doesn't render templates either: `postgresql_password` came out as the string `{{ vault_postgresql_password }}`. Both are what a test for secrets needs to see.

## Check 1: a JSON Schema for the variables

A *JSON Schema* is a JSON document that describes what another JSON document must contain: which keys are required (`required`), the type of each value (`type`), a list of allowed values (`enum`), a regular expression a string must match (`pattern`), and rules for every key whose name matches a pattern (`patternProperties`). A validator reads both and lists every place the document breaks the schema. The example uses [check-jsonschema](https://github.com/python-jsonschema/check-jsonschema), a command-line validator built on the Python `jsonschema` library, installed with pip and pinned in the repository's `requirements.txt`.

`ansible-inventory --list` gives each host's merged variables under `_meta.hostvars`, and each group's hosts, but not the groups of a host next to its variables. A schema can't say "db hosts need `postgresql_port`" on that shape, so the test reshapes it first with `jq`, a command-line JSON processor, into `{group: {host: variables}}`:

```sh
ansible-inventory -i inventory --list >list.json
jq '._meta.hostvars as $hv
    | (del(._meta) | with_entries(select(.value.hosts) | .value = (.value.hosts | map({(.): $hv[.]}) | add)))
      + {all: $hv}' list.json >inventory.json
check-jsonschema --schemafile schema/inventory.schema.json inventory.json
```

`--list` rather than `--list --export`: [item 6](inventory-checking-with-ansible-inventory.md) showed that `--export` gives variables per group as they're written, and a test should check what each host ends up with, after [item 9](inventory-precedence-depth-and-group-priority.md)'s precedence.

The schema then holds one definition per group: every host needs `env`, one of `prod` and `staging`; app hosts need an integer `app_port` between 1024 and 65535 and an `app_log_level` among `debug`, `info`, `warning` and `error`; db hosts need `postgresql_port`, `postgresql_max_connections` and `postgresql_password`, the first two integers. The secret rule is two `patternProperties` for every host:

```json
"patternProperties": {
  "^vault_": {"$ref": "#/$defs/encrypted"},
  "^(?!vault_).*(password|secret|token)$": {"anyOf": [{"$ref": "#/$defs/alias"}, {"$ref": "#/$defs/encrypted"}]}
}
```

`encrypted` is an object with only `__ansible_vault`, a string starting with `$ANSIBLE_VAULT;`, and `alias` a string matching `^\{\{ vault_[a-z0-9_]+ \}\}$`. Any `vault_` variable has to be encrypted, and any other variable named like a secret has to be an alias to one, so a new secret is covered without editing the schema.

What each broken inventory printed, path first:

| Case | check-jsonschema said |
|---|---|
| `postgresql_max_connections` left out | `$.db.db1: 'postgresql_max_connections' is a required property`, and the same for stg-db1 |
| `postgresql_port: "5432"`, quoted | `$.db.db1.postgresql_port: '5432' is not of type 'integer'` |
| `env: stage`, `app_log_level: verbose` | `$.all['stg-app1'].env: 'stage' is not one of ['prod', 'staging']`, and `'verbose' is not one of ['debug', 'info', 'warning', 'error']` |
| `vault_postgresql_password: S3cret-db` in clear | `$.all.db1.vault_postgresql_password: 'S3cret-db' is not of type 'object'` |

Each message names the group and the host, and check-jsonschema exited 1 with every error listed, not only the first.

## Check 2: rules a schema can't express

A schema validates one value at a time. It can't compare groups with each other, and two rules of this inventory are about exactly that: no host is left only in `ungrouped`, the group of hosts in no other group ([item 1](inventory-hosts-groups-all-ungrouped.md)), and every host is in exactly one environment group. They're `assert` tasks in a playbook on localhost, which reads the `groups` variable, every group with its hosts, and each host's `group_names`, and connects to no host:

```yaml
- name: Every host is in exactly one environment group
  ansible.builtin.assert:
    that: hostvars[item].group_names | intersect(policy_env_groups) | length == 1
    fail_msg: >-
      {{ item }} is in {{ hostvars[item].group_names | intersect(policy_env_groups) | length }}
      of {{ policy_env_groups | join(', ') }}
    quiet: true
  loop: "{{ groups['all'] }}"
```

With `policy_env_groups: [prod, staging]`, it printed:

| Case | The schema | The policy playbook |
|---|---|---|
| app1 copied into staging, left in prod | passed | `app1 is in 2 of prod, staging` |
| app2 added to `app`, in no environment | `$.all.app2: 'env' is a required property` | `app2 is in 0 of prod, staging` |
| db2 added under `all`, in no group | `$.all.db2: 'env' is a required property` | `db2 in no group but all` |

The first row is why both checks exist: app1 got `env` from both groups, `staging` won, and its variables were valid. The other two the schema catches too, through a missing `env`, but only the playbook says what is wrong with the groups.

## The CI job

`check.sh` runs both checks on one inventory and exits 1 if either fails, which fails the job. The example's `ci/inventory.yml` is a GitHub Actions workflow that installs ansible-core and check-jsonschema from the locked `requirements.txt` and runs `check.sh` on every pull request and every push to `main`. It's a file to copy into the `.github/workflows/` directory of an inventory repository: GitHub only runs workflows from there, so it isn't active in the companion repository, whose own CI runs `run.sh` instead. No secret is configured in the job, since nothing needs the vault password.

When the inventory isn't one directory, the same test works on whatever `-i` gets: several sources ([item 14](inventory-several-sources-load-order.md)) or an inventory plugin. A plugin that calls an API needs that API reachable from CI, or a fixture standing in for it.

## The example

The series' companion repository, [abdelhousni/ansible-inventory-series](https://github.com/abdelhousni/ansible-inventory-series/tree/main/25-testing-the-inventory-in-ci), holds the inventory, the schema, the policy playbook, `check.sh` and the workflow. Each failure case in `broken/` holds only the files that differ from the good inventory; `run.sh` lays each over a copy of it, runs `check.sh`, and prints the messages above and the exit codes. Its CI runs it on every push and compares the output with the expected one.

## Sources

- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `vault_guide/vault_encrypting_content.rst` (*Encrypting individual variables with Ansible Vault*), `reference_appendices/special_variables.rst` (`groups`, `group_names`).
- GitHub docs, [Workflow syntax for GitHub Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax): workflows live in `.github/workflows/`.
- [JSON Schema](https://json-schema.org/), the 2020-12 draft the schema declares.
- [check-jsonschema](https://github.com/python-jsonschema/check-jsonschema) 0.38.2.
- Every result above came from ansible-core 2.21.4 on 2026-10-03, on the local machine.
