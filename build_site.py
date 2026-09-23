#!/usr/bin/env python3
"""Build the static GitHub Pages site (_site/) from the TIL markdown files."""
import html
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
    "https://mastodon.social/@abdelhousni",
]
SITE_DESCRIPTION = "Abdellatif Housni's Today I Learned notes: short, practical write-ups on things learned while building."
LLMS_TXT_SUMMARY = (
    "Short, practical write-ups on things learned while building -- Linux, containers, "
    "Kubernetes/RKE2, infrastructure-as-code, TLS and the tooling around them. "
    "{count} entries across {topic_count} topics, each one a self-contained page."
)
BING_VERIFICATION_CODE = "B109FF34ED264CD7CDA115D1B13A4C7F"
SKIP_DIRS = {".git", ".github", "__pycache__"}
SERIES_MANIFEST = root / "series.json"
FEED_ENTRY_LIMIT = 50
LLMS_TXT_EXCERPT_LIMIT = 200
RECENT_TILS_LIMIT = 10

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


def build_rel_me_links():
    return "\n".join(f'<link href="{url}" rel="me">' for url in AUTHOR_SAME_AS)


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
<link rel="alternate" type="text/markdown" href="{slug}.md">
<link rel="describedby" href="../llms.txt">
</head>
<body>
<header><a href="../index.html">&larr; All TILs</a> &middot; <a href="./">{topic}</a></header>
<main>
<h1>{title}</h1>
<p class="meta">{topic} - {date}</p>
{body}
{series_nav}</main>
{mermaid_script}</body>
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
<link rel="describedby" href="llms.txt">
{rel_me_links}
{person_schema}
</head>
<body>
<header>
<h1>{title}</h1>
<p>Things I've learned, collected in <a href="https://github.com/abdelhousni/til">abdelhousni/til</a>. Site pattern and tooling adapted from <a href="https://github.com/simonw/til">simonw/til</a>.<br>
<a href="https://www.linkedin.com/in/abdelhousni/"><img src="https://img.shields.io/badge/abdelhousni-0A66C2?style=flat&amp;logo=Linkedin&amp;logoColor=white&amp;labelColor=0A66C2" alt="LinkedIn Badge"></a>
</p>
<p>{count} TILs so far. <a href="feed.atom">Atom feed</a>.</p>
</header>
<main>
{body}
</main>
</body>
</html>
"""

TOPIC_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{topic} - {site_title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{description}">
<meta name="author" content="{author}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:title" content="{topic} - {site_title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{url}">
<link rel="stylesheet" href="../style.css">
<link rel="alternate" type="application/atom+xml" title="{site_title}" href="../feed.atom">
<link rel="describedby" href="../llms.txt">
</head>
<body>
<header><a href="../index.html">&larr; All TILs</a></header>
<main>
<h1>{topic}</h1>
<p class="meta">{count} TIL{plural} filed under {topic}.</p>
{body}
</main>
</body>
</html>
"""

SERIES_NAV_TEMPLATE = """<nav class="series" aria-label="Series navigation">
<p class="series-part">Part {position} of {total} in the <strong>{series_title}</strong> series</p>
<ul>
{links}
</ul>
</nav>
"""

