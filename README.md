# Codex VDD Skills

Small, installable Codex skills for a Verifier-Driven Development workflow.

**VDD is the operating idea:** before a non-trivial change grows large, turn the
human intent into a contract, a mock set, and verifier feedback. Tests are one
kind of verifier, but not the only one. A useful loop can also include HTML
previews, CLI smokes, training-format dry-runs, sub-agent review passes, and
human feedback that gets folded back into future checks.

This repo packages that loop into four user-facing skills, two support skills,
and reusable reviewer agent roles:

| Skill | Purpose |
| --- | --- |
| **Verifier-Driven Development** | Make contract-first, verifier-first implementation the default loop. |
| **Planboard** | Fan out research and synthesis agents, then render a browser-reviewable implementation plan. |
| **Shuorenhua** | Clean plan, status, and documentation prose so review text stays direct and approval-ready. |
| **Wrap** | End a session by curating documentation updates and applying only the accepted ones. |

| Agent role | Purpose |
| --- | --- |
| **vdd-spec-reviewer** | Review an intent contract, spec, or requirements draft before planning. |
| **vdd-plan-reviewer** | Review an implementation plan for contract coverage, executability, and verifier quality. |

The bundle stays installable: Codex skill folders, custom agent role files, one
sample plan, and thin helper scripts.

