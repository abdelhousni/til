# Secrets in the inventory: vault.yml next to vars.yml, with plaintext aliases

Tenth entry in the Ansible inventory from scratch series. [Item 8](inventory-where-a-variable-should-live.md) put desired state in the inventory's `group_vars/` and `host_vars/`, and some of that state is secret: a database password, an API token. *Ansible Vault* encrypts it so the repository holds ciphertext, decrypted at run time with a *vault password*. [What Ansible Vault actually encrypts](what-ansible-vault-actually-encrypts.md) explains the tool itself, the two ways to encrypt, and where its protection stops. This entry stays in the inventory: it compares three layouts for one PostgreSQL password, measures what each reveals to a search, to `ansible-inventory`, to a playbook's output and to `git diff`, then splits prod and staging secrets with vault IDs. Everything below ran with ansible-core 2.21.4.

## Three layouts for one password

- **Alias:** `group_vars/postgresql/vault.yml` is encrypted whole and holds `vault_postgresql_password`. Next to it, a plaintext `vars.yml` holds every variable the role reads, the secret as an alias: `postgresql_password: "{{ vault_postgresql_password }}"`. It's the layout the `write-content` skill used for these examples generates, `vars.yml` beside `vault.yml` in each group's directory.
- **No alias:** `postgresql_password` is defined only inside the encrypted `vault.yml`.
- **Inline:** `ansible-vault encrypt_string … --name postgresql_password` produced one encrypted value, a `!vault` block, inside an otherwise plaintext `vars.yml`.

The vault password in the example is a committed test value, encrypting dummy data, so the example runs in CI. A real vault password never goes in the repository: a password manager, a CI secret or a vault client script holds it.

## What each layout reveals

| Question | Alias | No alias | Inline |
|---|---|---|---|
| `grep -r postgresql_password` finds | `vars.yml` | nothing | `vars.yml` |
| `ansible-inventory --host db1`, no vault password | fails, exit 4 | fails, exit 4 | works; the value is an encrypted blob |
| `ansible-inventory --host db1`, with the password | the secret in clear, as `vault_postgresql_password` | the secret in clear | still an encrypted blob |

- **Without an alias, the variable's name is encrypted too.** Nobody can find where `postgresql_password` comes from without the vault password; with the alias, `vars.yml` says where every variable is defined and which ones are secret.
- **An encrypted file stops `ansible-inventory` without the password:** *"Attempting to decrypt but no vault secrets found"*. [Item 6](inventory-checking-with-ansible-inventory.md)'s checks then need the vault password, and the output prints the secrets.
- **Inline values never come out of `ansible-inventory` in clear**, with or without the password: it printed `{"__ansible_vault": "$ANSIBLE_VAULT;1.1;AES256…"}` both times. The alias in `vars.yml` stayed unrendered too, `"{{ vault_postgresql_password }}"`; only the encrypted file's own variable came out decrypted.

## The playbook output

A task that prints the password, `msg: "password is {{ postgresql_password }}"`, printed it in clear: the alias resolves at run time like any variable. The same task with `no_log: true` printed only `ok: [db1]`. Vault protects the file; `no_log` is what protects the output of every task that uses the secret.

## What git sees

Changing the password in the encrypted `vault.yml`, decrypted, edited and re-encrypted, changed **6 of its 7 lines**: everything but the header, because each encryption uses a new random salt. `ansible-vault rekey`, which re-encrypts with a new vault password, did the same with the value unchanged. A reviewer sees that `vault.yml` changed and nothing more, which is why the alias layout keeps every non-secret setting in `vars.yml`, where diffs stay readable. In the inline layout, only the `!vault` block changes; the lines around it stay plaintext, though an inline value can't be rekeyed in place, as the vault entry explains.

## Prod and staging with vault IDs

A *vault ID* labels encrypted content with the name of the password that encrypted it: `ansible-vault encrypt --vault-id prod@<password file>` wrote the header `$ANSIBLE_VAULT;1.2;AES256;prod`. With prod and staging each in its own `group_vars/<env>/vault.yml`:

| Passwords given | Hosts | Result |
|---|---|---|
| `--vault-id prod@… --vault-id staging@…` | all | exit 0 |
| `--vault-id prod@…` | `--limit prod` | exit 0 |
| `--vault-id prod@…` | all | exit 4, *"Decryption failed (no vault secrets were found that could decrypt)"* |

Ansible decrypts the files of the hosts it targets: with `--limit prod`, the staging file was never read, so its password wasn't needed. A run on every host fails at the start without each environment's password, before any task, which is the safe way round. [Item 5](inventory-environments-directories-or-groups.md)'s separate inventory directories get the same separation from `-i` alone, with one vault password per directory.

## In short

- **Layout:** `group_vars/<group>/vault.yml`, encrypted, with `vault_`-prefixed names; `vars.yml` beside it, plaintext, with an alias for each secret.
- **`ansible-inventory` with the vault password prints the secrets** of encrypted files; inline `!vault` values stay encrypted.
- **`no_log: true`** on every task that uses a secret.
- **Expect whole-file diffs** on any change to `vault.yml`, rekeys included.
- **Vault IDs per environment:** a missing password stops the run unless `--limit` keeps to the hosts it can decrypt.

## The example repository

The series' companion repository, [abdelhousni/ansible-inventory-series](https://github.com/abdelhousni/ansible-inventory-series/tree/main/10-secrets-in-the-inventory), holds the three layouts, the vault ID inventory and their test passwords. `run.sh` greps, runs `ansible-inventory` with and without the password, runs a playbook that uses the secret with and without `no_log`, changes and rekeys a copy of `vault.yml` in its `out/` directory, and runs the vault ID cases; it prints whether the secret appears in clear, never the ciphertext. Its CI runs it on every push and compares the output with the expected one.

## Sources

- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `vault_guide/vault_encrypting_content.rst` and `vault_guide/vault_managing_passwords.rst`.
- ansible-core 2.21.4: `ansible-vault` and `ansible-inventory`, run as shown.
- Every result above came from ansible-core 2.21.4 on 2026-10-03, on the local machine.
