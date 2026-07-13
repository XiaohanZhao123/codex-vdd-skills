---
name: planboard
description: Browser-reviewable L1 acceptance-spec planning for non-trivial code or data changes. Use when the operator asks for planboard, a plan they can annotate in the browser, or a spec of "what must be true and how we verify it" before code. The Orchestrator runs a GQM intent interview, elicits requirements each fused to an acceptance gate, hardens every gate with a mutation-style attack via Codex sub-agents, then renders an annotatable HTML spec. Do not use for trivial one-file edits, quick questions, or research/docs tasks whose success has no writable verifier.
---

# planboard

Planboard produces an **L1 acceptance spec** the operator reviews in a browser
before code is written: a set of **requirements**, each fused to an **acceptance
gate** (how we prove it), plus the decisions, non-goals, and coarse scopes the
operator owns. It is a current-session Orchestrator workflow — do not open a
nested `codex exec` to plan.

In the **Planboard → VDD → implementation → /wrap** lifecycle, Planboard comes
first and stops at **verifier briefs**: it says *what must be true* and *how each
claim is checked* (failure class, source of truth, fixture form, pass/fail signal,
and what VDD must do when the gate fails).
VDD turns those briefs into executable verifiers; the main agent or explicit
workers implement against them. `/wrap` runs only after implementation to
reconcile documentation and verifier lifecycle. Planboard does not write tests or
implementation.

## Plan at L1: the unit is `requirement + gate`, a set, not a sequence

The operator reviews at the boundary. Their attention is the scarce resource, and
it belongs on **what must be true** and **whether the gate actually proves it** —
not on which class, file, or call order realizes it (that is L2, determined by L1,
and it goes to VDD/implementation). So the artifact is a **SET** of `requirement+gate`
units, grouped by scope, **unordered** — no `steps`, no `depends_on`, no build
sequence. A requirement is a solution-agnostic claim about the outcome; its gate
is the check that would fail if the claim were violated.

The load-bearing property is **gate strength**: a gate that passes while the
requirement is violated is worse than none — it launders a wish as a guarantee.
Every gate is attacked (mutation-style) and earns a `strong` verdict, or is shown
as `weak`/downgraded to a decision. Never render a gate as `strong` by assertion.

## Assets

- `render_planboard.py` — stdlib renderer: spec JSON → annotatable HTML.
- `references/plan-schema.md` — the JSON contract. Read it before writing the spec.
- `.codex/agents/planboard-{researcher,synthesizer,verifier}.toml` — the three
  Codex sub-agent roles, repurposed for this workflow: **researcher** elicits
  requirements (Example Mapping + one grounding probe), **synthesizer** designs a
  gate per requirement, and **verifier** runs separate mutation and coverage
  passes. The Orchestrator distills decisions/non-goals/scopes only after coverage.
  Prefer these names when the
  Codex surface exposes custom agents; otherwise spawn generic Codex sub-agents
  with equivalent prompts.

## Applicability gate (P0): code and data tasks only

Planboard is for changes whose success has a **writable verifier** — a check that
produces an observable red signal when a requirement is violated (a failing
assertion, a metric under threshold, a diff, a missing artifact). That is true for
**code and data** tasks; it is not reliably true for research/docs tasks, where the
"verifier" is a sub-agent judging against an uncertain standard.

Judge applicability **per requirement**, not per task (most real tasks mix). A
requirement that can carry a concrete verifier stays in the spec; a research-flavored
one whose only check is subjective goes to `non_goals` or is marked as a `human`-form
gate. Only decline the whole request when *no* requirement is verifier-writable —
then say so briefly and point the operator elsewhere. Set `task_class` to `code` or
`data`. Add one preflight line only when the class is genuinely ambiguous.

## GQM Intent Interview (P1 — the front touchpoint)

Requirements come from the operator's **intent**, elicited by asking — not from
digging through code, which overfits. When the goal is fuzzy ("quality high enough",
"faster", "cleaner"), turn it into observable metrics with **Goal → Question →
Metric** before anything else:

