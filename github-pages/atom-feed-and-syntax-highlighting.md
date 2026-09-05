# Adding an Atom feed and syntax highlighting to a static site build script

Continuing on from [publishing this TIL collection as a static site](static-site-instead-of-datasette.md), I wanted two things a real TIL site should have: an Atom feed people can subscribe to, and syntax-highlighted code blocks instead of flat gray `<pre>` boxes.

## Atom feed

`build_site.py` already looped over every topic directory to render per-entry HTML pages. I had it also append each rendered entry (title, date, url, and the rendered HTML body) to a flat list as it went, so after the loop I have everything needed to build a feed without re-parsing anything.

The feed itself is plain string templating, no library:

```python
FEED_ENTRY_TEMPLATE = """<entry>
<title>{title}</title>
<link href="{url}"/>
<id>{url}</id>
<updated>{updated}</updated>
<content type="html">{content}</content>
</entry>"""
```

Two things mattered for correctness:

- **XML-escaping the content.** An Atom `<content type="html">` element holds an HTML string *as escaped text*, not as literal child elements (that would require `type="xhtml"` with different rules). Every entry body has to go through `xml.sax.saxutils.escape()` before being dropped into the template, otherwise a `<p>` tag in the TIL body would be parsed as an actual feed XML element and break the document.
- **Capping the length.** Sorting all entries by date descending and slicing to the most recent 50 keeps the feed from growing forever — feed readers only care about what's new.

I validated the output the boring way: `xml.dom.minidom.parse()` on the generated file. If it doesn't raise, the XML is well-formed.

## Syntax highlighting

Python-Markdown ships a `codehilite` extension that hands fenced code blocks to Pygments. Turning it on is one line:

```python
markdown.markdown(
    body_text,
    extensions=["fenced_code", "tables", "codehilite"],
    extension_configs={"codehilite": {"guess_lang": False}},
)
```

(`guess_lang: False` matters — without it, codehilite tries to detect the language of unlabeled fenced blocks, which is slow and often wrong. Since I always label my fences with a language, I don't need the guesser.)

The highlighted output is `<span>` tags with class names like `.nt`, `.p`, `.s1` — Pygments' generic token classes. Those classes need a stylesheet to mean anything, and rather than hand-write one (and have it drift out of sync with whatever Pygments version generates the spans), I generate it at build time:

```python
from pygments.formatters import HtmlFormatter
formatter = HtmlFormatter(style="default")
css = formatter.get_style_defs(".codehilite")
```

That gets appended straight into `style.css` alongside my hand-written layout rules. Change `style="default"` to any other Pygments theme name and the CSS updates itself on the next build — no separate file to keep in sync.

## Result

Both are live at <https://abdelhousni.github.io/til/> — the feed at `/feed.atom`, discoverable via `<link rel="alternate" type="application/atom+xml">` in every page's `<head>`.