`shuorenhua` is vendored from
[MrGeDiao/shuorenhua](https://github.com/MrGeDiao/shuorenhua) under the MIT
license. This bundle includes the runtime skill files used by Codex; upstream
project docs, assets, and automation files are not included.

The VDD skill and reviewer agent roles include workflow ideas adapted from
[obra/superpowers](https://github.com/obra/superpowers) v5.1.3 under the MIT
license (Copyright (c) 2025 Jesse Vincent). The imported material is folded
into VDD as defensive delivery gates and reviewer contracts, not shipped as a
separate planning or implementation system.

## Philosophy

VDD is close to TDD, but wider:

- **TDD is test-first. VDD is verifier-first.**
- Tests are verifier surfaces; so are schemas, mocks, previews, trainer dry-runs,
  sub-agent reviews, and human inspection.
- The first deliverable is the contract: accepted inputs, rejected inputs,
  model-visible outputs, side effects, masks, coordinates, defaults, and review
  surfaces.
- Each manual correction should raise one question: can a verifier catch this
  class of mistake next time?

The skills here reflect that shape. VDD ties the loop together as the default
development practice and now includes root-cause debugging, review triage,
completion-evidence, and external-workflow import gates. Planboard makes intent
reviewable before implementation. Shuorenhua keeps the review text direct enough
to approve or reject quickly. Wrap prevents useful session knowledge from
evaporating.

## What Is Included

```text
.codex/
  agents/
    vdd-spec-reviewer.toml
    vdd-plan-reviewer.toml
    planboard-researcher.toml
    planboard-synthesizer.toml
    planboard-verifier.toml
    wrap-curator.toml
    wrap-librarian.toml
  skills/
    verifier-driven-development/
    planboard/
    shuorenhua/
    wrap/
    docs-curator/
    docs-librarian/
examples/
  sample-plan.json
scripts/
  install.py
  validate_public.py
```

`wrap` depends on `docs-curator` and `docs-librarian`, so those supporting skills are included.

## Install Into A Repository

From this repository:

```bash
python3 scripts/install.py --target /path/to/your/repo
```

To replace existing copies:

```bash
python3 scripts/install.py --target /path/to/your/repo --force
```

The installer copies:

- `.codex/skills/verifier-driven-development`
- `.codex/skills/planboard`
- `.codex/skills/shuorenhua`
- `.codex/skills/wrap`
- `.codex/skills/docs-curator`
- `.codex/skills/docs-librarian`
- `.codex/agents/vdd-spec-reviewer.toml`
- `.codex/agents/vdd-plan-reviewer.toml`
- `.codex/agents/planboard-*.toml`
- `.codex/agents/wrap-*.toml`

It does not modify application code.

## Recommended First Run

For the closest experience to the source workflow, do one baseline documentation
pass after installing. This gives `wrap` a stable place to file future session
learnings instead of scattering notes across whatever docs happen to exist.

From the target repository, ask Codex:

```text
Use the wrap-librarian subagent with this accepted setup item:

Normalize this repository's documentation baseline for future wrap runs.
Create or update docs/README.md as a concise documentation index, create
.codex/hooks/doc-map.json if it is missing, and add a short pointer from the
primary agent instruction file to the installed verifier-driven-development,
planboard, shuorenhua, and wrap skills, plus the vdd-spec-reviewer and
vdd-plan-reviewer agent roles.
Preserve existing content; relocate or link it instead of deleting it.
```

Review the diff before committing. This is a one-time setup step; normal session
wraps should still use the Curator -> human acceptance -> Librarian flow below.

## Use Verifier-Driven Development

Use VDD for non-trivial implementation, rewrite, refactor, data-pipeline,
exporter, adapter, prompt, UI preview, and training-format work:

```text
Use verifier-driven-development for this change. Start by extracting the
input/output contract, then build the smallest mock and verifier loop before
editing the implementation.
```

Expected loop:

1. State the intent contract in operational terms.
2. Name the acceptance gates in report order, especially the gate that would
   catch the operator's current concern.
3. Add or select a verifier that fails on the current behavior for that concern
   before editing the implementation.
4. Define how verifier failures should be handled: accept, repair, regenerate,
   filter/drop, or keep with a warning.
5. Reuse existing tests/verifiers and add a decisive mock set where needed.
6. Implement in narrow verifier loops.
7. Investigate failures from root cause: inspect the failing artifact, compare
   a known-good path, and trace the first bad boundary before editing again.
8. Classify review findings as `worth-fixing`, `wrong-analysis`, or
   `not-worth-fixing` before editing.
9. Use `vdd-spec-reviewer` or `vdd-plan-reviewer` for independent contract and
   plan checks when the repository has those roles installed.
10. Before claiming done, run a fresh relevant check, read its output, and
   report the exact command/result or the smallest missing verification.
11. For model-generated artifacts, report both quality gains and yield loss from
   filters or drops.
12. Feed human review and preview findings back into mocks or verifiers.

## Use Planboard

Ask Codex for planboard before a non-trivial change:

```text
Use planboard for this migration. I need a browser-reviewable plan first.
```

Expected flow:

1. The main agent reads the skill and the plan schema.
2. It fans out research, synthesis, and verification subagents.
3. It cleans the operator-visible plan text with `shuorenhua`.
4. It renders an HTML review page from JSON.
5. You annotate each step as `采纳` / `改` / `砍`, copy annotations, and paste them back.
6. For revision rounds, the new page shows a "本轮改动" block near the top with
   only the steps that need another read. Each item links to the changed step,
   and the step card is highlighted with the same note.
7. The agent revises the plan or starts implementation after acceptance.

Render the included sample:

```bash
mkdir -p /tmp/planboard-previews
python3 .codex/skills/planboard/render_planboard.py \
  examples/sample-plan.json \
  /tmp/planboard-previews/sample-plan.html \
  --slug sample-plan
python3 -m http.server 8000 --directory /tmp/planboard-previews
```

Open `http://localhost:8000/sample-plan.html`.

## Use Wrap

At the end of a work session:

```text
Use wrap.
```

Expected flow:

1. `wrap-curator` proposes a short ADD / RETIRE / PROMOTE list.
2. The main agent shows that list verbatim.
3. You accept selected items.
4. `wrap-librarian` applies only accepted items.

This keeps session learnings from drifting into stale or scattered documentation.

## How The Skills Fit Together

```text
Before a large change     planboard -> browser-reviewed implementation plan
Before human review       shuorenhua -> direct, approval-ready plan/status/docs prose
During implementation     verifier-driven-development -> contract + mocks + verifiers
Before claiming done      verifier-driven-development -> root cause, review triage, fresh evidence
After the session         wrap -> accepted doc updates, retired stale notes, promoted guardrails
```

For a new repository, install the bundle, run the recommended Librarian baseline
once, then use the skills as an installable workflow rather than a heavy process
tree.

## Privacy And Sanitization

This public version removes project-specific paths, private repo names, datasets, credentials, and internal host details. The skills still inspect local transcripts and docs when used inside a target repository; review the skill text before installing if your environment has stricter data-handling rules.

Run the bundled public-safety check:

```bash
python3 scripts/validate_public.py
```

## Requirements

- Python 3.11+ for `scripts/validate_public.py`, so agent TOML files are parsed
  during validation.
- Python 3.10+ is sufficient for `scripts/install.py`.
- Codex with skill support.
- Codex subagent support for the full `planboard` and `wrap` workflows.

## License

MIT.
