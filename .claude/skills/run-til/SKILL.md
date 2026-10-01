---
name: run-til
description: Build, serve, screenshot and check the TIL static site (til.housni.eu). Use when asked to run or preview the site, build it, see how an entry renders, take a screenshot of a page, check that lists, tables or Mermaid diagrams render, or run the site's link checks.
---

The site is static: `build_site.py` turns the markdown entries into `_site/`,
which `python -m http.server` serves. An agent checks it with
`.claude/skills/run-til/driver.mjs`, a headless-Chromium script that
screenshots pages and flags what the build gets wrong without failing.

All paths are relative to the repository root.

## Prerequisites

Python 3 with `venv`, `make`, `git` with full history, Node, and Playwright
with a Chromium. In the cloud container Playwright 1.56 is installed
globally under `/opt/node-tools/node_modules` and Chromium under
`/opt/pw-browsers`; the driver finds both, even in a shell without
`PLAYWRIGHT_BROWSERS_PATH`. Nothing else to install.

The build reads each entry's date from `git log`, so a shallow clone fails
`make build` on purpose:

```bash
git fetch --unshallow   # only if make build says "This is a shallow clone"
```

## Build

```bash
make build    # creates .venv on first run, then writes _site/
```

## Run (agent path)

Serve `_site/` in the background and wait for the port:

```bash
(.venv/bin/python -m http.server 8000 -d _site >/tmp/til-serve.log 2>&1 &)
timeout 15 bash -c 'until curl -sf localhost:8000/ >/dev/null; do sleep 0.3; done'
```

Then run the driver with page paths relative to the site root (`""` is the
homepage):

```bash
node .claude/skills/run-til/driver.mjs "" ansible/combine-recursive-list-merge-postgresql-quadlets.html podman/artifactory-as-a-pull-through-mirror.html
```

```
ok   http://localhost:8000/  "Abdellatif Housni: TIL"  -> /tmp/til-shots/index.png
ok   http://localhost:8000/ansible/combine-recursive-…html  "Merging dicts with combine: …"  -> /tmp/til-shots/ansible_combine-….png
ok   http://localhost:8000/podman/artifactory-…html  "Pointing Podman at …"  -> /tmp/til-shots/podman_artifactory-….png
```

For each page it takes a full-page screenshot in `/tmp/til-shots/` (`--out
DIR` to change; `--base URL` for another port), and reports `FAIL` with a
reason for:
- `list inside <p>`: a `- item` line that stayed in a paragraph;
- `mermaid blocks not rendered`: a ```` ```mermaid ```` block with no SVG;
- console errors, failed requests to the site, and non-200 pages.

It exits 1 if any page failed. Every page of the site, about 4 minutes:

```bash
node .claude/skills/run-til/driver.mjs --out /tmp/til-shots/all $(cd _site && find . -name '*.html' | sed 's#^\./##' | sort)
```

Full-page screenshots of long entries are several thousand pixels tall. To
look at one part, screenshot an element instead, e.g. with Playwright's
`page.locator("pre.mermaid").first().screenshot(...)`.

Stop the server:

```bash
fuser -k 8000/tcp
```

## Run (human path)

```bash
make serve    # builds, then serves on http://localhost:8000/ until ctrl-c
```

## Test

```bash
make check    # build + internal link check: "No broken internal links found (N pages checked)."
```

`make preflight` is what CI runs; it also rewrites `README.md` and checks
external links, which is slow.

## Gotchas

- **A list straight after a paragraph.** Python-Markdown needs a blank line
  before a list; GitHub doesn't. `build_site.py`'s
  `separate_lists_from_paragraphs` adds it. The driver's `list inside <p>`
  check is how that bug was found on 71 paragraphs, so run it after touching
  the markdown pipeline.
- **External resources behind the cloud proxy.** Mermaid
  (`cdn.jsdelivr.net`) and the shields.io badge fail in Chromium with
  `ERR_CERT_AUTHORITY_INVALID`. `ignoreHTTPSErrors` turns that into
  `ERR_TOO_MANY_RETRIES`, and Chromium's `--proxy-server` doesn't help. When
  `HTTPS_PROXY` is set, the driver fetches every external `https://` request
  with `curl`, which trusts the proxy's CA, and fulfils it from that.
- **Don't use Playwright's `proxy` launch option.** It also sends
  `localhost` through the proxy, which answers `405 Method Not Allowed`, even
  with `bypass: "localhost,127.0.0.1"` and with `--base http://127.0.0.1:8000`.
- **GoatCounter** (`//gc.zgo.at/count.js`) is protocol-relative, so on
  `http://localhost` it goes out as plain HTTP and the proxy refuses it. The
  driver blocks it; a local preview shouldn't count as a visit anyway.
- **An uncommitted `.md` file** builds with the date `unknown`; `make build`
  warns about it.

## Troubleshooting

- **`This is a shallow clone, so entry dates would all render as 'unknown'.`**
  from `make build`: run `git fetch --unshallow`.
- **`playwright not found`** from the driver: Playwright isn't at
  `/opt/node-tools/node_modules` or resolvable from the repo; install it
  (`npm i -g playwright`) or edit the path list at the top of `driver.mjs`.
