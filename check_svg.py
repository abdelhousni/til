#!/usr/bin/env python3
"""Check the hand-written SVG diagrams that sit next to entries.

A diagram that Mermaid can't draw is a plain SVG file beside its entry,
shown with an <img> tag (build_site.py publishes it, check_links.py checks
that the <img src> exists). This script checks the things a browser won't
report: it shows nothing at all for an SVG that isn't well-formed XML, and
an <img> SVG silently drops anything it would load from elsewhere.

For every SVG file Git tracks, it fails when the file:
- isn't well-formed XML (for example, two hyphens in a row inside a comment);
- has no <title> (the accessible name; the <img alt> repeats it on the page);
- contains a <script> or an event handler attribute such as onload;
- refers to anything outside the file: an external href, a url() or an
  @import of another file, so the drawing stays self-contained.

Usage: python3 check_svg.py [FILE.svg ...]
With no arguments, checks every SVG file Git tracks. Standard library only,
so it needs no virtualenv and no package.
"""
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

SVG = "{http://www.w3.org/2000/svg}"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
# url(#id) points inside the file and is fine; any other url() loads a file.
EXTERNAL_URL = re.compile(r"url\(\s*['\"]?(?!#)|@import", re.IGNORECASE)


def problems(path):
    try:
        tree = ET.parse(path)
    except ET.ParseError as error:
        return [f"not well-formed XML: {error}"]
    root = tree.getroot()
    found = []
    if root.tag != f"{SVG}svg":
        found.append("root element isn't <svg> in the SVG namespace")
    if root.find(f"{SVG}title") is None:
        found.append("no <title> child of <svg>")
    for element in root.iter():
        name = element.tag.removeprefix(SVG)
        if name == "script":
            found.append("contains a <script>")
        for attribute, value in element.attrib.items():
            if attribute.lower().startswith("on"):
                found.append(f"<{name}> has an event handler, {attribute}")
            if attribute in ("href", XLINK_HREF) and not value.startswith("#"):
                found.append(f"<{name}> refers to another file: {value}")
            if EXTERNAL_URL.search(value):
                found.append(f"<{name}> {attribute} loads another file: {value}")
        if name == "style" and element.text and EXTERNAL_URL.search(element.text):
            found.append("<style> loads another file")
    return found


def main():
    files = sys.argv[1:] or subprocess.run(
        ["git", "ls-files", "*.svg"], capture_output=True, text=True, check=True
    ).stdout.split()
    failed = 0
    for path in files:
        for problem in problems(path):
            print(f"{path}: {problem}")
            failed += 1
    print(f"{len(files)} SVG file(s) checked, {failed} problem(s).")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
