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
    if data.get("steps"):
        errors.append("examples/sample-plan.json: public sample must use requirements[], not legacy steps[]")
    if data.get("task_class") not in {"code", "data"}:
        errors.append("examples/sample-plan.json: task_class must be code or data")

    requirements = data.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        return errors + ["examples/sample-plan.json: missing non-empty requirements"]
    if len(requirements) > 8:
        errors.append("examples/sample-plan.json: more than 8 requirements")

    req_ids = [req.get("id") for req in requirements if isinstance(req, dict)]
    if len(req_ids) != len(requirements) or any(not item for item in req_ids):
        errors.append("examples/sample-plan.json: every requirement needs an id")
    if len(set(req_ids)) != len(req_ids):
        errors.append("examples/sample-plan.json: requirement ids must be unique")

    required_gate_fields = (
        "criterion",
        "failure_class",
        "source_of_truth",
        "input_form",
        "signal",
        "failure_response",
        "verifier_form",
        "lifecycle",
    )
    for idx, req in enumerate(requirements, start=1):
        if not isinstance(req, dict):
            errors.append(f"examples/sample-plan.json requirement {idx}: must be an object")
            continue
        for key in ("requirement", "scope_id"):
            if not req.get(key):
                errors.append(f"examples/sample-plan.json requirement {idx}: missing {key}")
        if any(key in req for key in ("files", "commands", "depends_on")):
            errors.append(f"examples/sample-plan.json requirement {idx}: contains L2 implementation fields")
        gate = req.get("gate")
        if not isinstance(gate, dict):
            errors.append(f"examples/sample-plan.json requirement {idx}: missing gate object")
            gate = {}
        for key in required_gate_fields:
            if not gate.get(key):
                errors.append(f"examples/sample-plan.json requirement {idx}: gate missing {key}")
        if gate.get("verifier_form") not in {
            "code",
            "script",
            "data-check",
            "preview",
            "subagent",
            "human",
        }:
            errors.append(f"examples/sample-plan.json requirement {idx}: invalid verifier_form")
        if gate.get("lifecycle") not in {"one-shot", "reusable", "wrap-decides"}:
            errors.append(f"examples/sample-plan.json requirement {idx}: invalid lifecycle")
        strength = req.get("gate_strength")
        if not isinstance(strength, dict):
            errors.append(f"examples/sample-plan.json requirement {idx}: missing gate_strength")
            strength = {}
        mutants = strength.get("mutants")
        if not isinstance(mutants, list) or not mutants:
            errors.append(f"examples/sample-plan.json requirement {idx}: strong gate needs mutants")
            mutants = []
        if strength.get("verdict") != "strong":
            errors.append(f"examples/sample-plan.json requirement {idx}: sample gate must be strong")
        if any(not isinstance(mutant, dict) or mutant.get("caught_by_gate") is not True for mutant in mutants):
            errors.append(f"examples/sample-plan.json requirement {idx}: every sample mutant must be caught")
        if req.get("coverage") != "covered":
            errors.append(f"examples/sample-plan.json requirement {idx}: coverage must be covered")

    scopes = data.get("scopes")
    if not isinstance(scopes, list) or not scopes:
        errors.append("examples/sample-plan.json: missing non-empty scopes")
        scopes = []
    if len(scopes) > 4:
        errors.append("examples/sample-plan.json: more than 4 scopes")
    scope_ids = [scope.get("id") for scope in scopes if isinstance(scope, dict)]
    if len(scope_ids) != len(scopes) or any(not item for item in scope_ids):
        errors.append("examples/sample-plan.json: every scope needs an id")
    if len(set(scope_ids)) != len(scope_ids):
        errors.append("examples/sample-plan.json: scope ids must be unique")
    known_req_ids = set(req_ids)
    declared_members = []
    member_scope = {}
    for scope in scopes:
        if not isinstance(scope, dict):
            continue
        if not scope.get("name") or not scope.get("outcome"):
            errors.append(f"examples/sample-plan.json: {scope.get('id')} needs name and outcome")
        if scope.get("appetite") not in {"S", "M", "L"}:
            errors.append(f"examples/sample-plan.json: {scope.get('id')} has invalid appetite")
        members = scope.get("requirement_ids") or []
        declared_members.extend(members)
        for req_id in members:
            if req_id in member_scope:
                errors.append(f"examples/sample-plan.json: {req_id} belongs to more than one scope")
            member_scope[req_id] = scope.get("id")
        unknown = sorted(set(members) - known_req_ids)
        if unknown:
            errors.append(
                "examples/sample-plan.json: scope references unknown requirements: "
                + ", ".join(unknown)
            )
    if sorted(declared_members) != sorted(req_ids):
        errors.append("examples/sample-plan.json: scope membership must cover each requirement exactly once")
    for req in requirements:
        if not isinstance(req, dict):
            continue
        if req.get("scope_id") not in set(scope_ids):
            errors.append(f"examples/sample-plan.json: {req.get('id')} references an unknown scope")
        elif member_scope.get(req.get("id")) != req.get("scope_id"):
            errors.append(f"examples/sample-plan.json: {req.get('id')} scope_id disagrees with scope membership")

    decisions = data.get("decisions") or []
    decision_ids = [dec.get("id") for dec in decisions if isinstance(dec, dict)]
    if len(decision_ids) != len(decisions) or len(set(decision_ids)) != len(decision_ids):
        errors.append("examples/sample-plan.json: decision ids must be present and unique")
    known_unit_ids = known_req_ids | set(scope_ids) | set(decision_ids)
    for dec in decisions:
        if not isinstance(dec, dict):
            continue
        labels = [opt.get("label") for opt in dec.get("options", []) if isinstance(opt, dict)]
        if not labels or dec.get("recommendation") not in labels:
            errors.append(f"examples/sample-plan.json: {dec.get('id')} needs a valid recommendation")
        unknown = sorted(set(dec.get("affects") or []) - known_unit_ids)
        if unknown:
            errors.append(
                f"examples/sample-plan.json: {dec.get('id')} affects unknown units: "
                + ", ".join(unknown)
            )

    if data.get("uncovered_failure_modes"):
        errors.append("examples/sample-plan.json: sample must have no uncovered failure modes")
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


