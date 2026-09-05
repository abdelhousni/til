# Targeting hosts the same way, whether the inventory is static or dynamic

The host patterns Ansible accepts on the command line and in a playbook's `hosts:` line don't care where the hosts came from — a plain INI file, a YAML static inventory, or a dynamic plugin like [the Foreman one](foreman-dynamic-inventory-plugin.md) all get flattened into the same in-memory host/group graph first. Patterns operate on that graph, not on the source file. This is on the current stable stack (ansible-core 2.20, Python 3.12+ on the controller) but the pattern syntax itself hasn't changed in years.

## The patterns

```sh
ansible all --list-hosts                    # everything
ansible webservers --list-hosts             # one group
ansible web01.example.com --list-hosts      # one host
ansible 'webservers,dbservers' --list-hosts # union (OR) -- comma or colon both work
ansible 'webservers:&datacenter1' --list-hosts   # intersection (AND)
ansible 'webservers:!staging' --list-hosts       # exclusion (NOT)
ansible '*.example.com' --list-hosts             # wildcard
ansible '~(web|db).*\.example\.com' --list-hosts # regex, note the leading ~
```

`--list-hosts` just prints who a pattern matches without touching anything — the safest way to sanity-check a pattern before pointing a real playbook run at it.

## Limiting at runtime without touching the playbook

A playbook's `hosts: all` (or `hosts: webservers`) sets the *maximum* possible target set; `--limit` (`-l` for short) narrows it further at invocation time, no editing required:

```sh
ansible-playbook site.yml --limit datacenter2
ansible-playbook site.yml -l 'webservers:&datacenter1'
```

Same pattern syntax as above works here too. `--limit @retry_hosts.txt` also accepts a file — the one Ansible itself writes after a failed run (`site.retry`), for rerunning against just the hosts that failed.

## Where this matters most: mixed static + dynamic sources

`-i` can be passed more than once, or pointed at a directory containing both a static file and a dynamic plugin config side by side:

```
inventory/
├── static-hosts.ini
└── production.foreman.yml
```

```sh
ansible-playbook site.yml -i inventory/
```

Ansible merges both sources into one graph before any pattern is applied — a group defined in the static file and a same-named group produced by the Foreman plugin combine, and `--limit`/`hosts:` patterns see the union transparently. This is exactly why `ansible-inventory --graph` (from [the Foreman TIL](foreman-dynamic-inventory-plugin.md)) is worth running whenever mixing sources — it's the only way to see what the *combined* graph actually looks like, since no single file on disk shows it.
