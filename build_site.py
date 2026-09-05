#!/usr/bin/env python3
"""Build the static GitHub Pages site (_site/) from the TIL markdown files."""
import json
import pathlib
import re
import shutil
import subprocess
import sys
from xml.sax.saxutils import escape

root = pathlib.Path(__file__).parent.resolve()

# The repo has a topic directory literally named "markdown/", which shadows
# the pip "markdown" package via the script-directory entry Python adds to
# sys.path. Drop that entry before importing so the real package is found.
sys.path = [p for p in sys.path if p not in ("", ".", str(root))]

import markdown  # noqa: E402
from pygments.formatters import HtmlFormatter  # noqa: E402

site = root / "_site"
SITE_TITLE = "Abdellatif Housni: TIL"
SITE_URL = "https://abdelhousni.github.io/til"
SITE_AUTHOR = "Abdellatif Housni"
AUTHOR_SAME_AS = [
    "https://github.com/abdelhousni",
    "https://www.linkedin.com/in/abdelhousni/",
]
SITE_DESCRIPTION = "Abdellatif Housni's Today I Learned notes: short, practical write-ups on things learned while building."
BING_VERIFICATION_CODE = "B109FF34ED264CD7CDA115D1B13A4C7F"
SKIP_DIRS = {".git", ".github", "__pycache__"}
FEED_ENTRY_LIMIT = 50

TAG_RE = re.compile(r"<[^>]+>")


def plain_text_summary(html_body, limit=160):
    """First paragraph of rendered HTML, tags stripped, for a <meta description>."""
    match = re.search(r"<p>(.*?)</p>", html_body, re.DOTALL)
    text = TAG_RE.sub("", match.group(1)) if match else ""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def build_person_schema():
    data = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": SITE_AUTHOR,
        "url": f"{SITE_URL}/",
        "sameAs": AUTHOR_SAME_AS,
    }
    return f'<script type="application/ld+json">\n{json.dumps(data, indent=2)}\n</script>'

PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title} - TIL</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{description}">
<meta name="author" content="{author}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{url}">
<link rel="stylesheet" href="../style.css">
<link rel="alternate" type="application/atom+xml" title="{site_title}" href="../feed.atom">
</head>
<body>
<header><a href="../index.html">&larr; All TILs</a></header>
<main>
<h1>{title}</h1>
<p class="meta">{topic} - {date}</p>
{body}
</main>
</body>
</html>
"""

INDEX_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{description}">
<meta name="author" content="{author}">
<meta name="msvalidate.01" content="{bing_verification_code}">
<link rel="canonical" href="{url}/">
<meta property="og:type" content="website">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{url}/">
<link rel="stylesheet" href="style.css">
<link rel="alternate" type="application/atom+xml" title="{title}" href="feed.atom">
{person_schema}
</head>
<body>
<header><h1>{title}</h1><p>{count} TILs so far. <a href="feed.atom">Atom feed</a>.</p></header>
<main>
{body}
</main>
</body>
</html>
"""

SITEMAP_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{urls}
</urlset>
"""

SITEMAP_URL_TEMPLATE = """<url>
<loc>{loc}</loc>
<lastmod>{lastmod}</lastmod>
</url>"""

ROBOTS_TXT = """User-agent: *
Allow: /

Sitemap: {site_url}/sitemap.xml
"""

FEED_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>{title}</title>
<link href="{site_url}/feed.atom" rel="self"/>
<link href="{site_url}/"/>
<id>{site_url}/</id>
<updated>{updated}</updated>
{entries}
</feed>
"""

FEED_ENTRY_TEMPLATE = """<entry>
<title>{title}</title>
<link href="{url}"/>
<id>{url}</id>
<updated>{updated}</updated>
<content type="html">{content}</content>
</entry>"""

