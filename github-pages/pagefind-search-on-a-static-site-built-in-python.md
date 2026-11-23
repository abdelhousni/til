# Adding Pagefind search to a static site built in Python

This site is a set of HTML files written by one Python script, [`build_site.py`](static-site-instead-of-datasette.md), and served by GitHub Pages. There is no server to send a search query to. [Pagefind](https://pagefind.app/docs/) is a search tool made for that case: it "runs after your static generator, and outputs a static search bundle to your generated site". The bundle is a directory of files: an index cut into pieces, and the JavaScript that reads it in the reader's browser. Nothing else runs anywhere.

Below is what it took for 170 entries: one pinned dependency, one command after the build, a few HTML attributes, and one setting I only found by serving the site from a subdirectory.

## Install it from PyPI and pin it

Pagefind is a single program written in Rust. Its documentation leads with `npx pagefind`, which downloads it through Node. It is also published on PyPI, which keeps this site's build Python-only. In `requirements.txt`:

```text
# Pinned: the extra ships the platform binary that indexes _site for search.
pagefind[bin]==1.6.0
```

The `pagefind` package alone is a thin wrapper. The `[bin]` *extra* (an optional set of dependencies, asked for in square brackets) pulls `pagefind_bin`, which contains the program for the current platform. Without it, `python -m pagefind` stops with `FileNotFoundError: Could not find pagefind binary`. The other extra, `[extended]`, is the one the [installation page](https://pagefind.app/docs/installation/) shows first: it "includes specialized support for indexing Chinese, Japanese, and Thai pages", and `[bin]` is "the smaller standard release". This site is in English, so `[bin]` it is.

1.6.0 was the latest release on 2026-11-23, according to `pip index versions pagefind` and the [release list](https://github.com/Pagefind/pagefind/releases).

## Index after the build

Pagefind reads the HTML the build wrote, not the Markdown sources. So it is a second command, after `build_site.py`:

```sh
python build_site.py
python -m pagefind --site _site
```

```text
Running Pagefind v1.6.0
Source:       "_site"
Output:       "_site/pagefind"

[Walking source directory]
Found 200 files matching **/*.{html}

[Parsing files]
Found a data-pagefind-body element on the site.
↳ Ignoring pages without this tag.

[Reading languages]
Discovered 1 language: en

[Building search indexes]
Total:
  Indexed 1 language
  Indexed 170 pages
  Indexed 11770 words
  Indexed 1 filter
  Indexed 0 sorts

Finished in 0.464 seconds
```

`--site` is "the location of your built static site", and the bundle goes to a `pagefind` directory inside it by default ([configuration options](https://pagefind.app/docs/config-options/)). The language comes from the `lang` attribute of each page's `<html>` element ([multilingual search](https://pagefind.app/docs/multilingual/)).

The same line went into the `Makefile`'s `build` target and into the GitHub Actions workflow, between the build and the link check:

```yaml
    - name: Build site
      run: python build_site.py
    - name: Build the search index
      run: python -m pagefind --site _site
    - name: Check for dead links
      run: python check_links.py --external
```

The whole of `_site` is uploaded to GitHub Pages, so `pagefind/` is published with the rest.

## Say what to index

Out of the box, Pagefind indexes the `<body>` of every HTML file: here that would include the homepage, the topic pages and the redirect stubs, which only repeat titles. Three attributes, described on the [indexing](https://pagefind.app/docs/indexing/) and [filtering](https://pagefind.app/docs/filtering/) pages, narrow it down. This is the entry template:

```html
<main data-pagefind-body>
<h1>{title}</h1>
<p class="meta"><span data-pagefind-filter="topic">{topic}</span><span data-pagefind-ignore> - {date}</span></p>
{body}
<p class="created" data-pagefind-ignore>{created_line}</p>
<div data-pagefind-ignore>{series_nav}</div></main>
```

- **`data-pagefind-body`** marks the part of a page to index. It also acts on the whole site: "If `data-pagefind-body` is found anywhere on your site, any pages without this attribute will not be indexed." Only the entry template has it, which is why 200 HTML files gave 170 indexed pages, one per entry.
- **`data-pagefind-ignore`** leaves an element out of the index. The date, the "Created" line and the series navigation would otherwise show up in result excerpts. So would the source of each [Mermaid diagram](mermaid-diagrams-in-markdown.md), which is text in a `<pre>` until the browser draws it, so that `<pre>` has the attribute too.
- **`data-pagefind-filter="topic"`** records the element's text as a value of a filter named `topic`: it "will associate that page with the filter name, and capture the contents of the element as the filter value". That is the `Indexed 1 filter` line. Nothing uses the filter yet; it is there for a topic selector later.

## Add the search box

Pagefind writes its interface into the bundle as well. Since version 1.5.0 that is the *Component UI*: [web components](https://developer.mozilla.org/en-US/docs/Web/API/Web_components), which are custom HTML elements defined by a script. Two files in the `<head>`, and three elements in the page ([Search UI](https://pagefind.app/docs/search-ui/)):

```html
<link rel="stylesheet" href="../pagefind/pagefind-component-ui.css">
<script src="../pagefind/pagefind-component-ui.js" type="module"></script>
...
<pagefind-modal-trigger></pagefind-modal-trigger>
<pagefind-config bundle-path="./"></pagefind-config>
<pagefind-modal></pagefind-modal>
```

`<pagefind-modal-trigger>` is a button that opens the search dialog and, by default, "listens for `Cmd+K` (Mac) or `Ctrl+K` (Windows/Linux)" ([modal trigger](https://pagefind.app/docs/components/modal-trigger/)). `<pagefind-modal>` is the dialog, with the input and the results. `<pagefind-config>` is explained below.

In `build_site.py` the `<head>` lines come from a small function, because the path to the site root differs by page: empty on the homepage, `../` on topic pages and entries.

```python
def search_head(prefix):
    return (
        f'<link rel="stylesheet" href="{prefix}pagefind/pagefind-component-ui.css">\n'
        f'<script src="{prefix}pagefind/pagefind-component-ui.js" type="module"></script>'
    )
```

The paths are relative on purpose. A site on GitHub Pages can be reached at the root of a custom domain or under `/<repository>/` on `github.io`, and a path starting with `/` only works for the first.

## The setting a subdirectory needs: `bundle-path`

Relative paths in the `<head>` weren't enough. Served from a subdirectory (`http://localhost:8001/til/`), the button appeared and the search found nothing. The browser console said why:

```text
404 http://localhost:8001/pagefind/pagefind.js
Pagefind couldn't be loaded from /pagefind/pagefind.js
You can configure this by passing a bundlePath option to the Pagefind Component UI
```

The Component UI loads the search code, `pagefind.js`, from `/pagefind/` at the root of the host when it can't work out where the bundle is. The [search configuration](https://pagefind.app/docs/search-config/) page says of the bundle path: "In most cases this should be automatically detected by the import URL. Set this if search isn't working and you are seeing a console warning". Its example is an absolute path, `bundle-path="/subpath/pagefind/"`, which would again tie the pages to one location.

What worked is `bundle-path="./"`. The value is resolved against the script that uses it, `pagefind-component-ui.js`, and that file sits in `pagefind/` beside `pagefind.js`. The same three characters are right on every page at any depth. Result links followed the bundle's location without any other setting: they came out as `/til/ansible/…` under the subdirectory and `/ansible/…` at the root. I tested both locations on the homepage, a topic page and an entry. The documentation doesn't mention a relative value, so this is what Pagefind 1.6.0 does, not a documented promise.

I also tried `base-url`, the option the same page gives for "hosting a site on a subpath". A relative value doesn't work there: `base-url="../"` produced links starting with `/../`.

## What a search downloads

The index isn't one file. For 170 entries the bundle is 2.1 MB: 170 *fragments* (one per page, holding its text for the excerpts), 18 index chunks, and the code. Counted in Chromium on an entry page, with files served uncompressed by `python -m http.server`:

| When | Files | Bytes |
|---|---|---|
| Page load | the Component UI: one CSS file, one JavaScript file | 226,107 |
| Opening the dialog | `pagefind.js`, its worker, a WebAssembly module, the index metadata and the filter values | 152,343 |
| Typing `quadlet` (8 results) | 1 index chunk and 6 fragments | 54,400 |

So the page pays for the interface up front, and a query fetches only the chunk for its words and the fragments of the results it shows.

## Three things to know before relying on it

- **A build without the second command has no search.** After `python build_site.py` alone, the two `<head>` files are 404s and the button never appears, because the element is only defined by the missing script. The page is otherwise intact.
- **Don't rebuild while testing.** A link check that rebuilt `_site` in the background removed `pagefind/` under the browser test I was running, with the same symptom.
- **The title starts every excerpt.** The `<h1>` is inside `data-pagefind-body`, so an excerpt begins by repeating the result's title.

## Checking it

```sh
grep -L "data-pagefind-body" _site/index.html _site/*/index.html | wc -l   # 29: the homepage and 28 topic pages
```

In headless Chromium (Playwright 1.56), on an entry: the dialog opened on a click and on Ctrl+K, `ansible inventory` returned 43 results, no excerpt contained a date or a "Created" line, and no request to `pagefind/` failed.

## Sources

- Pagefind documentation, read on 2026-11-23: [overview](https://pagefind.app/docs/), [installation](https://pagefind.app/docs/installation/), [indexing](https://pagefind.app/docs/indexing/), [filtering](https://pagefind.app/docs/filtering/), [configuration options](https://pagefind.app/docs/config-options/), [multilingual search](https://pagefind.app/docs/multilingual/), [Search UI](https://pagefind.app/docs/search-ui/), [modal trigger](https://pagefind.app/docs/components/modal-trigger/), [search configuration](https://pagefind.app/docs/search-config/).
- [Pagefind releases](https://github.com/Pagefind/pagefind/releases) and [`pagefind` on PyPI](https://pypi.org/project/pagefind/): version 1.6.0.
- The change itself: [abdelhousni/til#241](https://github.com/abdelhousni/til/pull/241).

Everything above ran in a Linux container with Python 3.13.18 and Pagefind 1.6.0, against a local copy of the site. The subdirectory case was tested locally, not on `github.io`.
