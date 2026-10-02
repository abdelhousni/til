# Network data with ansible.utils: checking pg_hba subnets and numbering Proxmox guests

Fourteenth entry in the Shaping data in Ansible series. Addresses and subnets look like strings, but they have rules: `10.30.0.0/33` doesn't exist, and `10.20.0.5/24` is a host address wearing a subnet's prefix. The `ansible.utils` collection has filters that understand them. This entry uses them twice:
- to check the client subnets of [part 5](subelements-versus-product-quadlet-volumes-pg-hba.md)'s `pg_hba` rules before they reach PostgreSQL;
- to give each of [part 4](selectattr-rejectattr-map-proxmox-guests-and-facts.md)'s Proxmox guests an address in its node's subnet.

Everything below ran with ansible-core 2.21.4, ansible.utils 6.1.1 and netaddr 1.3.0.

## Two things to install

The filters are in the `ansible.utils` collection, not in ansible-core, and they do the work with `netaddr`, a Python library for addresses, which has to be on the *controller*, the machine running `ansible-playbook`. The example repository added both to its requirements.

A short reminder of the notation, which part 5 introduced: `10.10.0.0/24` is a *subnet*, a range of addresses written as its first address and a *prefix*, the number of leading bits all its addresses share. A /24 holds 256 addresses, a /16 holds 65,536, and a /32 is a single address. In a subnet written correctly, the bits after the prefix, the *host bits*, are zero.

## What ipaddr makes of each input

The client subnets, as someone might type them into a form:

| Input | `ipaddr` | `ipaddr('net')` | `ipaddr('subnet')` | `is ansible.utils.ip` |
|---|---|---|---|---|
| `10.10.0.0/24` | `10.10.0.0/24` | `10.10.0.0/24` | `10.10.0.0/24` | true |
| `10.10.0.11/32` | `10.10.0.11/32` | none | `10.10.0.11/32` | true |
| `10.20.0.5/24` | `10.20.0.5/24` | none | `10.20.0.0/24` | false |
| `10.40.0.0` | `10.40.0.0` | none | `10.40.0.0/32` | true |
| `10.30.0.0/33` | false | false | false | false |
| `db.example` | false | false | false | false |
| `2001:db8::/64` | `2001:db8::/64` | `2001:db8::/64` | `2001:db8::/64` | true |

- **Invalid input isn't an error.** `ipaddr` returns `false`, so a typo flows on into the rest of the play.
- **`ipaddr` with no argument only asks "is this an address?"** It accepted `10.20.0.5/24` and the bare `10.40.0.0`.
- **`'net'` returns nothing for host bits, and for a single address.** Its code in `plugin_utils/base/ipaddr_utils.py` keeps only networks of more than one address whose host bits are zero. That rejects the /32, the form [part 11](data-from-other-hosts-extract-hostvars-pg-hba.md) uses for one application server.
- **`'subnet'` corrects quietly.** It turned `10.20.0.5/24` into `10.20.0.0/24`, a guess about what was meant.
- **The `ip` test accepts any address or correct network**, including the bare `10.40.0.0`.

### What PostgreSQL does with the bad ones

In PostgreSQL 16.14, two `pg_hba.conf` lines that `ipaddr` accepted:
- **`10.40.0.0` without a prefix stopped the server from starting.** PostgreSQL read the next column as a netmask: *"invalid IP mask "scram-sha-256": Name or service not known"*, then *"could not load pg_hba.conf"*.
- **`10.20.0.5/24` was accepted** as address `10.20.0.5` with netmask `255.255.255.0`. The rule then matches the whole /24. If the person meant the one host, the rule lets in 255 more.

### Checking, and naming the bad ones

A subnet is written correctly when `ipaddr('subnet')` gives it back unchanged: no host bits, a prefix, a valid address. That accepts the /32 that `'net'` refused:

```yaml
rejected: "{{ inputs | reject('in', inputs | map('ansible.utils.ipaddr', 'subnet')) | list }}"
```

Then an `assert` task stops the play with the list: *"not a network with a prefix: 10.20.0.5/24, 10.40.0.0, 10.30.0.0/33, db.example"*.

