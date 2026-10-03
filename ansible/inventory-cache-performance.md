# The inventory cache and performance: request counts, want_facts and timeouts

Twentieth entry in the Ansible inventory from scratch series. The previous entry, [When the inventory cache lies](inventory-cache-stale-data.md), was about the cost of the *inventory cache*: an inventory plugin that keeps what it read from its source and answers from that copy on later runs can hand Ansible hosts that no longer exist. That entry defines the cache options (`cache`, `cache_plugin`, `cache_connection`, `cache_timeout`) and the two cache plugins used here, `memory` and `jsonfile`. This one is about what the cache buys in return: fewer calls to the source's API, and less time spent waiting for it. It measures that on the Proxmox VE plugin of [The Proxmox inventory plugin: guests as hosts](inventory-proxmox-plugin-guests-as-hosts.md) (item 17), which explains Proxmox's *nodes* (the physical servers) and *guests* (the VMs and containers that become hosts), and the plugin's `filters`, `want_facts` and `want_post_filter_facts` options. Everything below ran with ansible-core 2.21.4 and community.proxmox 2.0.0.

## The case

Item 17's mock of the Proxmox API, a small Python server that answers the calls the plugin makes and writes each request it receives to a log, gets two changes:

- **A larger fixture.** A script, `mock/generate.py`, writes the responses for two nodes and 120 guests: VMs and containers in turn, a third of them running, the first 60 tagged `web` and the others `db`. Each guest has the status, configuration and snapshot list the plugin reads for facts.
- **Latency.** Every response waits 20 ms before it's sent, as a remote API would. The plugin sends its requests one after the other, so a run that makes N requests takes at least N × 20 ms.

Every configuration file keeps the 60 `web` guests, with the same filter, and leaves the nodes out (`exclude_nodes: true`):

```yaml
# inventory/cached.proxmox.yml
plugin: community.proxmox.proxmox
url: http://127.0.0.1:18200
user: ansible@pve
exclude_nodes: true
want_post_filter_facts: true
filters:
  - proxmox_tags == 'web'
cache: true
cache_plugin: ansible.builtin.jsonfile
cache_connection: out/cache
cache_timeout: 3600
```

The other files are the same without the `cache` lines, and with `want_facts`, `want_post_filter_facts` or neither. The password comes from the `PROXMOX_PASSWORD` environment variable. Each count below is the number of lines the mock logged during one `ansible-inventory --list` run.

## Requests per run, without the cache

| Configuration | Hosts | Requests |
|---|---|---|
| guest lists only | 60 | 7 |
| `want_facts: true` | 60 | 407 |
| `want_post_filter_facts: true` | 60 | 207 |

The plugin's source, `plugins/inventory/proxmox.py`, explains the numbers. Every run logs in first: with a password, it sends `POST /access/ticket` for a *ticket*, a session token sent as a cookie on the next requests. Then it reads the node list, the VM list and the container list of each node, and the pool list: 7 requests in all, whatever the number of guests.

Facts cost per guest: the guest's status, its configuration, its snapshots, and for a running guest its network interfaces, from the QEMU guest agent (a service inside the VM that reports its addresses) or from the container. That's 3 or 4 requests a guest. `want_facts` reads them for every guest *before* the filters run, so the 60 `db` guests the filter drops cost 200 requests for nothing. `want_post_filter_facts` reads them only for the guests the filters keep, and gives the same 60 hosts with half the requests. The price, as item 17 shows, is that a filter can't use a fact it hasn't read yet.

## With the cache

The cached file above, run several times in a row:

| Run | Requests |
|---|---|
| first, cache empty | 207 |
| second | 1: `POST /access/ticket` |
| with `--flush-cache` | 207 |
| cache file two hours old (`cache_timeout: 3600`) | 207 |
| the run after | 1 |

