#!/usr/bin/env python3
"""Build the static GitHub Pages site (_site/) from the TIL markdown files."""
import pathlib
import shutil
import subprocess
import sys

root = pathlib.Path(__file__).parent.resolve()

# The repo has a topic directory literally named "markdown/", which shadows
# the pip "markdown" package via the script-directory entry Python adds to
# sys.path. Drop that entry before importing so the real package is found.
sys.path = [p for p in sys.path if p not in ("", ".", str(root))]

import markdown  # noqa: E402
site = root / "_site"
SITE_TITLE = "Abdel Housni: TIL"
SKIP_DIRS = {".git", ".github", "__pycache__"}

PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title} - TIL</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="../style.css">
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
<link rel="stylesheet" href="style.css">
</head>
<body>
<header><h1>{title}</h1><p>{count} TILs so far.</p></header>
<main>
{body}
</main>
</body>
</html>
"""

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


def main():
    if site.exists():
        shutil.rmtree(site)
    site.mkdir()
    (site / "style.css").write_text(STYLE)

    topics = []
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
            body_text = strip_leading_title(text, title)
            html_body = markdown.markdown(body_text, extensions=["fenced_code", "tables"])
            out_dir = site / entry.name
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"{slug}.html").write_text(
                PAGE_TEMPLATE.format(title=title, topic=entry.name, date=date, body=html_body)
            )
            rows.append({"title": title, "date": date, "slug": slug})
        rows.sort(key=lambda r: r["date"])
        topics.append((entry.name, rows, rows[0]["date"]))

    topics.sort(key=lambda t: t[2])

    total = sum(len(rows) for _, rows, _ in topics)
    body_parts = []
    for topic, rows, _ in topics:
        body_parts.append(f"<h2>{topic}</h2>\n<ul>")
        for row in rows:
            body_parts.append(
                '<li><a href="{topic}/{slug}.html">{title}</a> - {date}</li>'.format(topic=topic, **row)
            )
        body_parts.append("</ul>")

    (site / "index.html").write_text(
        INDEX_TEMPLATE.format(title=SITE_TITLE, count=total, body="\n".join(body_parts))
    )


if __name__ == "__main__":
    main()
