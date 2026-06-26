---
name: verifier-driven-development
description: Verifier-Driven Development (VDD) workflow for non-trivial implementation, rewrite, refactor, simplification, data-pipeline, exporter, adapter, prompt, UI preview, and training-format work. Use when Codex needs to turn operator intent into explicit contracts, mocks, code verifiers, sub-agent verifier passes, and layered validation before or during code changes.
---

# Verifier-Driven Development (VDD)

Use this skill when the work is complex enough that "the code runs" is not a
sufficient proof of correctness. VDD turns the operator's intent into a small,
executable feedback loop before the implementation grows large.

Verification is not a final checklist. It is the development loop:
contract first, mock set second, implementation third, verifier feedback
throughout.

## Human Review Budget

Human review is a high-cost verifier, not a safety net for routine agent work.
Use it only at high-ROI choke points where automation cannot reliably judge the
outcome and a wrong decision would steer many later steps.

Default to automated verifiers, smoke runs, structured traces, and generated
previews that the implementer can inspect without stopping the operator. Stop
for human review only when the checkpoint has all of these properties:

- a clear decision the human is better positioned to make than code;
- compact artifacts that expose the decision without asking the human to debug;
- prior automated checks for schema, file existence, transport, and basic
  invariants have already passed or failed clearly;
- the answer changes the next implementation direction, experiment scope, or
  acceptance decision.

Good human-review gates include visual/semantic quality judgments, final
workflow acceptance, choosing between materially different product behaviors, or
approving an expensive/broad run. Poor gates include file plumbing, JSON schema
validity, routine per-step approvals, broken scripts, missing artifacts, or
anything the implementer can verify deterministically.

## Review Artifact Standard

When human review is justified, the artifact must be built for review, not for
debugging. A good preview follows the pattern that worked in CUA Mobile's
Node-A and SFT sample reviews: the page makes the human judge the hard semantic
question directly, while code handles plumbing and format checks first.

Design the artifact around the purpose of the review:

- expose the semantic relationship that automation cannot reliably judge, such
  as image-coordinate-action alignment, source-vs-adapter separation, target
  masking, visual quality, or whether feedback changed the next attempt;
- render the target contract directly, not a proxy that requires mental
  reconstruction;
- collocate the evidence needed for one judgment in one card or row: source
  truth, derived/model-visible form, relevant visual evidence, IDs, and
  provenance;
- use visual aids only when they reduce judgment load. Overlays, boxes, arrows,
  diffs, and side-by-side views are tools for showing correspondence, scale,
  locality, ordering, or change; they are not requirements by themselves;
- use stratified sampling when coverage matters, so every important semantic
  class or edge case appears at least once;
- include a compact audit header with counts, histograms, selected cases,
  warnings, verifier status, and exactly what decision the operator is being
  asked to make;
- copy or generate assets next to the HTML so the page is self-contained and
  stable under a preview server;
- run deterministic contract checks before writing the page, and fail clearly
  instead of asking the operator to notice missing or stale artifacts.

Avoid review pages that make the operator cross-reference loose files, raw logs,
long JSON dumps, or unstratified first-N samples. Those are implementer/debug
surfaces, not human-review gates.

## Core Rule

Before changing non-trivial behavior, state the behavior that must be preserved
or produced. Then make that behavior checkable with the smallest useful mix of
existing tests, new mocks, code verifiers, sub-agent verifier prompts, previews,
or real-entrypoint smoke runs.

If a manual correction exposes a class of mistake that can recur, decide whether
it should become a verifier, a mock case, or a focused sub-agent review.

For generated or probabilistic outputs, make the verifier policy explicit before
rerunning the pipeline: accept, repair, regenerate, filter/drop, or warn. If bad
outputs would poison downstream training or review, prefer a high-precision gate
and report the yield loss instead of silently keeping questionable rows.

## Workflow

### 1. Extract The Intent Contract

Write down the contract in operational terms. Include only details that can
affect implementation or validation:

- accepted inputs and rejected inputs;
- model-visible outputs, files, rows, messages, rendered text, UI, or side
  effects;
- ordering, masks, coordinate scales, defaults, IDs, provenance, warning/error
  policy, and skipped cases;
- what must remain separate, such as source format vs consumer adapter, internal
  state vs trainer-facing rows, or automated checks vs human review;
- how verifier failures should be handled, especially for generated artifacts
  where the choice may be regenerate, repair, filter, or keep with a warning;
- the recommended default when the codebase does not fully decide.

Inspect code, tests, docs, and prior artifacts before asking the operator. Ask
only for decisions the repository cannot answer.

### 2. Build A Mock Set

Prefer small decisive examples over broad snapshots. A good mock set is boring
to run and hard for the wrong implementation to pass.

Use mocks to cover:

- the common valid path;
- the edge case the operator explicitly worries about;
- one invalid input that should fail before downstream code crashes;
- one future-facing or multi-turn case when the chosen format must support it;
- visual or model-visible output when humans or trainers consume the result.

