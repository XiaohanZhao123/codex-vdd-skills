#!/usr/bin/env python3
"""Find doc lines that cite a repo path a commit DELETED — a faithful "this line is
stale" shadow for the Curator's RETIRE move. Prints candidates; never edits.

    python scan_dead_refs.py [docs_dir ...]      # default: docs

For each backticked, anchored, full repo path in <docs_dir>/**/*.md that BOTH
(a) no longer exists on disk AND (b) `git log --diff-filter=D` shows a real deleting
commit, print the citing doc line and the commit that killed the path. This is the
one retire signal worth trusting: a path either exists in git history or it doesn't,
so detection needs no judgment.

Two kinds of line are deliberately NOT flagged:
  - lines under a HISTORICAL / legacy / superseded heading, or carrying that
    vocabulary inline or on a neighboring line — those cite dead paths ON PURPOSE
    (audit trail, or saying right beside it that the path moved);
  - paths that were NEVER tracked in this repo (cross-repo or illustrative names) —
    absence proves nothing without a deletion in *this* repo's history.

A rename also registers as a deletion of the old path, so each candidate ships its
commit: if the thing merely moved, the Curator proposes fixing the path, not cutting
the line. Stdlib + git only; runs under whatever python3 is available.
"""

import re
import sys
import subprocess
import pathlib

# A citation must be an anchored, full repo path to be checkable — a bare basename
# (`stage.py`) or a partial (`pipes/base.py`) resolves elsewhere and proves nothing.
# `openspec/` is deliberately excluded: archiving a change MOVES it under
# openspec/changes/archive/, which registers as a deletion of the old path — a
# normal lifecycle move, not doc rot, and it would flood the retire list.
_TOP = ("src/", "scripts/", "configs/", "docs/", "tests/")
_EXT = (
    ".py",
    ".md",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".toml",
    ".sh",
    ".html",
    ".cfg",
    ".ini",
    ".txt",
)
_BACKTICK = re.compile(r"`([^`]+)`")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s")
_HIST = re.compile(
    r"historical|legacy|superseded|supersede|archaeolog|deprecat|"
    r"do not use|don'?t use|old way|retained for|no longer",
    re.I,
)


def anchored(tok):
    """True iff tok is a full, checkable repo path (not a basename/partial/glob)."""
    if any(c in tok for c in "<>{}*: ") or "\t" in tok:
        return False
    if not tok.startswith(_TOP):
        return False
    return tok.endswith(_EXT)


def git_deleted(path):
    """The 'short-hash subject' of the commit that deleted path, else None."""
    try:
        r = subprocess.run(
            [
                "git",
                "log",
                "-1",
                "--diff-filter=D",
                "--all",
                "--format=%h %s",
                "--",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return None
    out = r.stdout.strip()
    return out or None


def scan_doc(doc, window=3):
    """Yield (line_no, line_text, dead_path, deleting_commit) for doc.

    A citation is skipped when its section heading is historical OR any line within
    `window` lines carries the marker vocabulary — docs often cite a dead path while
    saying right beside it that it moved ("there is no longer a separate `X`"), and
    that adjacent line is the doc being correct, not stale. Checking only the
    citation's own line would miss it.
    """
    lines = doc.read_text(errors="replace").splitlines()
    section_hist = [False] * len(lines)
    cur = False
    for idx, raw in enumerate(lines):
        if _HEADING.match(raw):
            cur = bool(_HIST.search(raw))
        section_hist[idx] = cur

    out = []
    for idx, raw in enumerate(lines):
        lo, hi = max(0, idx - window), min(len(lines), idx + window + 1)
        if section_hist[idx] or any(_HIST.search(lines[j]) for j in range(lo, hi)):
            continue  # historical context cites dead paths on purpose — skip
        for tok in _BACKTICK.findall(raw):
            tok = tok.strip()
            if not anchored(tok) or pathlib.Path(tok).exists():
                continue
            ev = git_deleted(tok)
            if ev:
                out.append((idx + 1, raw.strip(), tok, ev))
    return out


def main(argv):
    dirs = argv or ["docs"]
    seen = set()
    n = 0
    for d in dirs:
        for doc in sorted(pathlib.Path(d).rglob("*.md")):
            for ln, text, tok, ev in scan_doc(doc):
                key = (str(doc), ln, tok)
                if key in seen:
                    continue
                seen.add(key)
                n += 1
                print(f"=== {doc}:{ln}  cites deleted `{tok}` ===")
                print(f"    line: {text[:200]}")
                print(f"    deleted by: {ev}")
                print(f"    recover: git show HEAD:{doc}")
                print()
    if n == 0:
        print(
            "no dead-reference candidates "
            "(every cited repo path still exists, is HISTORICAL-marked, or was never tracked)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
