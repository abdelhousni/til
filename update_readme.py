#!/usr/bin/env python3
"""Regenerate the README.md TIL index by scanning topic directories directly."""
import json
import pathlib
import re
import subprocess
import sys

root = pathlib.Path(__file__).parent.resolve()
SITE_URL = "https://til.housni.eu"
SKIP_DIRS = {".git", ".github", "__pycache__"}

index_re = re.compile(r"<!\-\- index starts \-\->.*<!\-\- index ends \-\->", re.DOTALL)
count_re = re.compile(r"<!\-\- count starts \-\->.*<!\-\- count ends \-\->", re.DOTALL)
COUNT_TEMPLATE = "<!-- count starts -->{}<!-- count ends -->"


def created_date_and_timestamp(path):
    """(YYYY-MM-DD, unix seconds) of the commit that first added this file.

    Same rule as build_site.py, so the README and the site list entries in
    the same order: the short date alone can't order two entries added on
    the same day.
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


def series_positions():
    """Map "topic/slug" to its position in its series.json series, if any.

    Entries added in one commit share a timestamp; their series order breaks
    the tie, as in build_site.py.
    """
    manifest = root / "series.json"
    if not manifest.exists():
        return {}
    positions = {}
    for series in json.loads(manifest.read_text()).values():
        for position, path in enumerate(series["entries"], start=1):
            positions[path.removesuffix(".md")] = position
    return positions


def title_for(path):
    for line in path.read_text().splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def collect_topics():
    positions = series_positions()
    topics = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or entry.name in SKIP_DIRS or entry.name.startswith("."):
            continue
        md_files = sorted(entry.glob("*.md"))
        if not md_files:
            continue
        rows = []
        for md in md_files:
            date, created_ts = created_date_and_timestamp(md)
            rows.append(
                {
                    "title": title_for(md),
                    "date": date,
                    "created_ts": created_ts,
                    "series_pos": positions.get(f"{entry.name}/{md.stem}", 0),
                    "topic": entry.name,
                    "slug": md.stem,
                }
            )
        rows.sort(key=lambda r: (r["created_ts"], r["series_pos"]))
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
