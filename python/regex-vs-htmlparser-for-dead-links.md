# A regex link checker breaks on the exact HTML it was meant to check

I noticed one of my own TIL entries had a dead link: [the second entry](../github-pages/atom-feed-and-syntax-highlighting.md) linked to a sibling post using `[text](static-site-instead-of-datasette.md)`, a relative link to the markdown *source* file. That resolves fine when GitHub renders the `.md` file directly, but my [static site build script](../github-pages/static-site-instead-of-datasette.md) only ever writes `.html` files, so the link 404'd on the actual published site.

The fix for that part was straightforward: rewrite relative `*.md` links to `*.html` before handing the markdown off for conversion.

```python
RELATIVE_MD_LINK_RE = re.compile(r"(?<=\]\()(?!https?://)([^)\s]+?)\.md(#[^)]*)?(?=\))")

def rewrite_relative_md_links(text):
    return RELATIVE_MD_LINK_RE.sub(lambda m: f"{m.group(1)}.html{m.group(2) or ''}", text)
```

## Then the fix for the bug broke the build

To stop this happening again, I added a `check_links.py` step to CI: build the site, then walk every `_site/**/*.html` file, extract `href` attributes, and fail if any local one points at a file that doesn't exist. First version used a plain regex:

```python
HREF_RE = re.compile(r'href="([^"]+)"')
```

It caught the bug I'd just fixed. Then, on the very next commit, it failed the build again — on a link that didn't exist:

```
BROKEN: github-pages/atom-feed-and-syntax-highlighting.html: broken link -> </span><span class=
```

That "link" is HTML markup, not a URL. The TIL post *about* the link bug shows the fix as a Python code sample, which itself contains the literal text `href="..."` (as an example, inside a fenced code block). Two things compounded:

1. My regex has no concept of "inside a `<code>` block" vs "inside a real `<a>` tag" — it just scans raw text for anything shaped like `href="..."`, so the example text matched too.
2. Pygments syntax-highlights that code sample by wrapping tokens in `<span>` tags, which splits the literal string `href="../feed.atom"` across multiple spans: `href=<span>"</span><span>...</span>`. My regex's `[^"]+` then greedily matched everything between the first `"` it found and the *next* one — which happened to be several spans away, capturing raw HTML markup as if it were a URL.

The actual fix was to stop treating HTML as text and parse it properly:

```python
from html.parser import HTMLParser

class HrefCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value:
                    self.hrefs.append(value)
```

`HTMLParser` only calls `handle_starttag` for genuine tags — text content inside a `<code>` block that merely *looks like* `href="..."` is just character data to it, never mistaken for a real attribute. No more false positives, and it still catches a real broken link just as well (I verified by manually reintroducing one and confirming the checker still exits non-zero).

## The lesson

Regexes over HTML break down exactly when the HTML gets interesting — and a link checker for a *programming blog*, where code samples routinely contain HTML-shaped strings, is about the worst place to find that out. If the content you're parsing might contain more of itself as text, use a real parser.
