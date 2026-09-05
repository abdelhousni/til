# Using the Foreman/Satellite dynamic inventory plugin

`theforeman.foreman.foreman` pulls hosts straight out of Foreman (or Red Hat Satellite, which is built on it) as live Ansible inventory — no manually maintained host list to fall out of sync with what's actually registered.

## Install and enable it

```sh
ansible-galaxy collection install theforeman.foreman
```

It depends on the Python `requests` library, so whichever Python interpreter Ansible runs under needs that installed too — easy to miss if Ansible is running from a venv that doesn't have it.

Inventory plugins aren't auto-enabled just by installing the collection; `ansible.cfg` needs to list it explicitly:

```ini
[inventory]
enable_plugins = theforeman.foreman.foreman
```

## The config file

The filename itself is what Ansible uses to recognize this as a Foreman inventory source — it has to end in `foreman.yml` or `foreman.yaml`, not just live in an `inventory/` directory:

```yaml
# inventory.foreman.yml
plugin: theforeman.foreman.foreman
url: https://foreman.example.com
user: ansibleinventory
password: changeme
validate_certs: true
```

Test it directly without running a playbook:

```sh
ansible-inventory -i inventory.foreman.yml --graph
```

## The gotcha: two different APIs underneath

The plugin defaults to `use_reports_api: true`, which is faster once you have more than a handful of hosts — but it only works if the **`foreman_ansible` plugin is installed on the Foreman server itself**. Point this at a plain Foreman or Satellite install that doesn't have that server-side plugin, and the Reports API path fails or comes back empty, with nothing in the error that obviously points at "wrong API." Setting `use_reports_api: false` falls back to the older Hosts API, which works everywhere but is slower against a large inventory.

## Other options worth knowing

```yaml
host_filters: 'organization="Web Engineering"'
want_hostcollections: true
want_facts: true
group_prefix: foreman_   # default -- every Foreman-derived group gets this prefix
```

`host_filters` takes Foreman's own search syntax (the same query language as the web UI's search box), so it's worth testing a filter there first before dropping it into YAML.
