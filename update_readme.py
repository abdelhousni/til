#!/usr/bin/env python3
"""Regenerate the README.md TIL index by scanning topic directories directly."""
import pathlib
import re
import subprocess
import sys

root = pathlib.Path(__file__).parent.resolve()
SITE_URL = "https://abdelhousni.github.io/til"
SKIP_DIRS = {".git", ".github", "__pycache__"}

index_re = re.compile(r"<!\-\- index starts \-\->.*<!\-\- index ends \-\->", re.DOTALL)
count_re = re.compile(r"<!\-\- count starts \-\->.*<!\-\- count ends \-\->", re.DOTALL)
COUNT_TEMPLATE = "<!-- count starts -->{}<!-- count ends -->"


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


def title_for(path):
    for line in path.read_text().splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def collect_topics():
    topics = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or entry.name in SKIP_DIRS or entry.name.startswith("."):
            continue
        md_files = sorted(entry.glob("*.md"))
        if not md_files:
            continue
        rows = [
            {
                "title": title_for(md),
                "date": created_date(md),
                "topic": entry.name,
                "slug": md.stem,
            }
            for md in md_files
        ]
        rows.sort(key=lambda r: r["date"])
        topics.append((entry.name, rows, rows[0]["date"]))
    topics.sort(key=lambda t: t[2])
    return topics


def main():
    topics = collect_topics()
    total = sum(len(rows) for _, rows, _ in topics)

    index = ["<!-- index starts -->"]
    for topic, rows, _ in topics:
        index.append("## {}\n".format(topic))
        for row in rows:
            url = "{}/{topic}/{slug}.html".format(SITE_URL, **row)
            index.append("* [{title}]({url}) - {date}".format(url=url, **row))
        index.append("")
    if index[-1] == "":
        index.pop()
    index.append("<!-- index ends -->")

    if "--rewrite" in sys.argv:
        readme = root / "README.md"
        index_txt = "\n".join(index).strip()
        contents = readme.read_text()
        contents = index_re.sub(index_txt, contents)
        contents = count_re.sub(COUNT_TEMPLATE.format(total), contents)
        readme.write_text(contents)
    else:
        print("\n".join(index))


if __name__ == "__main__":
    main()