STYLE = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; max-width: 780px; margin: 2rem auto; padding: 0 1rem; line-height: 1.5; color: #1a1a1a; }
header { margin-bottom: 2rem; }
header a { text-decoration: none; color: #0969da; }
h2 { border-bottom: 1px solid #d0d7de; padding-bottom: .3rem; margin-top: 2.5rem; }
ul { padding-left: 1.2rem; }
li { margin: .25rem 0; }
.meta { color: #57606a; font-size: .9rem; }
pre { background: #f6f8fa; padding: 1rem; overflow-x: auto; border-radius: 6px; }
code { background: #f6f8fa; padding: .1rem .3rem; border-radius: 4px; }
pre code { background: none; padding: 0; }
a { color: #0969da; }
"""


def created_date(path):
    for args in (
        ["git", "log", "--follow", "--diff-filter=A", "--format=%ad", "--date=short", "--", str(path)],
        ["git", "log", "--follow", "--format=%ad", "--date=short", "--", str(path)],
    ):
        result = subprocess.run(args, cwd=root, capture_output=True, text=True, check=True)
        dates = result.stdout.strip().splitlines()
        if dates:
            return dates[-1]
    return "unknown"


def title_for(path, text):
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def strip_leading_title(text, title):
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == f"# {title}":
            return "\n".join(lines[:i] + lines[i + 1 :])
    return text


# Matches markdown links to a sibling .md file, e.g. [text](other-entry.md)
# or [text](other-entry.md#section). Deliberately excludes http(s):// links
# and anchors, since those are either external or don't need rewriting.
RELATIVE_MD_LINK_RE = re.compile(r"(?<=\]\()(?!https?://)([^)\s]+?)\.md(#[^)]*)?(?=\))")


def rewrite_relative_md_links(text):
    return RELATIVE_MD_LINK_RE.sub(lambda m: f"{m.group(1)}.html{m.group(2) or ''}", text)


def attr_escape(text):
    return escape(text, {'"': "&quot;"})


def build_sitemap(all_entries):
    urls = [SITEMAP_URL_TEMPLATE.format(loc=f"{SITE_URL}/", lastmod=max(e["date"] for e in all_entries))] if all_entries else []
    urls += [
        SITEMAP_URL_TEMPLATE.format(loc=e["url"], lastmod=e["date"])
        for e in sorted(all_entries, key=lambda e: e["url"])
    ]
    return SITEMAP_TEMPLATE.format(urls="\n".join(urls))


def build_feed(entries):
    entries = sorted(entries, key=lambda e: e["date"], reverse=True)[:FEED_ENTRY_LIMIT]
    updated = f"{entries[0]['date']}T00:00:00Z" if entries else "1970-01-01T00:00:00Z"
    entry_xml = "\n".join(
        FEED_ENTRY_TEMPLATE.format(
            title=escape(e["title"]),
            url=e["url"],
            updated=f"{e['date']}T00:00:00Z",
            content=escape(e["html_body"]),
        )
        for e in entries
    )
    return FEED_TEMPLATE.format(title=SITE_TITLE, site_url=SITE_URL, updated=updated, entries=entry_xml)


def main():
    if site.exists():
        shutil.rmtree(site)
    site.mkdir()

    formatter = HtmlFormatter(style="default")
    (site / "style.css").write_text(STYLE + "\n" + formatter.get_style_defs(".codehilite"))

    topics = []
    all_entries = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or entry.name in SKIP_DIRS or entry.name.startswith("."):
            continue
        md_files = sorted(entry.glob("*.md"))
        if not md_files:
            continue
        rows = []
        for md in md_files:
            text = md.read_text()
            title = title_for(md, text)
            date = created_date(md)
            slug = md.stem
            body_text = rewrite_relative_md_links(strip_leading_title(text, title))
            html_body = markdown.markdown(
                body_text,
                extensions=["fenced_code", "tables", "codehilite"],
                extension_configs={"codehilite": {"guess_lang": False}},
            )
            url = f"{SITE_URL}/{entry.name}/{slug}.html"
            description = attr_escape(plain_text_summary(html_body))
            out_dir = site / entry.name
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"{slug}.html").write_text(
                PAGE_TEMPLATE.format(
                    title=title,
                    topic=entry.name,
                    date=date,
                    body=html_body,
                    site_title=SITE_TITLE,
                    description=description,
                    author=SITE_AUTHOR,
                    url=url,
                )
            )
            row = {"title": title, "date": date, "slug": slug}
            rows.append(row)
            all_entries.append({**row, "topic": entry.name, "html_body": html_body, "url": url})
        rows.sort(key=lambda r: r["date"])
        topics.append((entry.name, rows, rows[0]["date"]))

    topics.sort(key=lambda t: t[2])

    total = len(all_entries)
    body_parts = []
    for topic, rows, _ in topics:
        body_parts.append(f"<h2>{topic}</h2>\n<ul>")
        for row in rows:
            body_parts.append(
                '<li><a href="{topic}/{slug}.html">{title}</a> - {date}</li>'.format(topic=topic, **row)
            )
        body_parts.append("</ul>")

    (site / "index.html").write_text(
        INDEX_TEMPLATE.format(
            title=SITE_TITLE,
            count=total,
            body="\n".join(body_parts),
            description=attr_escape(SITE_DESCRIPTION),
            author=SITE_AUTHOR,
            url=SITE_URL,
            person_schema=build_person_schema(),
            bing_verification_code=BING_VERIFICATION_CODE,
        )
    )
    (site / "feed.atom").write_text(build_feed(all_entries))
    (site / "sitemap.xml").write_text(build_sitemap(all_entries))
    (site / "robots.txt").write_text(ROBOTS_TXT.format(site_url=SITE_URL))


if __name__ == "__main__":
    main()
