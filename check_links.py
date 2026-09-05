#!/usr/bin/env python3
"""Check the built site (_site/) for dead links.

Broken internal links (references to a file that doesn't exist in _site/)
fail the build -- they're always our own mistake and always fixable.
Unreachable external links only print a warning, since a third-party site
being briefly down or blocking bots shouldn't fail CI. Pass --external to
also check external links (skipped by default to keep local runs fast and
offline-friendly).
"""
import pathlib
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser

root = pathlib.Path(__file__).parent.resolve()
site = root / "_site"

TIMEOUT = 10


class HrefCollector(HTMLParser):
    """Collects href values from real <a> tags only.

    A regex scan over the raw HTML would also match the literal text
    'href="..."' when it appears as content inside a <pre>/<code> block (our
    own TIL posts show HTML/Python snippets containing href="..." examples),
    and Pygments splits that text across multiple <span> tags, which mangles
    a naive regex match entirely. Parsing real tags avoids both problems.
    """

    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value:
                    self.hrefs.append(value)


def links_in(html_path):
    collector = HrefCollector()
    collector.feed(html_path.read_text())
    return collector.hrefs


def check_internal(html_path, href):
    target = (html_path.parent / href.split("#")[0]).resolve()
    if not target.exists():
        return f"{html_path.relative_to(site)}: broken link -> {href}"
    return None


def check_external(url):
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "til-link-checker"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            if response.status >= 400:
                return f"{url}: HTTP {response.status}"
    except urllib.error.HTTPError as error:
        # Some servers reject HEAD but are fine with GET.
        if error.code == 405:
            try:
                urllib.request.urlopen(
                    urllib.request.Request(url, headers={"User-Agent": "til-link-checker"}), timeout=TIMEOUT
                )
                return None
            except Exception as retry_error:
                return f"{url}: {retry_error}"
        return f"{url}: HTTP {error.code}"
    except Exception as error:
        return f"{url}: {error}"
    return None


def main():
    check_external_links = "--external" in sys.argv

    html_files = sorted(site.rglob("*.html"))
    if not html_files:
        print("No built HTML found in _site/ -- run build_site.py first.", file=sys.stderr)
        sys.exit(1)

    broken_internal = []
    external_urls = set()
    for html_path in html_files:
        for href in links_in(html_path):
            if href.startswith(("http://", "https://")):
                external_urls.add(href)
            elif not href.startswith(("mailto:", "#")):
                error = check_internal(html_path, href)
                if error:
                    broken_internal.append(error)

    for error in broken_internal:
        print(f"BROKEN: {error}")

    if check_external_links:
        for url in sorted(external_urls):
            error = check_external(url)
            if error:
                print(f"WARN (external): {error}")

    if broken_internal:
        print(f"\n{len(broken_internal)} broken internal link(s) found.")
        sys.exit(1)

    print(f"No broken internal links found ({len(html_files)} pages checked).")


if __name__ == "__main__":
    main()