Mocks can be unit fixtures, JSON rows, tiny local datasets, rendered HTML pages,
prompt samples, CLI input dirs, or synthetic API payloads. Keep them close to
the verifier or test that consumes them.

### 3. Reuse And Extend Verifiers

Start with existing verifiers, tests, and smoke commands. If they cannot catch a
mistake the operator has identified, extend them before relying on manual review.

Use the right verifier type:

- **Code verifier**: deterministic structure, schema, coordinates, masks,
  parser boundaries, file existence, prompt forbidden terms, output scales.
- **Semantic verifier**: consistency between generated reasoning and actions,
  prompt labels, task state, provenance, and the intent visible in inputs.
- **Entrypoint smoke**: CLI/script behavior, generated artifact shape, real
  adapter consumption, framework preprocessing.
- **Preview verifier**: HTML/image/UI rendering where humans need to inspect
  semantic correspondence, visual quality, ordering, scale, locality, or
  readability.
- **Sub-agent verifier**: independent context checks for non-obvious semantic
  risks, stale assumptions, contract conflicts, or whether a simplification lost
  intent.

Do not scatter one-off checks through unrelated modules. Put verifier code and
verifier prompts in discoverable verifier/test locations that future agents will
reuse.

### 4. Implement In The Loop

Make the smallest implementation that satisfies the current contract. After each
meaningful change, run the narrow verifier that should catch the most likely
drift. Broaden validation only after the narrow loop is green.

When a verifier fails, classify it before editing again:

- real implementation bug;
- stale or underspecified contract;
- mock that no longer represents the intended behavior;
- verifier that is too broad, too narrow, or checking the wrong layer.

Fix the layer that is actually wrong. Do not weaken a verifier just to get a
green run.

### 5. Use Subagents As Challenge Surfaces

Use subagents when independent context is valuable or the operator asks for
fan-out. They should challenge the work, not act as vague brainstorming threads.

Good sub-agent tasks:

- verify that the contract matches code/docs/data;
- find missing mock cases before edits;
- inspect generated artifacts for format drift;
- compare a proposed rewrite against the old behavior;
- review whether human feedback should become a code verifier.

Give subagents raw artifacts and a bounded question. Avoid leaking your intended
answer unless the task is explicitly to review that answer. Resolve routine
sub-agent questions yourself; escalate only decisions the repo cannot settle.

Verifier prompts must be high quality. Include:

- the exact artifacts to inspect and which artifact is source of truth;
- a bounded checklist of semantic risks, stale formats, coordinate/scale
  mismatches, ordering mistakes, or role/transport violations;
- forbidden fallbacks or known-bad legacy markers when relevant;
- an output contract that requires severity, evidence path/ID/snippet, and the
  smallest concrete correction;
- an explicit "no blocking issues" path plus residual risks that still require
  human visual or semantic judgment.

Do not send a subagent a broad "review this" prompt when the failure class is
known. Turn the known failure class into a verifier prompt item, then feed any
new finding back into a code verifier, stratification bucket, review artifact,
or documented residual risk.

### 6. Simplify With The Same Contract

Use the same loop for cleanup and refactoring. Lock behavior with mocks and
verifiers first, simplify second, then run the same checks again.

Good simplification removes obsolete paths, duplicate logic, or confusing
interfaces after the verified replacement covers the contract. Avoid abstraction
that only makes the code look cleaner while hiding behavior that the verifier
needs to observe.

### 7. Feed Human Review Back Into Verification

Human review, HTML preview, trainer-format inspection, and operator feedback are
part of the verifier loop. They catch classes of mistakes automation missed.
They should be placed sparingly: use generated previews as evidence, but ask the
operator to review only the highest-ROI checkpoints described in the Human
Review Budget.

Treat the review surface itself as a product of the verifier system. A useful
preview should make suspicious cases easy to find, jump to, and inspect without
UI chrome blocking the evidence. When possible, verify the preview structure:
links target existing items, referenced assets exist, flagged cases are marked,
and layout choices do not hide the fields a human must compare.

After each manual correction, decide whether to add:

- a new mock;
- a stricter code verifier;
- a warning instead of an error for unsettled design territory;
- a focused sub-agent verifier prompt;
- a documented remaining risk when automation should not decide.

The goal is not to eliminate human judgment. The goal is to make repeated human
corrections unnecessary.

### 8. Close The Loop On Yield And Drift

For pipelines that synthesize, rationalize, rank, or otherwise generate data,
validation should answer two questions:

- did the new contract reduce the known failure class?
- how many otherwise useful samples did the verifier reject?

Keep rejected samples auditable enough for spot checks. Report counts, examples,
and the reason they failed. If the drop rate is too high, fix the upstream
contract, prompt, adapter, or model input before weakening the verifier. If the
drop rate is acceptable and the remaining data is cleaner, keep the precision
gate and make the loss visible in the final report.

## Reporting

When reporting the result, keep it short and concrete:

- contract protected or changed;
- mocks/verifiers added or reused;
- implementation changes made;
- validation commands and outcomes;
- unresolved risks or intentionally rejected verifier findings.

Lead with blockers when any remain.