- **Goal**: one solution-agnostic sentence for what success is.
- **Question**: "How would we know it worked? What observable behavior changes?
  What would 'bad' look like? Where is quality judged — which metric or signal
  settles it?"
- **Metric**: the observable quantity each question lands on (the gate's future
  source of truth).

Ask in the operator's language. Each question carries a recommended default and a
one-line reason so the operator can answer "default / you decide" and unblock. Aim
for one round, cap at two. Read the repo only to confirm a fact the operator cannot
recall (does this fixture exist?) — never to infer a metric. For a quality goal, first
ask *where quality is judged and which metric*; do not read a pile of code to guess it.
Record a **GQM brief** (goal → metric/oracle per question) and pass it as binding
context to every later sub-agent.

Skip the interview only when the conversation already pins the goal, the metrics, and
the oracle. When skipping, state those assumptions in one line and proceed.

## Orchestrator Contract

The Orchestrator runs the loop and keeps raw sub-agent output out of the operator
answer. Sub-agents are mandatory for a non-trivial run; if the current Codex surface
cannot spawn sub-agents, report that blocker instead of doing the workflow silently in
the parent.

1. Read the repo's primary agent instructions (`CLAUDE.md`/`AGENTS.md`/`.codex/README.md`),
   this skill, and `references/plan-schema.md`.
2. **P0 Applicability** (per requirement, above) → set `task_class`; decline or
   downgrade research-only requests.
3. **P1 GQM Intent Interview** (above) → the GQM brief. This is the only proactive
   interruption before review.
4. **P2 Elicit requirements — the `researcher` role (Example Mapping).** Spawn the
   researcher sub-agent to run the Example-Mapping / Three-Amigos triangle from the GQM
   brief: **Rules → requirements** (solution-agnostic), **Examples → each requirement's
   Given-When-Then cases**, **Questions → open decisions for P5**. Run exactly one
   **bounded grounding probe** against the repo, scoped to two answers only: does a named
   fixture/metric exist, and is there a reusable verifier. The probe and the elicitor are
   forbidden from inventing requirements out of code — report `none`, never fabricate.
   This single elicitation pass replaces the old five research angles.
5. **P3 Design a gate per requirement — the `synthesizer` role (stop at the VDD brief).**
   Spawn the synthesizer to write each `gate.criterion` (Given-When-Then, measurable,
   observable, implementation-agnostic) and fill the brief fields VDD consumes:
   `failure_class`, `source_of_truth`, `input_form`, `signal`, `failure_response`, `verifier_form`
   (`code`/`script`/`data-check`/`preview`/`subagent`/`human`; prefer code/data),
   `lifecycle` (`one-shot`/`reusable`/`wrap-decides`), `reuse` (an extendable existing
   verifier path, or null). `failure_response` says whether a failed gate blocks,
   repairs, regenerates, filters/drops, warns, or escalates; VDD must not guess the
   policy. A real assertion or test code inside the gate is a smell — stop at the brief.
6. **P4 Harden every gate (mutation attack — the spine) — the `verifier` role.** Spawn the
   verifier to list concrete **mutants** per requirement (specific ways to violate it) and
   check each against the gate: caught or survived. A surviving mutant means the gate is not
   done — strengthen the brief or specify the needed red fixture in `input_form`, then re-check.
   Planboard names that fixture; VDD later builds it. Flag smells (tautological,
   assertion-free, shape-only, happy-path-only). Record
   `gate_strength{mutants[], verdict, smells[]}`; `strong` = no surviving mutant,
   `open` = mutants not yet listed. P4 must return one `gate_strength` record for every
   input requirement id; a missing record is `open`, never an implied pass. **When a gate
   is irredeemably vacuous** (mutants always
   survive and no oracle exists), do not keep it as a weak requirement: **downgrade the
   requirement into a `decisions[]` entry** (a `needs-operator` choice about how — or whether —
   to make it checkable).