**Don't filter a list through `ipaddr`.** Given a list, it drops whatever fails. The source, `ipaddr_utils.py`, keeps only the items whose result is true. `inputs | ansible.utils.ipaddr('net')` returned `['10.10.0.0/24', '2001:db8::/64']`, two of seven. In `pg_hba` rules, the missing subnets are clients that can no longer connect, with no error anywhere.

## Numbering the Proxmox guests

`ipsubnet` splits a range into smaller subnets. `'10.10.0.0/16' | ansible.utils.ipsubnet(24)` gave `256`, the number of /24s in it, and with a second argument, the n-th one, counting from 0: `ipsubnet(24, 0)` was `10.10.0.0/24` and `ipsubnet(24, 1)` was `10.10.1.0/24`. One per node, in the order of a `proxmox_nodes` list, gives pve the first and pve2 the second.

`ipaddr` with a number gives the n-th address of a subnet. A guest's VMID, the unique number Proxmox gives it, makes a convenient host number:

```yaml
"{{ guest_range | ansible.utils.ipsubnet(24, proxmox_nodes.index(vm.node)) | ansible.utils.ipaddr(vm.vmid) }}"
```

| Guest | Node | Address |
|---|---|---|
| 100 | pve | `10.10.0.100/24` |
| 101 | pve2 | `10.10.1.101/24` |
| 102 | pve | `10.10.0.102/24` |
| 103 | pve2 | `10.10.1.103/24` |
| 104 | pve2 | `10.10.1.104/24` |
| 105 | pve2 | `10.10.1.105/24` |

**It stops working at VMID 255.** A /24 has 256 addresses, numbered 0 to 255, and `-1` is the last one, `10.10.0.255`, the *broadcast* address, which `network_in_usable` reported as not usable. Two filters behave differently past the end:
- **`ipaddr(300)` returned `false`**, which at least isn't an address.
- **`ipmath(300)`, which adds a number to an address, returned `10.10.1.44`**: a real address in the next node's subnet, `is ansible.utils.in_network('10.10.0.0/24')` false. Its source drops the prefix before adding, so it can't know it left the subnet.

Proxmox allows VMIDs from 100 to 999,999,999, so this scheme only holds while they stay below 255, and an `assert` should say so.

## Which one

- **Is this a correctly written subnet, /32 included?** `value | ansible.utils.ipaddr('subnet') == value`.
- **Only multi-address networks, host bits zero:** `ipaddr('net')`.
- **Several values:** check each and name the failures; never pass the list straight to `ipaddr`.
- **The n-th subnet of a range, the n-th address of a subnet:** `ipsubnet(prefix, n)` and `ipaddr(n)`, which return `false` past the end. `ipmath` doesn't check.

## The example repository

The series' companion repository, [abdelhousni/ansible-data-shaping-series](https://github.com/abdelhousni/ansible-data-shaping-series/tree/main/14-network-data), runs all of the above except the PostgreSQL test on the local machine, changing nothing outside its `out/` directory. `net.yml` checks the inputs in `vars/network.yml`, and numbers part 4's recorded guests. Its CI runs it on every push and compares the output with the expected one.

## Sources

- [ansible.utils](https://github.com/ansible-collections/ansible.utils) 6.1.1: `plugins/filter/ipaddr.py`, `ipsubnet.py`, `ipmath.py` (the prefix dropped before adding), `network_in_usable.py`, the tests in `plugins/test/`, and `plugins/plugin_utils/base/ipaddr_utils.py` (the `net` and `subnet` queries, and the list handling).
- [netaddr](https://github.com/netaddr/netaddr) 1.3.0.
- PostgreSQL 16 documentation, [The pg_hba.conf File](https://www.postgresql.org/docs/16/auth-pg-hba-conf.html); the two lines checked on PostgreSQL 16.14 from Ubuntu's packages, with `pg_hba_file_rules`.
- Proxmox VE's VMID range, from the [qm manual](https://pve.proxmox.com/pve-docs/qm.1.html).
- Every result above came from ansible-core 2.21.4 on 2026-10-02, on the local machine. No Proxmox server was involved.
