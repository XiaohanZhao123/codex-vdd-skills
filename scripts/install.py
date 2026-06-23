#!/usr/bin/env python3
"""Install the workflow skills into a target repository."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ["planboard", "wrap", "docs-curator", "docs-librarian"]
AGENTS = [
    "planboard-researcher.toml",
    "planboard-synthesizer.toml",
    "planboard-verifier.toml",
    "wrap-curator.toml",
    "wrap-librarian.toml",
]
IGNORE_PATTERNS = shutil.ignore_patterns(
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".DS_Store",
)


def copy_tree(src: Path, dst: Path, *, force: bool) -> None:
    if src.resolve() == dst.resolve():
        raise SystemExit(f"refusing to install over source directory: {dst}")
    if dst.exists():
        if not force:
            raise SystemExit(f"exists: {dst} (pass --force to replace)")
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=IGNORE_PATTERNS)


def copy_file(src: Path, dst: Path, *, force: bool) -> None:
    if dst.exists() and not force:
        raise SystemExit(f"exists: {dst} (pass --force to replace)")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path, help="target repository root")
    parser.add_argument("--force", action="store_true", help="replace existing installed copies")
    args = parser.parse_args()

    target = args.target.resolve()
    if not target.exists() or not target.is_dir():
        raise SystemExit(f"target is not a directory: {target}")
    if target == ROOT:
        raise SystemExit("refusing to install this bundle into itself")

    for name in SKILLS:
        copy_tree(
            ROOT / ".codex" / "skills" / name,
            target / ".codex" / "skills" / name,
            force=args.force,
        )
    for name in AGENTS:
        copy_file(
            ROOT / ".codex" / "agents" / name,
            target / ".codex" / "agents" / name,
            force=args.force,
        )

    print(f"installed {len(SKILLS)} skills and {len(AGENTS)} agents into {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
