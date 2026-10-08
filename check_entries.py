#!/usr/bin/env python3
"""Advisory check: ask Jev whether TIL entries follow the writing conventions.

Jev is a "decision model": it doesn't write text, it answers typed questions
about some text you give it. Here every question is a `noul` -- a calibrated
yes/no returned as a probability between 0.0 (no) and 1.0 (yes) -- so the
answer is a number this script can compare with a threshold, not prose it has
to parse.

The rule being checked comes from CLAUDE.md ("Writing TIL entries"): explain
every term the first time an entry relies on it, link to an earlier entry
that already does, and never point to a *later* entry for a definition the
current one needs. A regex can't tell whether a term is explained; a model
can at least give a second opinion.

This is a review aid, not a gate. A judgment can be wrong, so the script
prints entries worth a second look and always exits 0 (unless the API itself
can't be reached and --strict is given). It also sends the text of each entry
to the Jev service, which is fine for this public repository and the reason
it must never be pointed at private notes.

Usage:
    export JEV_API_KEY=jv_live_...             # never commit or print this
    python3 check_entries.py                   # every entry
    python3 check_entries.py ansible/foo.md    # just these files
    python3 check_entries.py --changed origin/main   # files changed vs a ref
    python3 check_entries.py --dry-run         # show the request, send nothing

Endpoint: by default the hosted proxy https://jevtypesafeai.com/api/v1/decide
(keys look like jv_live_...). To use TypeSafe's own API instead, set
JEV_URL=https://api.typesafe.ai/v1/systemone and use a TypeSafe key; the
request body is the same shape.

Standard library only, so it runs without the virtualenv.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys
import urllib.error
import urllib.request

root = pathlib.Path(__file__).parent.resolve()

DEFAULT_URL = "https://jevtypesafeai.com/api/v1/decide"
TIMEOUT = 30

# Jev bills per input token and the longest entry is ~25 KB, so there is no
# need to trim today. The cap is a guard against someone pasting a huge file.
MAX_CHARS = 30_000

# An answer at or above this probability is reported. Start high so the first
# runs show only the clear cases; lower it with --threshold once you have seen
# how noisy the questions are on real entries.
THRESHOLD = 0.70

# One yes/no question per way an entry can break the rule. Several questions
# go in one request: they are evaluated in parallel and the entry text, which
# is the expensive part, is only billed once. The answers are *problems*, so
# "yes" (a high probability) is the bad outcome for every one of them.
QUESTIONS = {
    "undefined_term": {
        "type": "noul",
        "instructions": (
            "The reader knows the Linux command line and Git but is new to "
            "this entry's subject. Does the text use a term specific to that "
            "subject, such as a tool, file format, protocol or concept, "
            "without defining it where it first appears and without linking "
            "to an entry or page that does? Everyday command-line and "
            "programming vocabulary does not count."
        ),
    },
    "forward_reference": {
        "type": "noul",
        "instructions": (
            "Does the text send the reader to a later or next entry, part or "
            "section for a definition or step that they need in order to "
            "follow the text they are reading now? A pointer to further "
            "reading, a mention of a future topic, or the word 'later' "
            "meaning a time or a version number does not count."
        ),
    },
    "untested_claim": {
        "type": "noul",
        "instructions": (
            "Does the text present commands or configuration as something "
            "that works or was tried, for example by showing their output or "
            "saying they were run, while never naming a version, an "
            "operating system or an environment? Text that openly attributes "
            "its claims to documentation or to another source, and does not "
            "say it ran anything, does not count."
        ),
    },
}


def entries(paths):
    """Return the entry files to check, as paths relative to the repo root.

    An entry is a Markdown file directly inside a topic directory -- the same
    rule update_readme.py and build_site.py use -- so README.md, CLAUDE.md
    and anything nested deeper are skipped.
    """
    if paths:
        return [pathlib.Path(p) for p in paths]
    found = []
    for topic in sorted(root.iterdir()):
        if topic.is_dir() and not topic.name.startswith((".", "_")) and topic.name != "node_modules":
            found.extend(p.relative_to(root) for p in sorted(topic.glob("*.md")))
    return found


def changed_entries(ref):
    """Entries added or modified since `ref` (e.g. origin/main).

    Three sources, because a draft is usually not committed yet: commits since
    `ref`, uncommitted edits to tracked files, and brand-new untracked files.
    """
    def git(*args):
        return subprocess.run(["git", *args], cwd=root, capture_output=True,
                              text=True, check=True).stdout.split("\n")

    names = set(git("diff", "--name-only", "--diff-filter=AM", f"{ref}...HEAD", "--", "*.md"))
    names |= set(git("diff", "--name-only", "--diff-filter=AM", "HEAD", "--", "*.md"))
    names |= set(git("ls-files", "--others", "--exclude-standard", "--", "*.md"))
    wanted = {str(p) for p in entries([])}
    return sorted(pathlib.Path(n) for n in names if n in wanted)


def decide(url, key, text):
    """POST one entry's text and the QUESTIONS; return the `answers` mapping."""
    body = json.dumps({"state": text[:MAX_CHARS], "questions": QUESTIONS}).encode()
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.load(response)["answers"]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("files", nargs="*", help="entries to check (default: all)")
    parser.add_argument("--changed", metavar="REF", help="only entries changed since REF")
    parser.add_argument("--threshold", type=float, default=THRESHOLD,
                        help=f"report answers at or above this probability (default {THRESHOLD})")
    parser.add_argument("--dry-run", action="store_true", help="print the first request, send nothing")
    parser.add_argument("--strict", action="store_true", help="exit 1 if the API can't be reached")
    args = parser.parse_args()

    files = changed_entries(args.changed) if args.changed else entries(args.files)
    if not files:
        print("No entries to check.")
        return 0

    if args.dry_run:
        print(json.dumps({"state": f"<text of {files[0]}>", "questions": QUESTIONS}, indent=2))
        print(f"\n{len(files)} entries would be checked.")
        return 0

    key = os.environ.get("JEV_API_KEY")
    if not key:
        print("JEV_API_KEY is not set; nothing checked.", file=sys.stderr)
        return 1 if args.strict else 0
    url = os.environ.get("JEV_URL", DEFAULT_URL)

    flagged = 0
    for path in files:
        try:
            answers = decide(url, key, (root / path).read_text())
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
            # Say what failed but never echo the request: it carries the key's
            # header, and URLError's text is enough to diagnose.
            print(f"{path}: Jev call failed ({type(exc).__name__}: {exc})", file=sys.stderr)
            if args.strict:
                return 1
            continue
        hits = {name: a["noul"] for name, a in answers.items() if a["noul"] >= args.threshold}
        if hits:
            flagged += 1
            detail = ", ".join(f"{name} {p:.2f}" for name, p in sorted(hits.items(), key=lambda kv: -kv[1]))
            print(f"{path}: {detail}")

    print(f"\n{flagged} of {len(files)} entries flagged at threshold {args.threshold}.")
    print("Advisory only: read the entry before changing it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
