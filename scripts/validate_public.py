#!/usr/bin/env python3
"""Validate the public skill bundle."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError as exc:  # pragma: no cover - direct CLI diagnostic
    raise SystemExit(
        "scripts/validate_public.py requires Python 3.11+ so agent TOML files "
        "are parsed instead of skipped"
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SKILLS = {
    "verifier-driven-development",
    "planboard",
    "shuorenhua",
    "wrap",
    "docs-curator",
    "docs-librarian",
}
EXPECTED_AGENTS = {
    "vdd-spec-reviewer.toml",
    "vdd-plan-reviewer.toml",
    "planboard-researcher.toml",
    "planboard-synthesizer.toml",
    "planboard-verifier.toml",
    "wrap-curator.toml",
    "wrap-librarian.toml",
}
FORBIDDEN = [
    "CUA" + "_mobile",
    "cua" + "-mobile",
    "xiao" + "han",
    "Xiao" + "han",
    "/" + "home" + "/" + "qid",
    "/" + "data" + "drive",
    "t2v" + "gusw2",
    "v-" + "zhihong",
    "MS" + "RA",
]
TEXT_EXTS = {".md", ".py", ".toml", ".json", ".txt", ".yaml", ".yml"}


def iter_text_files():
    for path in ROOT.rglob("*"):
        if ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if path.is_file() and path.suffix in TEXT_EXTS:
            yield path


def check_forbidden() -> list[str]:
    hits: list[str] = []
    for path in iter_text_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for needle in FORBIDDEN:
            if needle in text:
                rel = path.relative_to(ROOT)
                hits.append(f"{rel}: contains {needle!r}")
    return hits


def check_sample_plan() -> list[str]:
    errors: list[str] = []
    path = ROOT / "examples" / "sample-plan.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - direct CLI diagnostics
        return [f"{path.relative_to(ROOT)}: invalid JSON: {exc}"]
    if not isinstance(data.get("steps"), list) or not data["steps"]:
        errors.append("examples/sample-plan.json: missing non-empty steps")
    for idx, step in enumerate(data.get("steps", []), start=1):
        for key in ("id", "title", "what", "verification"):
            if not step.get(key):
                errors.append(f"examples/sample-plan.json step {idx}: missing {key}")
    return errors


def check_vendored_attribution() -> list[str]:
    errors: list[str] = []
    readme = (ROOT / "README.md").read_text(encoding="utf-8", errors="replace")
    if "MrGeDiao/shuorenhua" not in readme or "MIT" not in readme:
        errors.append("README.md: missing shuorenhua upstream attribution")
    if (
        "obra/superpowers" not in readme
        or "Copyright (c) 2025 Jesse Vincent" not in readme
        or "MIT" not in readme
    ):
        errors.append("README.md: missing Superpowers upstream attribution")
    vdd_text = (
        ROOT / ".codex" / "skills" / "verifier-driven-development" / "SKILL.md"
    ).read_text(encoding="utf-8", errors="replace")
    if (
        "https://github.com/obra/superpowers" not in vdd_text
        or "Copyright (c) 2025 Jesse Vincent" not in vdd_text
    ):
        errors.append("verifier-driven-development: missing Superpowers attribution")
    license_path = ROOT / ".codex" / "skills" / "shuorenhua" / "LICENSE"
    if not license_path.exists():
        errors.append(".codex/skills/shuorenhua/LICENSE: missing vendored MIT license")
    else:
        license_text = license_path.read_text(encoding="utf-8", errors="replace")
        if "Copyright (c) 2026 MrGeDiao" not in license_text:
            errors.append(".codex/skills/shuorenhua/LICENSE: unexpected copyright notice")
    return errors


def check_skill_bundle() -> list[str]:
    errors: list[str] = []
    skill_root = ROOT / ".codex" / "skills"
    present = {path.name for path in skill_root.iterdir() if path.is_dir()}
    missing = sorted(EXPECTED_SKILLS - present)
    extra = sorted(present - EXPECTED_SKILLS)
    if missing:
        errors.append(f"missing expected skills: {', '.join(missing)}")
    if extra:
        errors.append(f"unexpected skills: {', '.join(extra)}")
    for name in sorted(EXPECTED_SKILLS & present):
        skill_file = skill_root / name / "SKILL.md"
        if not skill_file.exists():
            errors.append(f"{name}: missing SKILL.md")
            continue
        text = skill_file.read_text(encoding="utf-8", errors="replace")
        if f"name: {name}" not in text.split("---", 2)[1]:
            errors.append(f"{name}: frontmatter name does not match folder")
    return errors


def check_agent_bundle() -> list[str]:
    errors: list[str] = []
    agent_root = ROOT / ".codex" / "agents"
    present = {path.name for path in agent_root.iterdir() if path.is_file()}
    missing = sorted(EXPECTED_AGENTS - present)
    extra = sorted(present - EXPECTED_AGENTS)
    if missing:
        errors.append(f"missing expected agents: {', '.join(missing)}")
    if extra:
        errors.append(f"unexpected agents: {', '.join(extra)}")
    for filename in sorted(EXPECTED_AGENTS & present):
        path = agent_root / filename
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{filename}: invalid TOML: {exc}")
            continue
        expected_name = filename.removesuffix(".toml")
        if data.get("name") != expected_name:
            errors.append(f"{filename}: name must be {expected_name!r}")
        for key in ("description", "developer_instructions"):
            value = data.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{filename}: missing non-empty {key}")
        nicknames = data.get("nickname_candidates")
        if nicknames is not None and not (
            isinstance(nicknames, list)
            and all(isinstance(item, str) and item for item in nicknames)
        ):
            errors.append(f"{filename}: nickname_candidates must be a string list")
    return errors



def check_renderer() -> list[str]:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "missing" / "nested" / "planboard-public-validate.html"
        injected_plan = Path(tmp) / "injected-plan.json"
        injected_out = Path(tmp) / "injected-plan.html"
        unicode_plan = Path(tmp) / "unicode-plan.json"
        unicode_out = Path(tmp) / "unicode-plan.html"
        token_plan = Path(tmp) / "token-plan.json"
        token_out = Path(tmp) / "token-plan.html"
        revision_plan = Path(tmp) / "revision-plan.json"
        revision_out = Path(tmp) / "revision-plan.html"
        cmd = [
            sys.executable,
            str(ROOT / ".codex" / "skills" / "planboard" / "render_planboard.py"),
            str(ROOT / "examples" / "sample-plan.json"),
            str(out),
            "--slug",
            'bad"slug',
        ]
        result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            return [f"renderer failed: {result.stderr.strip() or result.stdout.strip()}"]
        text = out.read_text(encoding="utf-8", errors="replace")
        injected_plan.write_text(
            json.dumps(
                {
                    "task": 'x </script><script>globalThis.pwned=1</script>',
                    "round": 1,
                    "headline": "h",
                    "steps": [
                        {
                            "id": "step-1",
                            "title": "t",
                            "what": "w",
                            "verification": "v",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        injected_result = subprocess.run(
            [
                sys.executable,
                str(ROOT / ".codex" / "skills" / "planboard" / "render_planboard.py"),
                str(injected_plan),
                str(injected_out),
                "--slug",
                "script-check",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if injected_result.returncode != 0:
            return [
                "renderer failed on script-injection fixture: "
                f"{injected_result.stderr.strip() or injected_result.stdout.strip()}"
            ]
        injected_text = injected_out.read_text(encoding="utf-8", errors="replace")
        unicode_plan.write_text(
            json.dumps(
                {
                    "task": "迁移功能",
                    "round": 1,
                    "headline": "h",
                    "steps": [
                        {
                            "id": "step-1",
                            "title": "t",
                            "what": "w",
                            "verification": "v",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        unicode_result = subprocess.run(
            [
                sys.executable,
                str(ROOT / ".codex" / "skills" / "planboard" / "render_planboard.py"),
                str(unicode_plan),
                str(unicode_out),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if unicode_result.returncode != 0:
            return [
                "renderer failed on unicode slug fixture: "
                f"{unicode_result.stderr.strip() or unicode_result.stdout.strip()}"
            ]
        token_plan.write_text(
            json.dumps(
                {
                    "task": "Render __ROUND__ and __ALTS__ literally",
                    "round": 3,
                    "headline": "Keep __DATE__ literal",
                    "steps": [
                        {
                            "id": "step-1",
                            "title": "t",
                            "summary": "mentions __ALTS__",
                            "what": "w",
                            "verification": "v",
                        }
                    ],
                    "alternatives_considered": [{"approach": "A", "why_not": "B"}],
                }
            ),
            encoding="utf-8",
        )
        token_result = subprocess.run(
            [
                sys.executable,
                str(ROOT / ".codex" / "skills" / "planboard" / "render_planboard.py"),
                str(token_plan),
                str(token_out),
                "--slug",
                "token-check",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if token_result.returncode != 0:
            return [
                "renderer failed on placeholder-token fixture: "
                f"{token_result.stderr.strip() or token_result.stdout.strip()}"
            ]
        token_text = token_out.read_text(encoding="utf-8", errors="replace")
        revision_plan.write_text(
            json.dumps(
                {
                    "task": "Revision visibility",
                    "round": 2,
                    "headline": "Show changed steps first.",
                    "changes_from_previous_round": [
                        {
                            "step_id": "step-1",
                            "status": "改",
                            "change": "Clarified the active entrypoint.",
                        },
                    ],
                    "steps": [
                        {
                            "id": "step-1",
                            "title": "t",
                            "what": "w",
                            "verification": "v",
                        },
                        {
                            "id": "step-2",
                            "title": "unchanged",
                            "what": "unchanged body",
                            "verification": "unchanged verifier",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        revision_result = subprocess.run(
            [
                sys.executable,
                str(ROOT / ".codex" / "skills" / "planboard" / "render_planboard.py"),
                str(revision_plan),
                str(revision_out),
                "--slug",
                "revision-check",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if revision_result.returncode != 0:
            return [
                "renderer failed on revision-visibility fixture: "
                f"{revision_result.stderr.strip() or revision_result.stdout.strip()}"
            ]
        revision_text = revision_out.read_text(encoding="utf-8", errors="replace")
    if "step-1-contract" not in text or "复制批注" not in text:
        return ["renderer output is missing expected sample content"]
    if 'var KEY = "planboard_bad-slug_r1";' not in text:
        return ["renderer did not sanitize the slug before embedding it in JavaScript"]
    if 'var TASK = "x \\u003c/script>\\u003cscript>globalThis.pwned=1\\u003c/script>";' not in injected_text:
        return ["renderer did not protect JSON strings embedded in a script tag"]
    if "slug=plan-" not in unicode_result.stdout:
        return ["renderer did not create a stable unique slug for non-ASCII task text"]
    if (
        "Render __ROUND__ and __ALTS__ literally" not in token_text
        or "Keep __DATE__ literal" not in token_text
        or "mentions __ALTS__" not in token_text
    ):
        return ["renderer replaced placeholder-like text from the input plan"]
    if (
        "本轮改动" not in revision_text
        or "Clarified the active entrypoint." not in revision_text
        or 'href="#pb-step-1"' not in revision_text
        or '<div class="step changed-step" id="pb-step-1"' not in revision_text
    ):
        return ["renderer did not expose revision changes as linked highlighted steps"]
    if "Accepted step stayed fixed." in revision_text:
        return ["renderer revision fixture includes an unchanged accepted step in the delta layer"]
    return []


def check_transcript_scanner() -> list[str]:
    scanner = ROOT / ".codex" / "skills" / "docs-curator" / "scripts" / "scan_transcripts.py"
    triggers = ROOT / ".codex" / "skills" / "docs-curator" / "triggers.txt"
    normal = {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "Document this behavior"}],
        },
    }
    event_msg = {
        "type": "event_msg",
        "payload": {
            "type": "user_message",
            "message": "Document this event stream behavior",
            "images": [],
            "local_images": [],
        },
    }
    subagent_meta = {
        "type": "session_meta",
        "payload": {"thread_source": "subagent", "source": {"subagent": "review"}},
    }
    bootstrap = {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": "# AGENTS.md instructions for /repo\nDocument this guidance",
                }
            ],
        },
    }
    with tempfile.TemporaryDirectory() as tmp:
        normal_path = Path(tmp) / "normal.jsonl"
        event_path = Path(tmp) / "event.jsonl"
        dup_path = Path(tmp) / "duplicate.jsonl"
        bootstrap_path = Path(tmp) / "bootstrap.jsonl"
        subagent_path = Path(tmp) / "subagent.jsonl"
        normal_path.write_text(json.dumps(normal) + "\n", encoding="utf-8")
        event_path.write_text(json.dumps(event_msg) + "\n", encoding="utf-8")
        duplicate_event_msg = {
            "type": "event_msg",
            "payload": {
                "type": "user_message",
                "message": "Document this behavior",
                "images": [],
                "local_images": [],
            },
        }
        dup_path.write_text(
            json.dumps(normal) + "\n" + json.dumps(duplicate_event_msg) + "\n",
            encoding="utf-8",
        )
        bootstrap_path.write_text(
            json.dumps(bootstrap) + "\n" + json.dumps(normal) + "\n",
            encoding="utf-8",
        )
        subagent_path.write_text(
            json.dumps(subagent_meta) + "\n" + json.dumps(normal) + "\n",
            encoding="utf-8",
        )
        normal_result = subprocess.run(
            [sys.executable, str(scanner), str(triggers), str(normal_path)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        subagent_result = subprocess.run(
            [sys.executable, str(scanner), str(triggers), str(subagent_path)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        event_result = subprocess.run(
            [sys.executable, str(scanner), str(triggers), str(event_path)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        dup_result = subprocess.run(
            [sys.executable, str(scanner), str(triggers), str(dup_path)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        bootstrap_result = subprocess.run(
            [sys.executable, str(scanner), str(triggers), str(bootstrap_path)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    errors: list[str] = []
    if normal_result.returncode != 0 or "Document this" not in normal_result.stdout:
        errors.append("transcript scanner failed to detect a normal human trigger")
    if event_result.returncode != 0 or "Document this event" not in event_result.stdout:
        errors.append("transcript scanner failed to detect a Codex event_msg user trigger")
    if dup_result.returncode != 0 or dup_result.stdout.count(">>> Document this") != 1:
        errors.append("transcript scanner did not deduplicate repeated Codex user messages")
    if bootstrap_result.returncode != 0 or bootstrap_result.stdout.count(">>> Document this") != 1:
        errors.append("transcript scanner did not skip injected AGENTS bootstrap text")
    if subagent_result.returncode != 0 or subagent_result.stdout.strip():
        errors.append("transcript scanner did not skip a Codex subagent transcript")
    return errors


def check_lint_helper() -> list[str]:
    helper = ROOT / ".codex" / "skills" / "docs-librarian" / "scripts" / "add_lint.py"
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "pyproject.toml").write_text(
            "[tool.ruff]\nline-length = 100\n", encoding="utf-8"
        )
        cfg = base / "src" / "package" / "ruff.toml"
        result = subprocess.run(
            [
                sys.executable,
                str(helper),
                "argparse.ArgumentParser",
                "Use C:\\tmp and quote \"paths\" literally.",
                str(cfg),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            return [f"add_lint failed: {result.stderr.strip() or result.stdout.strip()}"]
        text = cfg.read_text(encoding="utf-8")
    errors: list[str] = []
    if 'extend = "../../pyproject.toml"' not in text:
        errors.append("add_lint did not extend the nearest parent Ruff config")
    if '"argparse.ArgumentParser".msg' not in text:
        errors.append("add_lint did not write the banned API entry")
    data = tomllib.loads(text)
    msg = data["lint"]["flake8-tidy-imports"]["banned-api"]["argparse.ArgumentParser"]["msg"]
    if msg != 'Use C:\\tmp and quote "paths" literally.':
        errors.append("add_lint did not preserve TOML string escapes")
    return errors


def check_install_ignores_generated_files() -> list[str]:
    installer = ROOT / "scripts" / "install.py"
    cache_dir = ROOT / ".codex" / "skills" / "planboard" / "__pycache__"
    cache_file = cache_dir / "generated.pyc"
    cache_dir.mkdir(exist_ok=True)
    cache_file.write_bytes(b"generated")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "repo"
            target.mkdir()
            result = subprocess.run(
                [sys.executable, str(installer), "--target", str(target)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if result.returncode != 0:
                return [f"install failed: {result.stderr.strip() or result.stdout.strip()}"]
            missing = sorted(
                name
                for name in EXPECTED_SKILLS
                if not (target / ".codex" / "skills" / name / "SKILL.md").exists()
            )
            if missing:
                return [f"install did not copy expected skills: {', '.join(missing)}"]
            missing_agents = sorted(
                name
                for name in EXPECTED_AGENTS
                if not (target / ".codex" / "agents" / name).exists()
            )
            if missing_agents:
                return [f"install did not copy expected agents: {', '.join(missing_agents)}"]
            copied = target / ".codex" / "skills" / "planboard" / "__pycache__" / "generated.pyc"
            if copied.exists():
                return ["install copied generated __pycache__ files into the target repo"]
    finally:
        cache_file.unlink(missing_ok=True)
        try:
            cache_dir.rmdir()
        except OSError:
            pass
    return []


def check_install_refuses_self_target() -> list[str]:
    installer = ROOT / "scripts" / "install.py"
    result = subprocess.run(
        [sys.executable, str(installer), "--target", str(ROOT), "--force"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode == 0:
        return ["install allowed --force over the source bundle"]
    if "refusing to install this bundle into itself" not in result.stderr:
        return ["install self-target refusal produced an unexpected diagnostic"]
    return []


def main() -> int:
    errors = (
        check_forbidden()
        + check_skill_bundle()
        + check_agent_bundle()
        + check_vendored_attribution()
        + check_sample_plan()
        + check_renderer()
        + check_transcript_scanner()
        + check_lint_helper()
        + check_install_ignores_generated_files()
        + check_install_refuses_self_target()
    )
    if errors:
        print("validation failed:")
        for err in errors:
            print(f"- {err}")
        return 1
    print("public skill bundle validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
