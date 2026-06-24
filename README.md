# Codex VDD Skills

Small, installable Codex skills for a Verifier-Driven Development workflow.

**VDD is the operating idea:** before a non-trivial change grows large, turn the
human intent into a contract, a mock set, and verifier feedback. Tests are one
kind of verifier, but not the only one. A useful loop can also include HTML
previews, CLI smokes, training-format dry-runs, sub-agent review passes, and
human feedback that gets folded back into future checks.

This repo packages that loop into three practical skills:

| Skill | Purpose |
| --- | --- |
| **Verifier-Driven Development** | Make contract-first, verifier-first implementation the default loop. |
| **Planboard** | Fan out research and synthesis agents, then render a browser-reviewable implementation plan. |
| **Wrap** | End a session by curating documentation updates and applying only the accepted ones. |

The bundle is intentionally small: Codex skill folders, custom agent role files,
one sample plan, and thin helper scripts.

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

The skills here reflect that shape. Planboard makes intent reviewable before
implementation. Wrap prevents useful session knowledge from evaporating. VDD
ties the two together as the default development loop.

## What Is Included

```text
.codex/
  agents/
    planboard-researcher.toml
    planboard-synthesizer.toml
    planboard-verifier.toml
    wrap-curator.toml
    wrap-librarian.toml
  skills/
    verifier-driven-development/
    planboard/
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
- `.codex/skills/wrap`
- `.codex/skills/docs-curator`
- `.codex/skills/docs-librarian`
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
planboard, and wrap skills.
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
2. Define how verifier failures should be handled: accept, repair, regenerate,
   filter/drop, or keep with a warning.
3. Reuse existing tests/verifiers and add a decisive mock set where needed.
4. Implement in narrow verifier loops.
5. Use sub-agent verifier passes for independent semantic checks.
6. For model-generated artifacts, report both quality gains and yield loss from
   filters or drops.
7. Feed human review and preview findings back into mocks or verifiers.

## Use Planboard

Ask Codex for planboard before a non-trivial change:

```text
Use planboard for this migration. I need a browser-reviewable plan first.
```

Expected flow:

1. The main agent reads the skill and the plan schema.
2. It fans out research, synthesis, and verification subagents.
3. It renders an HTML review page from JSON.
4. You annotate each step as `采纳` / `改` / `砍`, copy annotations, and paste them back.
5. The agent revises the plan or starts implementation after acceptance.

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
During implementation     verifier-driven-development -> contract + mocks + verifiers
After the session         wrap -> accepted doc updates, retired stale notes, promoted guardrails
```

For a new repository, install the bundle, run the recommended Librarian baseline
once, then use the three skills as a lightweight workflow rather than a heavy
process.

## Privacy And Sanitization

This public version removes project-specific paths, private repo names, datasets, credentials, and internal host details. The skills still inspect local transcripts and docs when used inside a target repository; review the skill text before installing if your environment has stricter data-handling rules.

Run the bundled public-safety check:

```bash
python3 scripts/validate_public.py
```

## Requirements

- Python 3.10+ for helper scripts.
- Codex with skill support.
- Codex subagent support for the full `planboard` and `wrap` workflows.

## License

MIT.