7. **P5 Coverage + decisions + non-goals + scopes.** Spawn a **fresh** `verifier`
   invocation for the completeness check; do not reuse the mutation-adversary thread.
   It checks the whole set: which requirement has no P4 record or no `strong` gate, which intent-named
   failure mode has no gate (→ `uncovered_failure_modes`), and which gate has no parent
   requirement (scope creep). Gaps go on the coverage header, never silent; loop
   P2→P3→P4 until clean or explicitly marked. The Orchestrator then distills the Questions
   into `decisions[]` (ADR, one decision per record: decision, options + recommendation,
   status, `affects`), writes `non_goals[]` (RFC scope-out), and groups requirements into
   `scopes[]` (Shape-Up coarse fat-marker outcome + appetite + `requirement_ids` + optional
   `rabbit_holes`) — grouping only, no order, no files/commands.
8. **P6 Format + render.** The Orchestrator must invoke and follow the installed
   `shuorenhua` skill after the spec is stable; a phrase scan or a request to a
   synthesis sub-agent does not count as this pass. Treat the page as `docs`, use
   `standard` when the draft mixes internal jargon with operator-facing prose, and
   protect ids, paths, numbers, metric names, gate facts, and the
   `verifier_form`/`lifecycle`/`verdict` enums. Run both required rereads:
   - fidelity: every requirement, gate, mutant, source of truth, and pass/fail
     relation still means the same thing;
   - residual style: remove narrator framing, performative engineering jargon,
     unexplained shorthand, and over-uniform sentence patterns that still make the
     page read like a specification generator.
   Prefer direct questions and ordinary verbs in the scan layer. Keep technical
   terms where they carry the acceptance contract. Then write the JSON and render.

Verify (before render): check each gate against its P3 brief checklist and the coverage
invariant — not against a "step". A gate whose brief hides executable assertions is a
VDD-boundary smell; cut it back to a brief. Cut any requirement whose gate cannot be
grounded and cannot be downgraded to a decision.

**Stop condition:** every requirement has a gate with `gate_strength.verdict = strong`
(or is explicitly `weak`/`open` with a reason, or downgraded to a decision), and the
completeness check reports zero orphan requirement and zero unexplained
`uncovered_failure_mode`. Distillation budget: ≤ 8 requirements, ≤ 4 scopes; overflow
goes to `non_goals`/`open_questions`, never a synthetic requirement.

## Render + hand back

9. Write the spec JSON to `/tmp/planboard/<slug>-r<N>.json`.
10. Render:

```bash
python3 .codex/skills/planboard/render_planboard.py \
  /tmp/planboard/<slug>-r<N>.json \
  "${PLANBOARD_PREVIEW_DIR:-/tmp/planboard-previews}"/planboard-<slug>-<YYYYMMDD>-r<N>.html \
  --slug <slug>
```

11. Reply with only the URL plus one short instruction: mark each requirement / decision
    采纳/改/砍 (decision picks A/B/C), comment, click 复制批注, and paste the annotations back.

## Final Spec Rules

- Match `references/plan-schema.md`.
- Each unit is an L1 decision the operator owns — a `requirement+gate`, a `decision`, or a
  `scope` — never an implementation task. From the operator view there are no `files`,
  `commands`, `depends_on`, or step order.
- Required per requirement: `id`, `requirement`, and a gate containing `criterion`,
  `failure_class`, `source_of_truth`, `input_form`, `signal`, `failure_response`,
  `verifier_form`, and `lifecycle`. `reuse` is optional; `examples`, `gate_strength`,
  and `coverage` are filled by later phases.
- The gate is a **brief**, not a test. If it contains runnable assertions, it has crossed the
  VDD boundary — pull it back.
- Scannable layer per requirement: `requirement` (one line) + the gate in one line
  (`source_of_truth`+`signal`, or `criterion`) + the `gate_strength` badge + 采纳/改/砍.
  Details (examples, full brief, mutants, smells, coverage) live under 详情.
