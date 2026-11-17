# Adopting a live DNS zone with octoDNS without deleting anything

A DNS *zone* is the set of names one party manages, such as `example.dedyn.io` and the names under it, and each entry in it is a *record*: an `A` record maps a name to an IPv4 address, a `TXT` record holds text. [octoDNS](https://github.com/octodns/octodns) keeps those records as YAML files in Git and makes a DNS host match them. A *provider* is its connector to one host. It's the kind of tool [GitOps with push tools](../gitops/gitops-with-push-tools-ansible-opentofu.md) describes: something runs it, and Git says what should be true.

The trap comes on the first run. **octoDNS treats anything missing from the files as something to delete**, so pointing it at a zone that already holds records can remove them, including records other tools own.

## The trap, with its output

These examples use octoDNS's YAML provider as a stand-in for a real DNS host, which makes them safe to try. A zone holds four records. The empty name `''` is the *apex*, the zone's own name, and `ttl` is how many seconds resolvers may cache the answer:

```yaml
# live/example.dedyn.io.yaml, standing in for the DNS host
---
? ''
: type: A
  value: 203.0.113.10
_acme-challenge.pve:
  type: TXT
  value: abc123
app:
  type: A
  value: 192.0.2.10
home:
  ttl: 60
  type: A
  value: 203.0.113.10
```

And the config:

```yaml
# config.yaml
providers:
  config:
    class: octodns.provider.yaml.YamlProvider
    directory: ./src
    default_ttl: 3600
    enforce_order: true
  live:
    class: octodns.provider.yaml.YamlProvider
    directory: ./live
    default_ttl: 3600
    enforce_order: false
zones:
  example.dedyn.io.:
    sources: [config]
    targets: [live]
```

Declare only the record you care about, `app`, in `src/example.dedyn.io.yaml`, and run `octodns-sync`. Without `--doit` it's a *dry run*: it prints a plan and changes nothing. `uvx`, from the [uv](https://docs.astral.sh/uv/) Python tool, runs a command from a pinned package in a throwaway environment:

```sh
uvx --from octodns==1.22.0 octodns-sync --config-file config.yaml
```

```text
*   Delete <ARecord A 3600, example.dedyn.io., ['203.0.113.10']>
*   Delete <TxtRecord TXT 3600, _acme-challenge.pve.example.dedyn.io., ['abc123']>
*   Delete <ARecord A 60, home.example.dedyn.io., ['203.0.113.10']>
*   Summary: Creates=0, Updates=0, Deletes=3, Existing=4, Meta=False
```

## The safety threshold won't save a small zone

octoDNS refuses a plan that updates or deletes more than 30% of the existing records, unless given `--force`. With 12 records and 5 deletes, even the dry run stops:

```text
octodns.provider.plan.TooMuchChange: [example.dedyn.io.] Too many deletes, 41.67% is over 30.00% (5/12), force required
```

But the check only runs when the zone already holds **at least 10 records**: `MIN_EXISTING_RECORDS = 10` in [`octodns/provider/plan.py`](https://github.com/octodns/octodns/blob/v1.22.0/octodns/provider/plan.py). Below that, nothing is checked. With 5 records and 4 deletes, `--doit` went ahead and left one record:

```text
*   Summary: Creates=0, Updates=0, Deletes=4, Existing=5, Meta=False
```

The boundary is exact: 9 records with 8 deletes planned without a word, and 10 records with 4 deletes (40%) were refused. The 30% can be changed with `update_pcent_threshold` and `delete_pcent_threshold`, on a provider or on a zone, but the minimum of 10 is a constant in the code, not a setting: a 5-record zone with `delete_pcent_threshold: 0.1` still planned 4 deletes. A homelab zone can easily be below 10.

## Adopting the zone in four steps

**1. Dump what exists.** `octodns-dump` writes the zone as the provider sees it, including records you may have forgotten. Run it against the real host, with a provider such as [`octodns-desec`](https://pypi.org/project/octodns-desec/) configured under the name `desec`:

```sh
octodns-dump --config-file config.yaml --output-dir dump example.dedyn.io. desec
```

DNS queries can't list a zone, so this is the only complete view. Doing this on a real zone turned up a mistyped record with the zone name doubled, `home.example.dedyn.io.example.dedyn.io`.

**2. Sort the records into yours and theirs.** Some records change on their own:

- a *DynDNS* (dynamic DNS) client keeps a record on the home's public IP, which can change;
- an *ACME client*, the program that gets certificates from Let's Encrypt, creates a TXT record `_acme-challenge.<name>` to [prove it controls a domain](../tls/caddy-dns-01-desec-dedyn-io.md).

Keep those in the file, marked `ignored`, so octoDNS neither changes nor deletes them. The values below are wrong on purpose:

```yaml
# src/example.dedyn.io.yaml
---
? ''
: octodns:
    ignored: true
  type: A
  value: 198.51.100.1
_acme-challenge:
  octodns:
    ignored: true
  type: TXT
  value: managed-by-acme-client
_acme-challenge.pve:
  octodns:
    ignored: true
  type: TXT
  value: placeholder
app:
  type: A
  value: 192.0.2.10
home:
  octodns:
    ignored: true
  ttl: 60
  type: A
  value: 198.51.100.1
```

Only the name and type of an `ignored` record count, so a DynDNS update never shows up as a change. `_acme-challenge` doesn't exist yet and isn't created, but it's covered for when a certificate client adds it. Keys have to stay sorted, because `enforce_order` refuses to load the file otherwise:

```text
yaml.constructor.ConstructorError: keys out of order: expected app got home at ./src/example.dedyn.io.yaml, line 2, column 1
```

On a real provider, an apex `NS` record (the one naming the zone's nameservers) left out of the file is also left alone, with a warning in the log.

**3. Require a plan with no changes.** This is the proof that the file describes the zone:

```text
No changes were planned
```

If the plan shows anything else, fix the file, not the zone.

**4. Prove it before relying on it.** Add one record to a copy of the file. The plan should show exactly one line:

```text
*   Create <ARecord A 3600, grafana.example.dedyn.io., ['192.0.2.10']> (config)
*   Summary: Creates=1, Updates=0, Deletes=0, Existing=4, Meta=False
```

## Running it from Git

Once the plan is empty, CI can run it (*continuous integration*: automated jobs on every push, see [the DevOps terminology entry](../devops/devops-devsecops-dora-cicd-gitops-terminology.md)). One workflow can cover three cases:

| Trigger | Command | Effect |
|---|---|---|
| Pull request | `octodns-sync` | Posts the plan as a comment for review |
| Merge to `main` | `octodns-sync --doit` | Applies the plan |
| Daily schedule | `octodns-sync`, failing if the plan isn't empty | Reports records changed by hand, and corrects nothing |

Keep `--force` out of the workflow, so the threshold still applies to zones big enough for it. The provider reads the API token from the environment, through a setting such as `token: env/DESEC_TOKEN` ([`octodns-desec`'s README](https://pypi.org/project/octodns-desec/)).

One more thing to watch once it's in place: **run octoDNS only from CI**. A local `--doit` leaves `main` describing something other than what's live.

## Sources

- Tested on 2026-10-31 with octoDNS 1.22.0, and again on 2026-11-17 in a cloud container with the same version, still the latest on PyPI: every output above, using two YAML providers and `example.dedyn.io`, including `TooMuchChange` at 5 of 12, the unprotected delete at 4 of 5, the 9 and 10 record boundary, and a zone-level `delete_pcent_threshold` having no effect below 10 records. With a create applied by `--doit`, an `ignored` record's live value stayed as it was.
- The threshold logic read in octoDNS 1.22.0's [`plan.py`](https://github.com/octodns/octodns/blob/v1.22.0/octodns/provider/plan.py) (`MAX_SAFE_UPDATE_PCENT`, `MAX_SAFE_DELETE_PCENT` and `MIN_EXISTING_RECORDS`), and the zone settings in `manager.py`.
- Run separately against a real zone at deSEC with `octodns-desec` 1.3.0 and GitHub Actions: the dump, the plan with no changes, one create, the apex `NS` warning, and the three workflow triggers. Addresses here are the [RFC 5737](https://www.rfc-editor.org/rfc/rfc5737) documentation ranges.
- Not tested: an `ignored` `_acme-challenge` while a certificate client is using it, beyond the same mechanism working on a TXT record that already exists.
