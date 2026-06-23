#!/usr/bin/env python3
"""Add a ruff banned-api lint (rule TID251): ban an import or call whose mere
presence means a rule is broken — a "faithful shadow".

    python add_lint.py <banned.api> "<message that points at the rule>" [ruff.toml]

Maintains a dedicated ruff config it owns (marked by a header line). Idempotent.
It only touches files it created, so it can never clobber a real ruff.toml — point
it at a fresh path, e.g. src/my_package/pipes/ruff.toml (ruff applies the nearest
config). Stdlib only, so it runs under whatever python3 a hook happens to use.
"""

from __future__ import annotations

import re
import sys
import pathlib
import os
import json

MARKER = "# ruff config managed by add_lint.py — banned-api lints only"
_TOML_STRING = r'"(?:\\.|[^"\\])*"'
_BAN = re.compile(rf"^(?P<api>{_TOML_STRING})\.msg = (?P<msg>{_TOML_STRING})\s*$")
_EXTEND = re.compile(rf"^extend = (?P<path>{_TOML_STRING})\s*$")


def _has_ruff_config(path: pathlib.Path) -> bool:
    if path.name in {"ruff.toml", ".ruff.toml"}:
        return True
    if path.name != "pyproject.toml":
        return False
    try:
        text = path.read_text()
    except Exception:
        return False
    return "[tool.ruff" in text


def _nearest_parent_config(cfg: pathlib.Path) -> pathlib.Path | None:
    cfg_path = cfg.resolve()
    for parent in (cfg_path.parent, *cfg_path.parent.parents):
        for name in ("ruff.toml", ".ruff.toml", "pyproject.toml"):
            candidate = parent / name
            if candidate == cfg_path:
                continue
            if candidate.exists() and _has_ruff_config(candidate):
                return candidate
    return None


def _relative_extend_path(cfg: pathlib.Path, parent_config: pathlib.Path) -> str:
    return pathlib.Path(os.path.relpath(parent_config, start=cfg.parent.resolve())).as_posix()


def _toml_string(value: str) -> str:
    return json.dumps(value)


def _load_toml_string(value: str) -> str:
    return json.loads(value)


def main(argv) -> int:
    if len(argv) < 2:
        print(
            'usage: add_lint.py <banned.api> "<message>" [ruff.toml]', file=sys.stderr
        )
        return 2
    api, msg = argv[0], argv[1]
    cfg = pathlib.Path(argv[2]) if len(argv) > 2 else pathlib.Path("ruff.toml")

    bans = {}
    extend = None
    if cfg.exists():
        text = cfg.read_text()
        if not text.startswith(MARKER):
            print(
                f"refusing: {cfg} is not managed by this tool; add the ban by hand",
                file=sys.stderr,
            )
            return 1
        for line in text.splitlines():
            em = _EXTEND.match(line)
            if em:
                extend = _load_toml_string(em.group("path"))
            m = _BAN.match(line)
            if m:
                bans[_load_toml_string(m.group("api"))] = _load_toml_string(m.group("msg"))
    else:
        parent_config = _nearest_parent_config(cfg)
        if parent_config is not None:
            extend = _relative_extend_path(cfg, parent_config)

    if bans.get(api) == msg:
        print(f"already banned: {api}")
        return 0
    bans[api] = msg

    out = [
        MARKER,
    ]
    if extend:
        out.extend([f"extend = {_toml_string(extend)}", ""])
    out.extend([
        "[lint]",
        'extend-select = ["TID251"]',
        "",
        "[lint.flake8-tidy-imports.banned-api]",
    ])
    for k in sorted(bans):
        out.append(f"{_toml_string(k)}.msg = {_toml_string(bans[k])}")
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text("\n".join(out) + "\n")
    print(f"lint added: ban {api}  ({cfg})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