- `scopes` are a read-only grouping band (no verdict control). `decisions` carry an A/B/C
  radio preselecting the recommendation.
- The coverage header is an invariant surface: a requirement with no gate, a gate whose
  verdict is not `strong`, or a missing/invalid P5 coverage result is a spec defect the
  header must show — never hide it.
- Stable ids (`req-`/`dec-`/`scope-`) are load-bearing across rounds. Keep them
  globally unique and anchor-safe; never renumber a survivor. The HTML keys
  annotations by id and rejects ids that would collide after anchor normalization.
- Invoke `shuorenhua` on the visible layer before writing JSON, then complete its
  fidelity and residual-style rereads. Do not enter Codex plan mode.

## Language

Match the operator's language in replies and in operator-visible fields. `shuorenhua`
cleans prose but does not translate — if the operator works in Chinese, verify every
visible field (`headline`, `intent`, each requirement's `requirement`/`why`/`examples`
`then`/`gate.criterion`, decision prose, `non_goals`, `scope` names, `uncovered_failure_modes`,
`open_questions`, `changes_from_previous_round`) is in that language before writing JSON, and
keep protected spans English verbatim: file paths, commands, code symbols, schema keys, unit
ids, metric names, and the `verifier_form`/`lifecycle`/`verdict` enums.

## Revision Loop

When the operator pastes annotations:

- If everything is accepted or "开干", stop planning; hand off to VDD/implementation if
  requested.
- If the blob has questions without verdicts, answer those first.
- Otherwise rerun the loop for round `N+1`, passing the original task, the previous spec JSON,
  and the annotation blob verbatim.

Preserve accepted unit ids. Apply 改 notes directly. Drop 砍 units unless the note asks for a
replacement. Apply resolved `decision` choices and re-thread affected requirements. Populate
`changes_from_previous_round` with one item per changed/added/removed/decided unit (keyed by
`unit_id` across `req-`/`dec-`/`scope-`) — the renderer shows it as the top "本轮改动" block.
When feedback changes the intent, rerun P1 (GQM) before re-eliciting.

## Output Locations

- JSON scratch: `/tmp/planboard/<slug>-r<N>.json`
- HTML preview: `${PLANBOARD_PREVIEW_DIR:-/tmp/planboard-previews}/planboard-<slug>-<YYYYMMDD>-r<N>.html`
- URL: served by the preview server (a local default is
  `python3 -m http.server 8000 --directory "${PLANBOARD_PREVIEW_DIR:-/tmp/planboard-previews}"`).

Prefer a scratch or external preview directory over `$HOME` or the repo. Do not restart or
modify an existing preview server unless the operator asks.

## Content Judgment Rules

These shape the requirements and their gates (written in requirement+verifier terms, so they
apply directly):

- For rewrite/refactor requests, first settle whether the operator wants to replace the existing
  path or add a side path; when rewrite is confirmed, make "the old path is deleted/demoted after
  the new one is verified" an explicit requirement with its own gate.
- For data or training-format work, separate the three layers as distinct requirements: canonical
  source format, preprocessor/trainer-visible target, and framework adapter. Do not let a gate treat
  an adapter shape as the source contract, and do not call a source JSON trainer-ready until a gate
  covers the preprocessor/masking path.
- For external-collaborator formats, ground a gate on the actual examples + training code, not only a
  prose format doc — a doc is necessary but not sufficient when live code rewrites fields before labels
  are built.
- For coordinates and GUI actions, require a gate that checks both structure and model-visible target
  text; call out drag/move/scroll, coordinate normalization, placeholder replacement, and loss/mask
  placement as failure classes a gate must catch.
- The rendered HTML is the operator's review surface: readable text, stable ids, obvious annotation
  controls, and enough on the page (the coverage header + each gate's one-line summary) to judge
  采纳/改/砍 without reopening raw research.
