---
name: planboard
description: Browser-reviewable implementation planning for non-trivial changes. Use when the operator asks for planboard, a plan they can annotate in the browser, or a step-by-step plan before code. The current Orchestrator must spawn Codex sub-agents for research, synthesis, and verification, then render the final JSON plan to an annotatable HTML page. Do not use for trivial one-file edits or quick questions.
---

# planboard

Planboard produces an implementation plan that the operator reviews in a browser
before code is written. It is a current-session Orchestrator workflow: do not
open a nested `codex exec` to plan.

## Assets

- `render_planboard.py` — stdlib renderer: plan JSON to annotatable HTML.
- `references/plan-schema.md` — JSON contract. Read it before writing the final
  plan JSON.
- `.codex/agents/planboard-{researcher,synthesizer,verifier}.toml` — project
  subagent roles. Prefer these names when the current Codex surface exposes
  custom agents; otherwise spawn generic Codex subagents with equivalent prompts.

## Orchestrator Contract

The main Orchestrator runs the planning loop and keeps raw research out of the
operator-facing answer. Subagents are mandatory for non-trivial planboard runs;
if the current Codex surface cannot spawn subagents, report that blocker instead
of silently performing the workflow in the parent context.

1. Read the repository's primary agent instruction file if present (`CLAUDE.md`,
   `AGENTS.md`, `.codex/README.md`, or equivalent), this skill, and
   `references/plan-schema.md`.
2. Spawn parallel sub-agents for the five research angles. Use the available
   Codex subagent tool directly from the current session, pass narrow prompts,
   and avoid forking broad parent context unless the task requires it:
   - `grounding`: existing code patterns, module boundaries, concrete files/functions.
   - `integration`: callers, configs, schemas, CLIs, data contracts.
   - `risks`: failure modes, compatibility, migration concerns.
   - `tests`: existing coverage, missing tests, validation commands.
   - `priorart`: similar in-repo implementations and design alternatives.
3. Wait for the research agents. Do not paste raw findings to the operator.
4. Spawn three synthesis sub-agents using different lenses. Give each synthesis
   agent only the task, schema constraints, and distilled research findings it
   needs:
   - `minimal`: the smallest complete plan.
   - `robust`: pin behavior and validation before changing risky surfaces.
   - `impact`: highest-leverage work first.
5. Judge the candidates into one plan with at most six load-bearing steps.
   If there are A/B/C-style choices, choose the recommended default, state the
   reason, and record rejected options in `alternatives_considered` when they
   still matter.
6. Verify every step's claims against actual repo files, either directly in the
   Orchestrator or with a final verification subagent. Verifier findings should
   name the affected step id, cite the evidence command or file line, and give
   the smallest correction. Cut unsupported steps.
7. Run the operator-visible plan text through `shuorenhua` before rendering.
   Treat the plan as `status/docs` prose, use `minimal` or `standard` cleanup,
   and preserve protected spans: file paths, commands, code symbols, schema
   keys, step ids, A/B/C labels, verdict tags, and cited evidence. Clean only
   visible prose fields such as `headline`, `approach_summary`, step `title`,
   `summary`, `what`, `why`, `verification`, `risk`,
   `changes_from_previous_round`, `alternatives_considered`, `open_questions`,
   and `deferred`. The pass must remove template/AI-flavored phrasing without
   adding facts, weakening decisions, or changing the plan contract.
8. Write the final plan JSON to `/tmp/planboard/<slug>-r<N>.json`.
9. Render directly with the bundled renderer:

```bash
python3 .codex/skills/planboard/render_planboard.py \
  /tmp/planboard/<slug>-r<N>.json \
  "${PLANBOARD_PREVIEW_DIR:-/tmp/planboard-previews}"/planboard-<slug>-<YYYYMMDD>-r<N>.html \
  --slug <slug>
```

10. Reply with only the URL plus one short instruction: mark each step 采纳/改/砍,
   comment, click 复制批注, and paste the annotations back.

