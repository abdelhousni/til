# Handling deployment failures with Ansible's block/rescue/always

Saw [a LinkedIn post](https://www.linkedin.com/posts/seifallah-bennour_ansible-devops-infrastructure-activity-7498706753606373376-hn1h) comparing Ansible's `block`/`rescue`/`always` to try/catch — deploy, roll back automatically on failure, alert the team, clean up regardless. It's a real, built-in Ansible feature ([current docs](https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_blocks.html)), and it's more precise than "try/catch" once you look at what actually triggers each part.

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

`rescue` only runs if a task in `block` actually executes and comes back `failed`. `always` runs regardless — success, rescue, or otherwise.

## Two things that aren't obvious from "it's like try/catch"

**Not every failure triggers `rescue`.** Per the docs: "errors caused by invalid task definitions and unreachable hosts do not trigger the rescue or always sections of a block." A host that's down, or a task with a genuinely broken module argument, never gets far enough to produce the kind of `failed` result `rescue` reacts to — it's not the same category of failure as "the command ran and exited non-zero."

**A successful rescue still counts as a failure in the stats.** If `rescue` runs and completes cleanly, Ansible reverts the task's status and continues the play as though the original task had succeeded — but "Ansible still reports a failure in the playbook statistics" at the end of the run. So a green rollback doesn't mean a green run: check the actual play recap, not just whether the playbook kept going.

## Making the alert actually say what broke

Rather than a generic "deploy failed" message, `rescue` gets two special variables pointing at exactly what triggered it:

```yaml
rescue:
  - name: Alert the team with the real failure
    community.general.slack:
      token: "{{ slack_token }}"
      msg: "{{ ansible_failed_task.name }} failed: {{ ansible_failed_result.msg | default('no message') }}"
```

`ansible_failed_task` is the task that returned `failed` (`.name` for its name), and `ansible_failed_result` is that task's full return value — the same data you'd get from `register`-ing it. No need to manually `register` and `when: result is failed` your way to the same information; `rescue` already hands it to you.