SERIES_PREV_TEMPLATE = """<li class="series-prev">&larr; Previous: <a href="../{topic}/{slug}.html">{title}</a></li>"""
SERIES_NEXT_TEMPLATE = """<li class="series-next">Next: <a href="../{topic}/{slug}.html">{title}</a> &rarr;</li>"""

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
<author>
<name>{author}</name>
<uri>{site_url}/</uri>
</author>
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
h3 { margin: 1.5rem 0 .2rem; font-size: 1rem; }
ul { padding-left: 1.2rem; }
li { margin: .25rem 0; }
.meta { color: #57606a; font-size: .9rem; }
.topic { color: #57606a; font-size: .85rem; font-weight: normal; }
.topic a { color: inherit; }
pre { background: #f6f8fa; padding: 1rem; overflow-x: auto; border-radius: 6px; }
code { background: #f6f8fa; padding: .1rem .3rem; border-radius: 4px; }
pre code { background: none; padding: 0; }
a { color: #0969da; }
pre.mermaid { background: none; padding: 0; text-align: center; }
pre.mermaid svg { max-width: 100%; height: auto; }
nav.series { margin-top: 2.5rem; border-top: 1px solid #d0d7de; padding-top: 1rem; }
nav.series .series-part { color: #57606a; font-size: .9rem; margin: 0 0 .5rem; }
nav.series ul { list-style: none; padding: 0; margin: 0; }
nav.series li { margin: .35rem 0; }
ol.reading-order { padding-left: 1.4rem; }
ol.reading-order li { margin: .25rem 0; }
.elsewhere { color: #57606a; font-size: .85rem; }
"""

MERMAID_SCRIPT = """<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
  mermaid.initialize({ startOnLoad: true });
</script>
"""

# Matches a fenced ```mermaid ... ``` block. Pulled out and swapped for a raw
# <pre class="mermaid"> block *before* the text reaches python-markdown,
# because codehilite/fenced_code don't know "mermaid" as a language and would
# otherwise flatten it into an ordinary, unlabelled highlighted code block --
# indistinguishable from any other unrecognized language, so nothing could
# find it afterwards to render as a diagram.
MERMAID_FENCE_RE = re.compile(r"^```mermaid[ \t]*\n(.*?)\n^```[ \t]*$", re.DOTALL | re.MULTILINE)


def created_date_and_timestamp(path):
    """(YYYY-MM-DD, unix seconds) of the commit that first added this file.

    The date is what a reader sees; the timestamp is only ever a sort key.
    Both come out of one `git log` call so the two can never disagree.

    The timestamp exists because ordering by the short date alone stops
    being an ordering the moment two entries share a day, which happens
    routinely here. Python's sort is stable, so same-day entries keep the
    order the tree was walked in -- topic directory, then filename -- and
    the newest entry of the day lands below older ones under a heading
    that promises the opposite. Unix seconds also compare correctly across
    timezones, which an ISO-8601 string compared as text does not.

    A file with no creation commit yet sorts as though it were the newest
    thing in the repository, which is what a local preview of a draft
    wants, and matches what the "unknown" string happened to do before.
    """
    for args in (
        ["git", "log", "--follow", "--diff-filter=A", "--format=%ad\t%at", "--date=short", "--", str(path)],
        ["git", "log", "--follow", "--format=%ad\t%at", "--date=short", "--", str(path)],
    ):
        result = subprocess.run(args, cwd=root, capture_output=True, text=True, check=True)
        lines = result.stdout.strip().splitlines()
        if lines:
            date, _, stamp = lines[-1].partition("\t")
            return date, int(stamp)
    return "unknown", float("inf")


def last_modified_datetime(path):
    """Full ISO-8601 timestamp of the most recent commit touching this file.

    Atom's <updated> exists so feed readers can tell whether an entry
    changed since they last fetched it -- using the *creation* date here
    means an edited entry never looks updated to a subscriber, which is
    exactly the bug this fixes.
    """
    result = subprocess.run(
        ["git", "log", "-1", "--format=%aI", "--", str(path)],
        cwd=root, capture_output=True, text=True, check=True,
    )
    timestamp = result.stdout.strip()
    return timestamp if timestamp else "1970-01-01T00:00:00Z"


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


def build_sitemap(all_entries, topics):
    urls = [SITEMAP_URL_TEMPLATE.format(loc=f"{SITE_URL}/", lastmod=max(e["date"] for e in all_entries))] if all_entries else []
    # Topic indexes are real landing pages, not just directories -- without
    # them here a crawler only ever reaches a topic through the homepage.
    urls += [
        SITEMAP_URL_TEMPLATE.format(loc=f"{SITE_URL}/{topic}/", lastmod=max(r["date"] for r in rows))
        for topic, rows, _ in sorted(topics, key=lambda t: t[0])
    ]
    urls += [
        SITEMAP_URL_TEMPLATE.format(loc=e["url"], lastmod=e["date"])
        for e in sorted(all_entries, key=lambda e: e["url"])
    ]
    return SITEMAP_TEMPLATE.format(urls="\n".join(urls))


def build_llms_txt(all_entries, topics, series_nav):
    """An /llms.txt index, per the proposal at https://llmstxt.org/.

    Required shape, in order: an H1, a blockquote summary, any non-heading
    prose, then H2 sections whose lists are "[name](url): notes" links. The
    links point at the markdown twin of each entry rather than its HTML,
    since the whole point is to hand an agent something it can read directly.

    Topics are the sections, alphabetically, so every entry appears exactly
    once -- a series is noted inline on its members instead of getting its own
    section, which would list those entries twice.
    """
    lines = [
        f"# {SITE_TITLE}",
        "",
        "> " + LLMS_TXT_SUMMARY.format(count=len(all_entries), topic_count=len(topics)),
        "",
        "Every entry is published as markdown next to its HTML, at the same path with "
        "`.md` in place of `.html`; the links below point at the markdown. Sections are "
        "topics. Each line gives the entry's first-publication date, its place in a "
        "reading series where it has one, and how it opens.",
        "",
    ]
    for topic, rows, _ in sorted(topics, key=lambda t: t[0]):
        lines.append(f"## {topic}")
        lines.append("")
        for row in rows:
            entry = next(e for e in all_entries if e["topic"] == topic and e["slug"] == row["slug"])
            notes = [row["date"] + "."]
            info = series_nav.get(f"{topic}/{row['slug']}")
            if info:
                notes.append(
                    f'Part {info["position"]} of {info["total"]} in the {info["series_title"]} series.'
                )
            notes.append(html.unescape(plain_text_summary(entry["html_body"], limit=LLMS_TXT_EXCERPT_LIMIT)))
            url = entry["url"].removesuffix(".html") + ".md"
            lines.append(f'- [{row["title"]}]({url}): {" ".join(notes)}')
        lines.append("")
    lines += [
        "## Optional",
        "",
        f"- [Homepage]({SITE_URL}/): the rendered site, with the same entries grouped by topic.",
        f"- [Atom feed]({SITE_URL}/feed.atom): stamped by last modification, not first publication.",
        f"- [Sitemap]({SITE_URL}/sitemap.xml): every HTML page, including the per-topic indexes.",
        "- [Source repository](https://github.com/abdelhousni/til): the markdown these pages are built from.",
        "",
    ]
    return "\n".join(lines)


def build_feed(entries):
    # Sorted and stamped by last_modified, not creation date -- an edited
    # older entry should surface near the top and look "updated" to
    # subscribers, the same way any other feed behaves.
    entries = sorted(entries, key=lambda e: e["last_modified"], reverse=True)[:FEED_ENTRY_LIMIT]
    updated = entries[0]["last_modified"] if entries else "1970-01-01T00:00:00Z"
    entry_xml = "\n".join(
        FEED_ENTRY_TEMPLATE.format(
            title=escape(e["title"]),
            url=e["url"],
            updated=e["last_modified"],
            content=escape(e["html_body"]),
        )
        for e in entries
    )
    return FEED_TEMPLATE.format(title=SITE_TITLE, site_url=SITE_URL, author=SITE_AUTHOR, updated=updated, entries=entry_xml)


ORDINALS = [
    "First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth", "Ninth", "Tenth",
    "Eleventh", "Twelfth", "Thirteenth", "Fourteenth", "Fifteenth", "Sixteenth", "Seventeenth",
    "Eighteenth", "Nineteenth", "Twentieth",
]

# An intro line like "Fourth entry in the RKE2/Kubernetes series." Anchored to
# the start of a line on purpose, so a mid-sentence "the second entry" in some
# other article's prose isn't read as a series declaration.
SERIES_PROSE_RE = re.compile(r"^(\w+) entry in the .+? series\b", re.MULTILINE)


def ordinal_errors(articles, nav):
    """Entries whose declared ordinal disagrees with the manifest, or that declare one at all without being listed."""
    errors = []
    for article in articles:
        match = SERIES_PROSE_RE.search(article["text"])
        if not match:
            continue
        key = f"{article['topic']}/{article['slug']}"
        info = nav.get(key)
        if info is None:
            errors.append(
                f"{key}.md calls itself the {match.group(1).lower()} entry in a series, but no series in the manifest lists it"
            )
            continue
        expected = ORDINALS[info["position"] - 1] if info["position"] <= len(ORDINALS) else None
        if expected and match.group(1).lower() != expected.lower():
            errors.append(
                f"{key}.md says \"{match.group(1)} entry\", but '{info['series']}' lists it at position "
                f"{info['position']} (\"{expected}\")"
            )
    return errors


def load_series(articles):
    """Map "topic/slug" to its position in a series, from the series.json manifest.

    Reading order is a property of the series, not of any one article, so it
    lives in a single manifest rather than in per-article front matter.
    Reordering then touches one file instead of N, and can't silently skip or
    duplicate a position the way N independently-maintained ordinals can --
    which is exactly what had already drifted here: the first two entries of
    the RKE2 series never declared an ordinal at all, so nothing tied them to
    the seven that did. JSON rather than YAML keeps this stdlib-only.
    """
    if not SERIES_MANIFEST.exists():
        return {}

    by_key = {f"{a['topic']}/{a['slug']}": a for a in articles}
    manifest = json.loads(SERIES_MANIFEST.read_text())
    nav, listed_in, errors = {}, {}, []

    for series_key, series in manifest.items():
        keys = []
        for path in series["entries"]:
            key = path[:-3] if path.endswith(".md") else path
            if key not in by_key:
                errors.append(f"'{series_key}' lists {path}, which is not a TIL in this repo")
            elif key in listed_in:
                errors.append(f"'{series_key}' lists {path}, already listed in '{listed_in[key]}'")
            else:
                listed_in[key] = series_key
                keys.append(key)
        for position, key in enumerate(keys, start=1):
            nav[key] = {
                "series": series_key,
                "series_title": series["title"],
                "position": position,
                "total": len(keys),
                "entry": by_key[key],
                "prev": by_key[keys[position - 2]] if position > 1 else None,
                "next": by_key[keys[position]] if position < len(keys) else None,
            }

    errors += ordinal_errors(articles, nav)
    if errors:
        raise SystemExit("series.json is out of sync with the entries:\n  - " + "\n  - ".join(errors))
    return nav


def series_touching(topic, series_nav):
    """Every series with at least one entry in this topic, each in reading order.

    A series can span topics -- the HashiCorp one lives in terraform/ and
    packer/ -- so the whole series is returned, not just this topic's slice,
    and the caller marks the entries that live elsewhere.
    """
    keys = []
    for info in series_nav.values():
        if info["entry"]["topic"] == topic and info["series"] not in keys:
            keys.append(info["series"])
    sections = []
    for series_key in keys:
        members = sorted(
            (i for i in series_nav.values() if i["series"] == series_key),
            key=lambda i: i["position"],
        )
        sections.append((members[0]["series_title"], members))
    return sections


def build_topic_body(topic, rows, sections, entries_by_key):
    parts = []
    for series_title, members in sections:
        parts.append(f"<h2>Reading order: {escape(series_title)}</h2>")
        parts.append('<ol class="reading-order">')
        for info in members:
            entry = info["entry"]
            here = entry["topic"] == topic
            href = f'{entry["slug"]}.html' if here else f'../{entry["topic"]}/{entry["slug"]}.html'
            elsewhere = "" if here else f' <span class="elsewhere">in {entry["topic"]}</span>'
            parts.append(f'<li><a href="{href}">{escape(entry["title"])}</a>{elsewhere}</li>')
        parts.append("</ol>")
    if sections:
        parts.append("<h2>Everything in this topic, oldest first</h2>")
    # Title and date alone don't tell a reader whether an entry is the one they
    # want. Same first-paragraph excerpt the homepage's "Recent TILs" shows --
    # the topic label is dropped, since the page already is the topic.
    for row in rows:
        excerpt = plain_text_summary(entries_by_key[f"{topic}/{row['slug']}"]["html_body"], limit=280)
        parts.append(
            '<h3><a href="{slug}.html">{title}</a> - {date}</h3>\n<p>{excerpt}</p>'.format(
                slug=row["slug"], title=escape(row["title"]), date=row["date"], excerpt=excerpt
            )
        )
    return "\n".join(parts)


def render_series_nav(info):
    if not info:
        return ""
    links = []
    for template, neighbour in ((SERIES_PREV_TEMPLATE, info["prev"]), (SERIES_NEXT_TEMPLATE, info["next"])):
        if neighbour:
            links.append(
                template.format(topic=neighbour["topic"], slug=neighbour["slug"], title=escape(neighbour["title"]))
            )
    return SERIES_NAV_TEMPLATE.format(
        position=info["position"],
        total=info["total"],
        series_title=escape(info["series_title"]),
        links="\n".join(links),
    )


def main():
    if site.exists():
        shutil.rmtree(site)
    site.mkdir()

    formatter = HtmlFormatter(style="default")
    (site / "style.css").write_text(STYLE + "\n" + formatter.get_style_defs(".codehilite"))

    # Read every entry's title before rendering any page: a series nav block
    # links to its neighbours by title, so page N can't be written until
    # N-1 and N+1 have been read.
    articles = []
    for topic_dir in sorted(root.iterdir()):
        if not topic_dir.is_dir() or topic_dir.name in SKIP_DIRS or topic_dir.name.startswith("."):
            continue
        for md in sorted(topic_dir.glob("*.md")):
            text = md.read_text()
            articles.append(
                {
                    "path": md,
                    "text": text,
                    "topic": topic_dir.name,
                    "slug": md.stem,
                    "title": title_for(md, text),
                }
            )

    series_nav = load_series(articles)

    rows_by_topic = {}
    all_entries = []
    for article in articles:
        md, text, title = article["path"], article["text"], article["title"]
        topic, slug = article["topic"], article["slug"]
        date, created_ts = created_date_and_timestamp(md)
        last_modified = last_modified_datetime(md)
        body_text = rewrite_relative_md_links(strip_leading_title(text, title))
        body_text, has_mermaid = MERMAID_FENCE_RE.subn(
            lambda m: f'<pre class="mermaid">\n{escape(m.group(1))}\n</pre>', body_text
        )
        html_body = markdown.markdown(
            body_text,
            extensions=["fenced_code", "tables", "codehilite"],
            extension_configs={"codehilite": {"guess_lang": False}},
        )
        url = f"{SITE_URL}/{topic}/{slug}.html"
        description = attr_escape(plain_text_summary(html_body))
        out_dir = site / topic
        out_dir.mkdir(parents=True, exist_ok=True)
        # The markdown twin is the source verbatim: its relative links already
        # point at sibling .md files, which is exactly right once those are
        # published here too.
        (out_dir / f"{slug}.md").write_text(text)
        (out_dir / f"{slug}.html").write_text(
            PAGE_TEMPLATE.format(
                title=title,
                topic=topic,
                slug=slug,
                date=date,
                body=html_body,
                series_nav=render_series_nav(series_nav.get(f"{topic}/{slug}")),
                site_title=SITE_TITLE,
                description=description,
                author=SITE_AUTHOR,
                url=url,
                mermaid_script=MERMAID_SCRIPT if has_mermaid else "",
            )
        )
        row = {"title": title, "date": date, "created_ts": created_ts, "slug": slug}
        rows_by_topic.setdefault(topic, []).append(row)
        all_entries.append(
            {**row, "topic": topic, "html_body": html_body, "url": url, "last_modified": last_modified}
        )

    topics = []
    for topic, rows in rows_by_topic.items():
        rows.sort(key=lambda r: r["created_ts"])
        # Topics stay ordered by first-entry *date*, deliberately: several
        # topics were seeded on the same day, so switching this key to the
        # timestamp too would reshuffle every section on the homepage to fix
        # an ordering nobody reads as chronological. The entries inside each
        # topic are what had to be corrected.
        topics.append((topic, rows, rows[0]["date"]))

    topics.sort(key=lambda t: t[2])

    total = len(all_entries)

    # "Browse by topic:" -- same idea as til.simonwillison.net's own homepage,
    # adapted for a static site: his links to a separate Datasette page per
    # topic, ours jumps to that topic's <h2> section further down this same
    # page, since there's no per-topic filtering backend here.
    browse_links = " &middot; ".join(
        '<a href="#{topic}" title="{count} TIL{plural}">{topic}</a> {count}'.format(
            topic=topic, count=len(rows), plural="" if len(rows) == 1 else "s"
        )
        for topic, rows, _ in sorted(topics, key=lambda t: t[0])
    )
    body_parts = [f"<p><strong>Browse by topic:</strong> {browse_links}</p>"]

    # "Recent TILs" -- same section til.simonwillison.net's own homepage
    # leads with: a reverse-chronological feed of the latest entries with a
    # short excerpt each, distinct from the exhaustive per-topic lists below.
    recent = sorted(all_entries, key=lambda e: e["created_ts"], reverse=True)[:RECENT_TILS_LIMIT]
    if recent:
        body_parts.append("<h2>Recent TILs</h2>")
        for e in recent:
            excerpt = plain_text_summary(e["html_body"], limit=280)
            body_parts.append(
                '<h3><span class="topic"><a href="#{topic}">{topic}</a></span> '
                '<a href="{topic}/{slug}.html">{title}</a> - {date}</h3>\n<p>{excerpt}</p>'.format(
                    topic=e["topic"], slug=e["slug"], title=e["title"], date=e["date"], excerpt=excerpt
                )
            )

    for topic, rows, _ in topics:
        body_parts.append(f'<h2 id="{topic}"><a href="{topic}/">{topic}</a></h2>\n<ul>')
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
            rel_me_links=build_rel_me_links(),
            url=SITE_URL,
            person_schema=build_person_schema(),
            bing_verification_code=BING_VERIFICATION_CODE,
        )
    )
    entries_by_key = {f"{e['topic']}/{e['slug']}": e for e in all_entries}
    for topic, rows, _ in topics:
        topic_url = f"{SITE_URL}/{topic}/"
        plural = "" if len(rows) == 1 else "s"
        (site / topic / "index.html").write_text(
            TOPIC_TEMPLATE.format(
                topic=topic,
                count=len(rows),
                plural=plural,
                body=build_topic_body(topic, rows, series_touching(topic, series_nav), entries_by_key),
                site_title=SITE_TITLE,
                description=attr_escape(f"{len(rows)} TIL{plural} filed under {topic} on {SITE_TITLE}."),
                author=SITE_AUTHOR,
                url=topic_url,
            )
        )

    (site / "feed.atom").write_text(build_feed(all_entries))
    (site / "sitemap.xml").write_text(build_sitemap(all_entries, topics))
    (site / "robots.txt").write_text(ROBOTS_TXT.format(site_url=SITE_URL))
    (site / "llms.txt").write_text(build_llms_txt(all_entries, topics, series_nav))


if __name__ == "__main__":
    main()