## Revision Loop

When the operator pastes annotations:

- If they say everything is accepted or "开干", stop planning and move to
  implementation if requested.
- If the blob contains questions without verdicts, answer those first.
- Otherwise rerun the Orchestrator workflow for round `N+1`, passing:
  - the original task,
  - the previous plan JSON,
  - the annotation blob verbatim.

Preserve accepted step ids. Apply 改 notes directly. Drop 砍 steps unless the
note asks for a replacement.

Every revision round must make the delta obvious in the HTML. Populate
`changes_from_previous_round` with one short item per changed, preserved, or
removed step that matters for review. The rendered page shows this block near
the top as "本轮改动（打开页面先看这里）", so the operator can see at a glance
what changed after their annotations without reopening the previous round.

When feedback changes a core assumption, rerun the planning loop instead of
patching prose in place. Re-ground the disputed point against files, examples,
or external training code when available, then render a new round with the
changed premise visible in `headline`, `approach_summary`,
`changes_from_previous_round`, and affected steps.

If the operator needs to choose between approaches, write the options directly
in the plan with inline labels such as `A（...）`, `B（...）`, `C（...）`; always
include the recommended default and a one-sentence reason. Do not hand back a
bare menu. If the operator can express the choice in the annotation box, the
HTML does not need bespoke controls for that decision.

## Output Locations

- JSON scratch: `/tmp/planboard/<slug>-r<N>.json`
- HTML preview: `${PLANBOARD_PREVIEW_DIR:-/tmp/planboard-previews}/planboard-<slug>-<YYYYMMDD>-r<N>.html`
- URL: depends on the preview server. A local default is
  `python3 -m http.server 8000 --directory "${PLANBOARD_PREVIEW_DIR:-/tmp/planboard-previews}"`.

Prefer a scratch or external preview directory over `$HOME` or the repository.
Do not restart or modify an existing preview server unless the operator asks.

## Final Plan Rules

- Match `references/plan-schema.md`.
- Six steps or fewer; push secondary items into `deferred`.
- Every step needs `id`, `title`, `summary`, `what`, and `verification`.
- Keep visible text scannable, but do not starve the operator of context. The
  `summary` should be one decision-bearing sentence; details belong in `what`,
  `why`, `commands`, `verification`, and `risk`.
- The visible layer for each step must be enough to choose 采纳/改/砍 without
  opening details. Avoid empty labels such as "update docs" or "implement
  changes"; say the contract change or implementation boundary.
- Apply `shuorenhua` to the final visible layer before writing JSON. Prefer
  direct, concrete wording over rhetorical setup, empty summaries, and
  contrastive phrasing that repeats known context.
- Stable step ids are load-bearing across rounds.
- Do not enter Codex plan mode; planboard is its own review surface.
- Match the operator's language in replies.

## Content Judgment Rules

- For rewrite/refactor requests, first determine whether the operator wants to
  replace the existing path or add a side path. When rewrite is confirmed,
  reuse proven pieces but plan deletion/demotion of stale formal surfaces after
  the new path is verified.
- For data or training format work, explicitly separate three layers:
  canonical source format, preprocessor/trainer-visible target, and adapter
  format used by a framework. Do not describe an adapter shape as the source
  contract, and do not claim a source JSON is trainer-ready until the
  preprocessor/masking path is verified.
- For external collaborator formats, inspect the actual examples and training
  code when possible. Treat a prose format document as necessary but not
  sufficient if the live training code rewrites fields before labels are built.
- For coordinates and GUI actions, require a verifier/smoke path that checks
  both structure and model-visible target text. Drag, move, scroll, coordinate
  normalization, placeholder replacement, and loss/mask placement should be
  called out when they can silently corrupt training data.
- The rendered HTML is an operator review surface. Keep font sizes readable for
  Chinese text, preserve stable step ids, make annotation controls obvious, and
  put enough context on the page that the operator does not need to re-open raw
  research to decide 采纳/改/砍.
