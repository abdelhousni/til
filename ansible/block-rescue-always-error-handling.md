# Handling deployment failures with Ansible's block/rescue/always

Saw [a LinkedIn post](https://www.linkedin.com/posts/seifallah-bennour_ansible-devops-infrastructure-activity-7498706753606373376-hn1h) comparing Ansible's `block`/`rescue`/`always` to try/catch — deploy, roll back automatically on failure, alert the team, clean up regardless. It's a real, built-in Ansible feature ([current docs](https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_blocks.html)), and it's more precise than "try/catch" once you look at what actually triggers each part.

The vocabulary, for anyone new to Ansible:
- A **playbook** is a YAML file of **plays**; a play maps a set of hosts to a list of **tasks**.
- A **task** calls one **module**, the unit of work that does something on the host (`ansible.builtin.git` checks out a repository, `ansible.builtin.systemd` manages a service). Each task comes back `ok`, `changed`, `failed`, `skipped` or `unreachable`.
- Modules ship in **collections**. `ansible.builtin` comes with Ansible itself; `community.general`, used below for Slack, is a separate collection (`ansible-galaxy collection install community.general`), though the full `ansible` package bundles it.
- A **block** groups tasks so they can share settings and error handling.

## The shape of it

```yaml
tasks:
  - name: Deploy new version
    block:
      - name: Fetch latest code
        ansible.builtin.git:
          repo: https://github.com/example/app.git
          dest: /srv/app
          version: main

      - name: Restart service
        ansible.builtin.systemd:
          name: myapp
          state: restarted
    rescue:
      - name: Roll back to last known-good version
        ansible.builtin.git:
          repo: https://github.com/example/app.git
          dest: /srv/app
          version: v1.2.0

      - name: Restart with the stable version
        ansible.builtin.systemd:
          name: myapp
          state: restarted

      - name: Alert the team
        community.general.slack:
          token: "{{ slack_token }}"
          msg: "Deploy failed, rolled back to v1.2.0"
    always:
      - name: Clear temp cache
        ansible.builtin.file:
          path: /tmp/app-cache
          state: absent
```

When a task in `block` fails, the remaining `block` tasks are skipped and `rescue` runs. `rescue` only runs if a task in `block` actually executes and comes back `failed`. `always` runs regardless — success, rescue, or a rescue that fails too.

## Two things that aren't obvious from "it's like try/catch"

**Not every failure triggers `rescue`.** Per the docs: "errors caused by invalid task definitions and unreachable hosts do not trigger the rescue or always sections of a block." A host that's down, or a task with a genuinely broken module argument, never gets far enough to produce the kind of `failed` result `rescue` reacts to — it's not the same category of failure as "the command ran and exited non-zero."

**A successful rescue is counted as `rescued`, not `failed`.** Ansible reverts the task's failed status and continues the play as though it had succeeded. The docs add that "Ansible still reports a failure in the playbook statistics", but in the *play recap* — the per-host summary line `ansible-playbook` prints at the end — it shows up in its own column. With ansible-core 2.21.1, a block whose task fails and whose `rescue` succeeds ends with:

```text
localhost : ok=2 changed=0 unreachable=0 failed=0 skipped=0 rescued=1 ignored=0
```

and `ansible-playbook` exits with 0. If the rescue task fails too, `always` still runs, but the recap shows `failed=1 rescued=1` and the exit code is 2. So a CI job that only checks the exit code sees a rolled-back deploy as a success. To notice rollbacks, look for `rescued=` above 0 in the recap, or have `rescue` send the alert itself, as below.

## Making the alert actually say what broke

Rather than a generic "deploy failed" message, `rescue` gets two special variables pointing at exactly what triggered it:

```yaml
rescue:
  - name: Alert the team with the real failure
    community.general.slack:
      token: "{{ slack_token }}"
      msg: "{{ ansible_failed_task.name }} failed: {{ ansible_failed_result.msg | default('no message') }}"
```

`ansible_failed_task` is the task that returned `failed` (`.name` for its name), and `ansible_failed_result` is that task's full return value. Normally, getting a task's result takes `register: result` on the task, which saves its return value in a variable, and then a `when: result is failed` condition on the next task. `rescue` already hands it to you. With a `command` task that ran `/bin/false`, the message above reads `Step that fails failed: The command exited with a non-zero return code.`, and `ansible_failed_result.rc` is `1`.

## Sources

- Ansible docs: [Blocks](https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_blocks.html), from `docs/docsite/rst/playbook_guide/playbooks_blocks.rst` in [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation).
- The recap lines and the failure message were produced with ansible-core 2.21.1 against `localhost`, once with a rescue that succeeds and once with a rescue that fails.