def check_planboard_bundle_contract() -> list[str]:
    errors: list[str] = []
    planboard = (
        ROOT / ".codex" / "skills" / "planboard" / "SKILL.md"
    ).read_text(encoding="utf-8", errors="replace")
    schema = (
        ROOT / ".codex" / "skills" / "planboard" / "references" / "plan-schema.md"
    ).read_text(encoding="utf-8", errors="replace")
    renderer = (
        ROOT / ".codex" / "skills" / "planboard" / "render_planboard.py"
    ).read_text(encoding="utf-8", errors="replace")
    vdd = (
        ROOT / ".codex" / "skills" / "verifier-driven-development" / "SKILL.md"
    ).read_text(encoding="utf-8", errors="replace")
    readme = (ROOT / "README.md").read_text(encoding="utf-8", errors="replace")

    for token in (
        "requirements",
        "gate_strength",
        "mutation",
        "fresh",
        "shuorenhua",
        "failure_response",
    ):
        if token not in planboard:
            errors.append(f"planboard SKILL.md: missing L1 contract token {token!r}")
    if "must invoke and follow" not in planboard or "residual style" not in planboard:
        errors.append("planboard SKILL.md: shuorenhua is not an explicit two-reread final pass")
    if "effective_gate_verdict" not in renderer:
        errors.append("planboard renderer: missing earned-strength recomputation")
    for field in (
        "failure_class",
        "source_of_truth",
        "input_form",
        "signal",
        "failure_response",
        "verifier_form",
        "lifecycle",
    ):
        if field not in schema or field not in renderer:
            errors.append(f"planboard gate contract: {field!r} is not shared by schema and renderer")
    if "requirements[]" not in schema or "no mutants render as `open`" not in schema:
        errors.append("planboard schema: missing requirements or earned-strength contract")
    if "L1 acceptance spec" not in readme or "mutation" not in readme:
        errors.append("README.md: Planboard still lacks the L1 gate/mutation workflow")

    combined = "\n".join((planboard, schema, vdd, readme))
    for stale in (
        "wrap implements",
        "L2 sequencing belongs to wrap",
        "VDD/wrap",
        "Fan out research and synthesis agents",
    ):
        if stale in combined:
            errors.append(f"Planboard/VDD lifecycle still contains stale wording: {stale!r}")
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
        legacy_plan = Path(tmp) / "legacy-plan.json"
        legacy_out = Path(tmp) / "legacy-plan.html"
        revision_plan = Path(tmp) / "revision-plan.json"
        revision_out = Path(tmp) / "revision-plan.html"
        bad_strength_plan = Path(tmp) / "bad-strength-plan.json"
        bad_strength_out = Path(tmp) / "bad-strength-plan.html"
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
        valid_gate = {
            "criterion": "The observable result exact-matches the fixture.",
            "failure_class": "The result drifts while the page still looks valid.",
            "source_of_truth": "A frozen fixture.",
            "input_form": "One valid and one invalid fixture.",
            "signal": "Exact match for the valid fixture and a failure for the invalid fixture.",
            "failure_response": "Block the change and repair the mismatch before retrying.",
            "verifier_form": "code",
            "lifecycle": "reusable",
            "reuse": None,
        }
        valid_strength = {
            "mutants": [
                {
                    "mutant": "Return the wrong value with the right shape.",
                    "caught_by_gate": True,
                    "hardening": "Compare values as well as structure.",
                }
            ],
            "verdict": "strong",
            "smells": [],
        }
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
        legacy_plan.write_text(
            json.dumps(
                {
                    "task": "Legacy execution context",
                    "round": 2,
                    "changes_from_previous_round": [
                        {
                            "step_id": "step-2-verifier",
                            "status": "改",
                            "change": "Clarified which verifier proves the legacy contract.",
                        }
                    ],
                    "steps": [
                        {
                            "id": "step-1-contract",
                            "title": "Pin the contract",
                            "what": "Record the contract.",
                            "files": ["docs/export-adapter.md"],
                            "verification": "The contract is reviewable.",
                        },
                        {
                            "id": "step-2-verifier",
                            "title": "Build the verifier",
                            "what": "Add the check.",
                            "commands": ["pytest -q tests/test_export_adapter_verifier.py"],
                            "verification": "The malformed fixture fails.",
                        },
                        {
                            "id": "step-3-adapter",
                            "title": "Implement the adapter",
                            "what": "Add the opt-in path.",
                            "depends_on": ["step-1-contract", "step-2-verifier"],
                            "verification": "The smoke passes.",
                        },
                    ],
                    "alternatives_considered": [
                        {
                            "approach": "Replace the exporter in one step",
                            "why_not": "It widens the change before verifier coverage exists.",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        legacy_result = subprocess.run(
            [
                sys.executable,
                str(ROOT / ".codex" / "skills" / "planboard" / "render_planboard.py"),
                str(legacy_plan),
                str(legacy_out),
                "--slug",
                "legacy-context",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if legacy_result.returncode != 0:
            return [
                "renderer failed on legacy execution-context fixture: "
                f"{legacy_result.stderr.strip() or legacy_result.stdout.strip()}"
            ]
        legacy_text = legacy_out.read_text(encoding="utf-8", errors="replace")
        revision_plan.write_text(
            json.dumps(
                {
                    "task": "Revision visibility",
                    "round": 2,
                    "task_class": "code",
                    "headline": "Show changed requirements first.",
                    "intent": "Keep revision review focused on units that changed.",
                    "changes_from_previous_round": [
                        {
                            "unit_id": "req-1",
                            "status": "改",
                            "change": "Clarified the acceptance signal.",
                        },
                        {
                            "unit_id": "req-removed",
                            "status": "砍",
                            "change": "Removed a requirement that no longer serves the intent.",
                        },
                    ],
                    "requirements": [
                        {
                            "id": "req-1",
                            "scope_id": "scope-1",
                            "requirement": "Changed requirement",
                            "gate": valid_gate,
                            "gate_strength": valid_strength,
                            "coverage": "covered",
                        },
                        {
                            "id": "req-2",
                            "scope_id": "scope-1",
                            "requirement": "Unchanged requirement",
                            "gate": valid_gate,
                            "gate_strength": valid_strength,
                            "coverage": "covered",
                        },
                    ],
                    "scopes": [
                        {
                            "id": "scope-1",
                            "name": "Revision scope",
                            "outcome": "Both requirements remain reviewable.",
                            "appetite": "S",
                            "requirement_ids": ["req-1", "req-2"],
                        }
                    ],
                    "decisions": [],
                    "non_goals": [],
                    "uncovered_failure_modes": [],
                    "open_questions": [],
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
        bad_strength_plan.write_text(
            json.dumps(
                {
                    "task": "Reject claimed strength",
                    "round": 1,
                    "task_class": "code",
                    "headline": "Claimed strength must be recomputed.",
                    "intent": "The coverage header must expose every unearned strong gate.",
                    "requirements": [
                        {
                            "id": "req-missing-gate",
                            "requirement": "A missing gate cannot be strong.",
                            "gate_strength": {**valid_strength, "verdict": "weak"},
                            "coverage": "covered",
                        },
                        {
                            "id": "req-empty-mutants",
                            "requirement": "An unattacked gate cannot be strong.",
                            "gate": valid_gate,
                            "gate_strength": {"mutants": [], "verdict": "weak", "smells": []},
                            "coverage": "covered",
                        },
                        {
                            "id": "req-missing-failure-response",
                            "requirement": "An incomplete gate cannot be strong.",
                            "gate": {
                                key: value
                                for key, value in valid_gate.items()
                                if key != "failure_response"
                            },
                            "gate_strength": valid_strength,
                            "coverage": "covered",
                        },
                        {
                            "id": "req-surviving-mutant",
                            "requirement": "A surviving mutant makes the gate weak.",
                            "gate": valid_gate,
                            "gate_strength": {
                                "mutants": [
                                    {
                                        "mutant": "Return the wrong value.",
                                        "caught_by_gate": False,
                                        "hardening": "Add an exact-value fixture.",
                                    }
                                ],
                                "verdict": "strong",
                                "smells": [],
                            },
                            "coverage": "covered",
                        },
                        {
                            "id": "req-coverage-gap",
                            "requirement": "A coverage gap makes the gate weak.",
                            "gate": valid_gate,
                            "gate_strength": valid_strength,
                            "coverage": "gap",
                        },
                        {
                            "id": "req-invalid-enum",
                            "requirement": "An unknown verifier form cannot be strong.",
                            "gate": {**valid_gate, "verifier_form": "guess"},
                            "gate_strength": valid_strength,
                            "coverage": "covered",
                        },
                        {
                            "id": "req-missing-coverage",
                            "requirement": "Missing P5 coverage cannot look strong.",
                            "gate": valid_gate,
                            "gate_strength": valid_strength,
                        },
                        {
                            "id": "req-invalid-coverage",
                            "requirement": "Unknown P5 coverage cannot look strong.",
                            "gate": valid_gate,
                            "gate_strength": valid_strength,
                            "coverage": "unknown",
                        },
                    ],
                    "scopes": [],
                    "decisions": [],
                    "non_goals": [],
                    "uncovered_failure_modes": ["A named failure mode has no gate."],
                    "open_questions": [],
                }
            ),
            encoding="utf-8",
        )
        bad_strength_result = subprocess.run(
            [
                sys.executable,
                str(ROOT / ".codex" / "skills" / "planboard" / "render_planboard.py"),
                str(bad_strength_plan),
                str(bad_strength_out),
                "--slug",
                "bad-strength",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if bad_strength_result.returncode != 0:
            return [
                "renderer failed on unearned-strength fixture: "
                f"{bad_strength_result.stderr.strip() or bad_strength_result.stdout.strip()}"
            ]
        bad_strength_text = bad_strength_out.read_text(encoding="utf-8", errors="replace")

        missing_p5_plan = Path(tmp) / "missing-p5-plan.json"
        missing_p5_out = Path(tmp) / "missing-p5-plan.html"
        missing_p5_plan.write_text(
            json.dumps(
                {
                    "task": "Require an explicit P5 result",
                    "round": 1,
                    "task_class": "code",
                    "requirements": [
                        {
                            "id": "req-1",
                            "requirement": "A complete gate still needs whole-spec coverage.",
                            "gate": valid_gate,
                            "gate_strength": valid_strength,
                            "coverage": "covered",
                        }
                    ],
                    "scopes": [],
                    "decisions": [],
                }
            ),
            encoding="utf-8",
        )
        missing_p5_result = subprocess.run(
            [
                sys.executable,
                str(ROOT / ".codex" / "skills" / "planboard" / "render_planboard.py"),
                str(missing_p5_plan),
                str(missing_p5_out),
                "--slug",
                "missing-p5",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if missing_p5_result.returncode != 0:
            return [
                "renderer failed on missing-P5 fixture: "
                f"{missing_p5_result.stderr.strip() or missing_p5_result.stdout.strip()}"
            ]
        missing_p5_text = missing_p5_out.read_text(encoding="utf-8", errors="replace")
        if (
            'class="coverage cov-warn"' not in missing_p5_text
            or "缺少 P5 覆盖检查结果" not in missing_p5_text
        ):
            return ["renderer treated a missing whole-spec P5 result as clean"]

        def valid_requirement(uid: str) -> dict:
            return {
                "id": uid,
                "requirement": "The unit remains independently reviewable.",
                "gate": valid_gate,
                "gate_strength": valid_strength,
                "coverage": "covered",
            }

        id_error_cases = {
            "duplicate": {
                "requirements": [valid_requirement("req-1")],
                "decisions": [{"id": "req-1", "decision": "Duplicate raw id"}],
                "scopes": [],
            },
            "anchor-collision": {
                "requirements": [
                    valid_requirement("req-a/b"),
                    valid_requirement("req-a-b"),
                ],
                "decisions": [],
                "scopes": [],
            },
            "wrong-prefix": {
                "requirements": [valid_requirement("unit-1")],
                "decisions": [],
                "scopes": [],
            },
            "legacy-anchor-collision": {
                "requirements": [],
                "steps": [
                    {"id": "step/a", "title": "One", "what": "x", "verification": "v"},
                    {"id": "step-a", "title": "Two", "what": "y", "verification": "v"},
                ],
            },
        }
        for case_name, case_plan in id_error_cases.items():
            case_path = Path(tmp) / f"id-{case_name}.json"
            case_out = Path(tmp) / f"id-{case_name}.html"
            case_path.write_text(json.dumps(case_plan), encoding="utf-8")
            case_result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / ".codex" / "skills" / "planboard" / "render_planboard.py"),
                    str(case_path),
                    str(case_out),
                    "--slug",
                    case_name,
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if case_result.returncode == 0 or "invalid unit ids" not in case_result.stderr:
                return [f"renderer accepted annotation-corrupting unit ids: {case_name}"]
    if (
        "req-1-source-contract" not in text
        or "dec-1-future-default" not in text
        or "复制批注" not in text
        or 'class="coverage cov-ok"' not in text
        or "<b>3</b> 强 gate" not in text
        or 'name="dec-1-future-default"' not in text
        or 'value="A" checked' not in text
    ):
        return ["renderer output is missing the L1 sample, strong coverage, or decision control"]
    if 'var KEY = "planboard_bad-slug_r1";' not in text:
        return ["renderer did not sanitize the slug before embedding it in JavaScript"]
    if 'var TASK = "x \\u003c/script>\\u003cscript>globalThis.pwned=1\\u003c/script>";' not in injected_text:
        return ["renderer did not protect JSON strings embedded in a script tag"]
    if 'data-id="step-1"' not in injected_text:
        return ["renderer lost the thin legacy steps[] compatibility path"]
    if (
        "docs/export-adapter.md" not in legacy_text
        or "pytest -q tests/test_export_adapter_verifier.py" not in legacy_text
        or "step-1-contract" not in legacy_text
        or "step-2-verifier" not in legacy_text
        or "Replace the exporter in one step" not in legacy_text
        or "Clarified which verifier proves the legacy contract." not in legacy_text
        or '<div class="unit req changed-unit" id="pb-step-2-verifier"' not in legacy_text
        or '<div class="unitchange">' not in legacy_text
    ):
        return [
            "renderer dropped files, commands, dependencies, alternatives, or revision context "
            "from a legacy plan"
        ]
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
        or "Clarified the acceptance signal." not in revision_text
        or 'href="#pb-req-1"' not in revision_text
        or '<div class="unit req changed-unit" id="pb-req-1"' not in revision_text
        or '<div class="unitchange">' not in revision_text
        or "req-removed" not in revision_text
        or 'href="#pb-req-removed"' in revision_text
    ):
        return ["renderer did not expose revision changes as linked highlighted units"]
    if (
        'class="coverage cov-warn"' not in bad_strength_text
        or "<b>0</b> 强 gate" not in bad_strength_text
        or "<b>8</b> 弱/待补" not in bad_strength_text
        or bad_strength_text.count('<span class="vbadge badge-open">') < 6
        or bad_strength_text.count('<span class="vbadge badge-weak">') < 2
        or "A named failure mode has no gate." not in bad_strength_text
    ):
        return ["renderer trusted an unearned strong gate or hid a coverage defect"]
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
        + check_planboard_bundle_contract()
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
