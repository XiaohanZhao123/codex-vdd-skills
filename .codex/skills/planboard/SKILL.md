---
name: planboard
description: Browser-reviewable implementation planning for non-trivial changes. Use when the operator asks for planboard, a plan they can annotate in the browser, or a step-by-step plan before code. The current Orchestrator must run a short clarification preflight when the request is vague, then spawn Codex sub-agents for research, synthesis, and verification, and render the final JSON plan to an annotatable HTML page. Do not use for trivial one-file edits or quick questions.
---

# planboard

Planboard produces an implementation plan that the operator reviews in a browser
before code is written. It is a current-session Orchestrator workflow: do not
open a nested `codex exec` to plan.

In the Planboard -> VDD -> wrap lifecycle, Planboard comes first. Its job is to
clarify intent, split the work, and design verifier briefs that VDD can later
turn into real tests, scripts, sub-agent prompts, preview pages, and smoke
commands. Do not use Planboard to pretend the verifier already exists.

## Assets

- `render_planboard.py` — stdlib renderer: plan JSON to annotatable HTML.
- `references/plan-schema.md` — JSON contract. Read it before writing the final
  plan JSON.
- `.codex/agents/planboard-{researcher,synthesizer,verifier}.toml` — project
  subagent roles. Prefer these names when the current Codex surface exposes
  custom agents; otherwise spawn generic Codex subagents with equivalent prompts.

## Clarification Preflight

Before spawning Planboard research agents, decide whether the operator's request
is concrete enough to plan. This is a short signal-driven exchange, not a full
interview and not a questionnaire.

Run the preflight when the request is directionally clear but operationally
vague, especially for quality words such as readability, usability, polish,
cleanup, simplification, "make it clearer", "better review", "improve UX", or
"optimize". Also run it when the target surface, audience, success signal,
priority, or rewrite-vs-side-path boundary cannot be inferred from the repo.

Skip the preflight only when the conversation already gives enough context to
name acceptance gates and verifier briefs. When skipping, state the assumptions
briefly and proceed to normal Planboard research.

Preflight rules:

- Inspect the repo first for facts it can answer. Ask the operator only for
  intent, audience, target surface, success criteria, priority, or a true scope
  choice.
- Ask in the operator's language. Usually one round is enough, but 2-3 short
  turns are fine when the answer changes the target or exposes a missing
  acceptance gate. Keep each turn to at most 1-3 focused questions; prefer one
  compact question with bullets when possible.
- Include a recommended default and a reason so the operator can answer "use
  the default" and unblock the plan.
- For vague quality goals, identify the target surface, the current pain, the
  reviewer/user, and the observable success signal. If one of these is obvious
  from context, state it as an assumption instead of asking.
- Do not spawn research, synthesis, or verifier subagents until the preflight is
  sufficient.
- Let the operator's signal decide the next step: proceed when they accept the
  default, say "you decide", say the direction is right, or ask to start
  Planboard; ask one more focused follow-up only when their answer changes the
  intent and the acceptance gate is still unclear.

Example shape for `提升可读性`:

```text
开 Planboard 前我先确认一个点：这次“可读性”主要卡在哪里？
我建议默认按 HTML review surface 来做：第一页能直接看到结论、失败点和下一步，不用回翻聊天记录。
如果这个方向对，回“默认”或“开 planboard”就行；如果不是，请告诉我目标页面/输出和最痛的阅读问题，我再追一个短问题后开 planboard。
```

## Orchestrator Contract

The main Orchestrator runs the planning loop and keeps raw research out of the
operator-facing answer. Subagents are mandatory for non-trivial planboard runs;
if the current Codex surface cannot spawn subagents, report that blocker instead
of silently performing the workflow in the parent context.

1. Read the repository's primary agent instruction file if present (`CLAUDE.md`,
   `AGENTS.md`, `.codex/README.md`, or equivalent), this skill, and
   `references/plan-schema.md`.
2. Run the Clarification Preflight before any subagent spawn. If it requires an
   operator answer, ask and wait for the operator's signal. Continue the
   preflight only while the signal changes intent or leaves the acceptance gate
   unclear; otherwise proceed. Record a short preflight brief, including the
   signal that ended the exchange, and pass it to every research and synthesis
   agent as binding context.
3. Spawn parallel sub-agents for the five research angles. Use the available
   Codex subagent tool directly from the current session, pass narrow prompts,
   and avoid forking broad parent context unless the task requires it:
   - `grounding`: existing code patterns, module boundaries, concrete files/functions.
   - `integration`: callers, configs, schemas, CLIs, data contracts.
   - `risks`: failure modes, compatibility, migration concerns.
   - `tests`: existing coverage, missing tests, validation commands.
   - `priorart`: similar in-repo implementations and design alternatives.
4. Wait for the research agents. Do not paste raw findings to the operator.
5. Spawn three synthesis sub-agents using different lenses. Give each synthesis
   agent only the task, schema constraints, and distilled research findings it
   needs:
   - `minimal`: the smallest complete plan.
   - `robust`: pin behavior and validation before changing risky surfaces.
   - `impact`: highest-leverage work first.
6. Judge the candidates into one plan with at most six load-bearing steps.
   If there are A/B/C-style choices, choose the recommended default, state the
   reason, and record rejected options in `alternatives_considered` when they
   still matter.
7. Verify every step's claims and verifier briefs against actual repo files,
   either directly in the Orchestrator or with a final verification subagent.
   Verifier findings should name the affected step id, cite the evidence
   command or file line, and give the smallest correction. Cut unsupported
   steps. For vague quality requests, also verify that the plan is anchored to
   the preflight brief rather than a generic improvement label.
8. Run the operator-visible plan text through `shuorenhua` before rendering.
   Treat the plan as `status/docs` prose, use `minimal` or `standard` cleanup,
   and preserve protected spans: file paths, commands, code symbols, schema
   keys, step ids, A/B/C labels, verdict tags, and cited evidence. Clean only
   visible prose fields such as `headline`, `approach_summary`, step `title`,
   `summary`, `what`, `why`, `verification`, `risk`,
   `changes_from_previous_round`, `alternatives_considered`, `open_questions`,
   and `deferred`. The pass must remove template/AI-flavored phrasing without
   adding facts, weakening decisions, or changing the plan contract.
9. Write the final plan JSON to `/tmp/planboard/<slug>-r<N>.json`.
10. Render directly with the bundled renderer:

```bash
python3 .codex/skills/planboard/render_planboard.py \
  /tmp/planboard/<slug>-r<N>.json \
  "${PLANBOARD_PREVIEW_DIR:-/tmp/planboard-previews}"/planboard-<slug>-<YYYYMMDD>-r<N>.html \
  --slug <slug>
```

11. Reply with only the URL plus one short instruction: mark each step 采纳/改/砍,
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

If revision feedback introduces a vague quality goal or changes the audience,
target surface, or success signal, run the Clarification Preflight again before
starting the next research round.

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
- Treat `verification` as a verifier brief. It must name the acceptance gate,
  the mistake or drift it should catch, the source of truth, the verifier form
  (`code`, `script`, `preview`, `subagent`, `human`), the input artifact/mock,
  the pass/fail signal, the failure response, and the likely lifecycle
  (`one-shot`, `reusable`, or `wrap-decides`). Keep it concise, but do not
  collapse it into "run relevant tests".
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