On a warm cache the plugin reads every response it needs from the cache file, one JSON file in `out/cache/` holding the responses by URL, and only the login reaches the API. `--flush-cache` makes it call the API for everything and write the cache again. A cache file older than `cache_timeout` (the `jsonfile` plugin compares the file's modification time) counts as missing: the run makes all its requests and writes a fresh file. A `cache_timeout` of 0 means never expire, from ansible-core's `plugins/cache/__init__.py`.

Leaving out `cache_plugin` saves nothing between runs: the default cache plugin, `memory`, keeps the data in the `ansible-inventory` process, which ends with the run. Two runs in a row made 207 requests each.

## Wall time

Timings vary from one machine to the next, so the example checks two things that can't flake rather than print seconds:

- the uncached `want_post_filter_facts` run took at least 207 × 20 ms, 4.1 s: yes;
- the cached run took less than half as long: yes.

The cached run still pays for starting Python and Ansible, and for one login. What it saves grows with the number of guests, the facts asked for, and the latency between the controller and the API; a real cluster across a WAN link answers slower than a local mock.

## Timeouts

The plugin has no timeout option: its documentation lists none, and its source calls `requests` without a `timeout` argument, which waits for an answer as long as the connection stays open. Of the cache options, `cache_timeout` is the only one with *timeout* in its name, and it has nothing to do with the network: it's how long the cache stays valid.

The example has a second mock whose `/nodes` answers 3 seconds late:

- `ansible-inventory` waited, then exited 0 with all 120 guests. Nothing reports that the API was slow.
- Under `timeout 2 ansible-inventory …` (the `timeout` command of GNU coreutils, which kills the command after the given seconds), the run was killed with exit code 124 and printed nothing.

So the limit has to come from outside: `timeout` in a script, or the job timeout of the scheduler that runs the playbook. A warm cache avoids most of the slow requests, but not all of them.

## The cache doesn't make the API optional

With the mock stopped and the cache warm:

| Authentication | Result |
|---|---|
| password | no hosts: the login request fails with *Connection refused*, the source doesn't parse, `ansible-inventory` exits 0 |
| API token | 60 hosts, from the cache |

The plugin logs in before it reads anything, cache or not. With a password, the login is a request, `POST /access/ticket`, so a down API breaks the source despite the cache. With an *API token*, an ID and a secret created in Proxmox for a user, sent in a header on every request (`token_id` and `token_secret`, or the `PROXMOX_TOKEN_ID` and `PROXMOX_TOKEN_SECRET` variables), there is nothing to request before reading the cache, and the inventory came out whole. As in [item 15](inventory-plugins-single-source-of-truth.md), a source that fails gives an empty inventory with exit code 0 unless `any_unparsed_is_failed` is set.

## What to take from it

- Count requests, not seconds: a mock that logs them makes the cost of each option visible and stable.
- Prefer `want_post_filter_facts` to `want_facts` when the filters don't need the facts.
- `cache: true` needs a persistent `cache_plugin` such as `ansible.builtin.jsonfile` to save anything between runs.
- Choose `cache_timeout` for how stale the hosts may get, the subject of the previous entry, not for performance alone.
- Put an outer time limit on inventory runs against a remote API, and use an API token if the cache should cover an API outage.

## The example

The series' companion repository, [abdelhousni/ansible-inventory-series](https://github.com/abdelhousni/ansible-inventory-series/tree/main/20-inventory-cache-performance), holds the mock, the fixture generator and the configuration files. `run.sh` generates the fixture, starts the two mocks on ports 18200 and 18201, counts the requests of each run, checks the wall-time bounds, then runs the slow and absent API cases. Its CI runs it on every push and compares the output with the expected one.

## Sources

- community.proxmox 2.0.0, `plugins/inventory/proxmox.py`: the options (`want_facts`, `want_post_filter_facts`, `token_id`, `token_secret`, no timeout option), `_get_auth` (ticket request with a password, header only with a token), `_get_json` (cache lookup per URL, `requests` call without a timeout), `_handle_item` (facts read before or after the filters).
- ansible-core 2.21.4 source: `plugins/doc_fragments/inventory_cache.py` (cache options and defaults), `plugins/cache/__init__.py` (expiry by file modification time, `cache_timeout` 0), `plugins/inventory/__init__.py` (`get_cache_key`).
- Ansible docs, from [ansible/ansible-documentation](https://github.com/ansible/ansible-documentation): `plugins/inventory.rst` (inventory cache).
- Every result above came from ansible-core 2.21.4 on 2026-10-03, on the local machine.
