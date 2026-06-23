#!/usr/bin/env python3
"""Wire a doc to a code area: add (or update) a "<path-prefix>": "<doc>" entry in
the doc-push hook's doc-map.json, so editing files under that prefix pushes the doc.

    python add_doc_link.py <path-prefix> <doc-path> [doc-map.json]

Idempotent; preserves the rest of the map; validates JSON. Use this instead of
hand-editing the file so the link format can't drift.
"""

import json
import sys
import pathlib


def main(argv: list) -> int:
    if len(argv) < 2:
        print(
            "usage: add_doc_link.py <path-prefix> <doc-path> [doc-map.json]",
            file=sys.stderr,
        )
        return 2
    prefix, doc = argv[0], argv[1]
    mp = (
        pathlib.Path(argv[2])
        if len(argv) > 2
        else pathlib.Path(".codex/hooks/doc-map.json")
    )

    data = {}
    if mp.exists():
        try:
            data = json.loads(mp.read_text())
        except json.JSONDecodeError as e:
            print(f"error: {mp} is not valid JSON ({e})", file=sys.stderr)
            return 1
        if not isinstance(data, dict):
            print(f"error: {mp} is not a JSON object", file=sys.stderr)
            return 1

    if data.get(prefix) == doc:
        print(f"already linked: {prefix} -> {doc}")
        return 0

    data[prefix] = doc
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"linked: {prefix} -> {doc}  ({mp})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
