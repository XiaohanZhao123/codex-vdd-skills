---
name: verifier-driven-development
description: Verifier-Driven Development (VDD) workflow for non-trivial implementation, rewrite, refactor, simplification, data-pipeline, exporter, adapter, prompt, UI preview, training-format work, failure investigation, review feedback, and completion claims. Use when Codex needs to turn operator intent into explicit contracts, mocks, code verifiers, sub-agent verifier passes, and layered validation before, during, or after code changes.
---

# Verifier-Driven Development (VDD)

Use this skill when the work is complex enough that "the code runs" is not a
sufficient proof of correctness. VDD turns the operator's intent into a small,
executable feedback loop before the implementation grows large.

Verification is not a final checklist. It is the development loop:
contract first, mock set second, implementation third, verifier feedback
throughout.

Defensive delivery gates and reviewer-role patterns in this skill are adapted
from Superpowers v5.1.3, MIT License, source
`https://github.com/obra/superpowers` (Copyright (c) 2025 Jesse Vincent).

## Place In The Workflow

For work that needs human approval before implementation, the order is:

```text
Planboard -> VDD -> implementation -> /wrap
```

Planboard comes first and decides the intent, acceptance gates, verifier briefs,
and human review surface. VDD starts from the accepted brief and makes it
executable: mocks, code verifiers, sub-agent verifier prompts, preview
generation, smoke commands, and the implementation loop.

For vague quality requests, Planboard should not fan out into research
immediately. Run a short signal-driven clarification preflight first: ask only
for intent details the repo cannot infer, include a recommended default, allow
2-3 short turns when the answer changes the target or acceptance gate, and let
the operator's signal decide the next step. When the operator accepts the
default, says "you decide", says the direction is right, or asks to start
Planboard, record that signal and proceed. VDD treats the resulting preflight
brief as the top of the intent contract.

A verifier is code or an executable review artifact, but its design starts from
intent. Do not treat a verifier brief as a premature implementation plan. The
brief should name the mistake to catch, the source of truth, the verifier form,
the input artifact or mock, the pass/fail signal, what to do on failure, and
whether the verifier looks one-shot or reusable.

After implementation, VDD must close through the planned review surface. If the
gate depends on an HTML preview or other human-readable artifact, regenerate or
refresh it and report the current URL/path. Do not ask the operator to review a
large chat-context summary when the evidence can be put in a focused artifact.

At session end, `/wrap` decides lifecycle only: keep reusable docs/verifiers,
retire stale or task-only surfaces that still need explicit cleanup, and promote
repeated failure classes into hooks, lints, durable verifiers, or runbook rules.
It does not rerun VDD or redesign the plan.

## Start From The Spec: Two Ways In

VDD is the executable bridge from **Planboard → VDD → implementation**, and it maps
onto the **double loop** of ATDD: the acceptance gate is the outer loop (does the
outcome meet the requirement?), while the implementation's unit checks are the
inner loop. VDD makes the outer loop real by turning each gate into an executable
check with evidence that matches the requirement. A new or changed behavior is
red on the current baseline until implemented. A preservation requirement is
green on the baseline, red under each controlled mutant, and green again after
the mutant is removed. The main agent or explicit workers then implement against
those checks; `/wrap` runs only afterward to reconcile documentation and verifier
lifecycle.

**With a planboard spec (the normal path).** When a planboard acceptance spec
exists (`/tmp/planboard/<slug>-r<N>.json`: `requirements[]`, each with a `gate`
brief and a `gate_strength` record), consume it directly instead of re-extracting
intent — the gates *are* the contract. Map it in:

- `gate.criterion` + the requirement's `examples` (Given-When-Then) → the
  executable acceptance test to write. The JSON brief and executable test are
  separate artifacts that express the same acceptance claim; keep them traceably
  aligned.
- `gate.verifier_form` → which verifier to build (`code` / `script` / `data-check`
  / `preview` / `subagent` / `human`). `gate.source_of_truth`, `input_form`, and
  `signal` supply the oracle, the fixture, and the pass/fail condition.
- `gate.failure_response` → what to do when the gate fails: block, repair,
  regenerate, filter/drop, warn, or escalate. Follow the accepted policy; do not
  invent one during implementation.
- `gate.reuse` → the existing verifier/test to extend rather than write fresh.
- `gate_strength.mutants` → **ready-made red cases and regression fixtures**.
  Planboard already attacked the gate brief with these; build the real verifier and
  confirm it goes **red on each mutant** (proof it is not vacuous). For a preservation
  gate, also prove baseline green, mutant red, then restored baseline green before
  implementation. Keep the killed mutants as regression cases.
- `gate_strength.verdict` → readiness. `strong` gates are ready to build. A
  `weak`/`open` gate, or a requirement planboard downgraded into a
  `needs-operator` decision, is not buildable yet — resolve it (strengthen the gate,
  or get the decision) before writing its verifier, not after.

**Without a planboard spec (start light).** For a small task where a full planboard
is overkill, VDD raises its own minimal contract: name one or two acceptance
properties and their gates directly (Workflow Step 1 below), build the verifier,
and collect the matching baseline/mutant evidence. Do not spin up planboard for
work whose gates you can state in a sentence — the lightweight path is the point.

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
debugging. A good preview makes the human judge the hard semantic question
directly, while code handles plumbing and format checks first.

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

When the operator names a failure class or acceptance property, make the first
new artifact a verifier that exposes that failure. For a new or changed behavior,
run it on the current baseline and record the intended red result. For a behavior
that must remain unchanged, record baseline green, controlled-mutant red, and
restored baseline green. If the verifier cannot be written from the current
contract, ask for the missing contract detail before implementing.

When a planboard gate supplies the property, its `gate_strength.mutants` are the
red cases: the verifier must fail on each before you implement. A verifier that
cannot be made red on any mutant is vacuous — fix the gate, not the verifier.

If a manual correction exposes a class of mistake that can recur, decide whether
it should become a verifier, a mock case, or a focused sub-agent review.

For generated or probabilistic outputs, make the verifier policy explicit before
rerunning the pipeline: accept, repair, regenerate, filter/drop, or warn. If bad
outputs would poison downstream training or review, prefer a high-precision gate
and report the yield loss instead of silently keeping questionable rows.

## Defensive Delivery Gates

Use these gates whenever the work involves a failure, review comment, external
workflow import, or completion claim. They are part of VDD, not a separate
process: the output of each gate should either update the contract, add a mock,
tighten a verifier, improve a review artifact, or become a documented residual
risk.

### Failure Investigation Gate

Before fixing a failing test, broken build, bad export, prompt drift, review
artifact bug, or unexpected runtime behavior:

- reproduce the failure or inspect the exact failing artifact;
- read the full error/log/output that makes the failure real;
- compare one known-good path, fixture, row, command, or previous artifact with
  the failing path;
- trace the first boundary where the value, state, shape, or behavior becomes
  wrong;
- state one hypothesis and test one variable at a time.

If three fixes fail, stop editing the implementation and question the contract,
fixture, entrypoint, dependency boundary, or architecture. Add a smaller trace,
mock, or verifier if the current evidence does not reveal the first bad
boundary. Do not weaken a verifier because the root cause is inconvenient.

### Review Feedback Gate

Review findings are evidence, not instructions. Classify each finding before
editing:

- `worth-fixing`: a real bug, regression risk, missing verifier, unclear
  contract, misleading artifact, or maintainability problem that affects future
  work.
- `wrong-analysis`: contradicted by code, tests, docs, artifacts, or the
  accepted contract.
- `not-worth-fixing`: style churn or speculative cleanup that does not improve
  safety, clarity, or maintainability for the current change.

For worth-fixing findings, make the smallest targeted edit and rerun the
relevant check. For rejected findings, keep the decisive evidence short:
path/line, command output, artifact ID, or contract clause. If a finding exposes
a repeated failure class, convert it into a verifier or reviewer prompt item.

### Completion Evidence Gate

Before saying a task is done, fixed, passing, ready, or safe to commit:

- run a fresh command or artifact generation step that covers the changed
  contract;
- read the output, not only the exit code;
- check whether warnings are acceptable under the contract's failure policy;
- verify the generated artifact is current when the claim depends on generated
  files;
- report the exact command/result, or state the smallest missing verification
  and why it was not run.

Stale test results, informal samples, cached artifacts, warning-only summaries,
and a subagent's success report are incomplete evidence until independently
checked or intentionally accepted with provenance.

### External Workflow Import Gate

When benchmarking or vendoring an external agent workflow, import only the parts
that strengthen this repository's verifier loop:

- principles that change a decision rule;
- reviewer roles with bounded input, evidence, and output contracts;
- reusable checks that map to an existing skill, verifier, or runbook;
- attribution and license notices for copied or adapted material.

Avoid importing a total-control process tree, a parallel planning system, or an
implementer role unless the target repository already has a repeated need for
that exact role. Prefer small VDD upgrades: sharper verifier gates, better
reviewer prompts, explicit stop conditions, and clearer completion evidence.

## Workflow

### 1. Extract The Intent Contract

This step is the lightweight, no-planboard path — and the fallback when a planboard
gate left something under-specified. When a planboard spec exists, its `gate` briefs
already are this contract: skip to building the verifiers (Step 3) and use this step
only to fill a gap the gate left open.

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

Before leaving this step, name the acceptance gates in the order they should be
reported. Match each gate to the operator's requirement rather than to the
easiest downstream number.

Examples:

- Requirement: "select a subset from a superset." Gate: heterogeneous samples
  produce different active subsets. Red result: every sample selects the full
  superset.
- Requirement: "matching absence should not earn positive credit." Gate: the
  scoring denominator excludes double-absent fields. Red result: the final
  score looks fine but the denominator includes rows that neither side uses.
- Requirement: "the preview proves the semantic claim." Gate: the HTML exposes
  the exact fields the human must judge. Red result: the page renders but the
  operator must infer the important relation from raw logs or scattered files.

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

Use the readiness sequence that matches the requirement:

1. Add or identify the verifier that expresses the failure class.
2. For new or changed behavior, confirm the current baseline fails for the
   intended reason. For preserved behavior, confirm baseline green, each
   controlled mutant red, and the restored baseline green.
3. Implement the smallest change that makes every new/change gate pass while
   keeping every preservation gate green.
4. Keep the killed mutant or failing fixture as a regression case.

When a planboard gate supplies `gate_strength.mutants`, seed steps 1–2 with them:
each mutant is a concrete way to violate the requirement, so the verifier must go
red on it. The mutants it kills become the regression cases in step 4. The verifier
type follows the gate's `verifier_form`.

Put the verifier at the layer where the claim lives. A deterministic scorer
proves repeatability; it does not prove the extracted contract is meaningful. A
readable preview proves the review surface exists; it does not prove the
scoring denominator is right. A parser proves shape; it does not prove semantic
selection.

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
green run. If the failure is not understood, reproduce or inspect the artifact,
trace the first bad boundary, and test one hypothesis at a time before changing
the implementation.

When reporting progress, lead with the acceptance gates, not with convenient
secondary numbers. For example, report contract diversity before score spread
when diversity was the acceptance property. Report denominator membership before
the aggregate score when denominator design was the risk.

### 5. Use Subagents As Challenge Surfaces

Use subagents when independent context is valuable or the operator asks for
fan-out. They should challenge the work, not act as vague brainstorming threads.
Delegate only when the subtask has its own files/artifacts, no shared-state
conflict, and a clear stop condition.

Good sub-agent tasks:

- verify that the contract matches code/docs/data;
- find missing mock cases before edits;
- inspect generated artifacts for format drift;
- compare a proposed rewrite against the old behavior;
- review whether human feedback should become a code verifier.

If the repository includes `vdd-spec-reviewer` or `vdd-plan-reviewer` agent
roles, use them for independent gate-executability/strength checks (spec) and
readiness/coverage checks (plan-reviewer, repurposed). Prefer the
platform's native code-review tool or an existing code-review skill for code
review; do not create a parallel implementer workflow by default.

Use the independent-domain test before dispatching:

- **Own source of truth**: the agent can answer from the files, artifacts, or
  command outputs named in its prompt.
- **No sequencing ownership**: the agent is not deciding the next main-thread
  implementation step.
- **Observable stop condition**: it can return `Approved` / `Issues Found` /
  `Blocked` without asking for conversational clarification.
- **Bounded write scope**: reviewer agents are read-only unless the parent
  explicitly assigns a disjoint edit set.
- **Evidence-bearing output**: every blocker includes path/section/ID/snippet
  or command output plus the smallest correction.

Good subagent prompts are closer to verifier specs than brainstorming prompts.
They name the artifact, source of truth, risk class, severity scale, expected
red/green evidence, and what not to review. They also include a positive
approval path so the agent does not manufacture advisory churn.

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

### Reviewer Role Contracts

Use reviewer roles when the review surface is stable enough to encode once and
reuse. Keep each role narrow:

- `vdd-spec-reviewer` reviews the acceptance spec before verifiers are built — a
  planboard spec (`requirements[]` + `gate` briefs + `gate_strength`) or a
  self-raised contract. It audits **gate executability and strength**: is each gate
  buildable into a verifier with the right readiness evidence, is its
  `source_of_truth` real, did any gate
  ship `weak`/`open`/vacuous, is any intent-named failure mode uncovered, is any
  requirement missing a gate. It blocks only on gaps that would make a verifier
  wrong or unbuildable: missing acceptance property, missing source of truth,
  missing failure policy, contradiction, or a gate no mutant can turn red.
- `vdd-plan-reviewer` (repurposed) confirms the built verifiers before
  implementation: every new/change gate is red on the unmet baseline; every
  preservation gate shows baseline green, mutant red, and restored green; every
  `gate_strength.mutant` is covered; and no accepted requirement lacks a built
  verifier. VDD does not produce an implementation plan; the main agent or explicit
  workers own L2 sequencing during implementation. The VDD review checks verifier
  sensitivity and coverage, not task ordering.

Do not add a VDD implementer role by default. Implementation should stay owned
by the main agent or by explicit worker agents with disjoint write scopes. Do
not add a generic VDD code reviewer when the platform already provides native
code review or the repository has an existing review skill. The VDD-specific
gap is earlier: contract readiness and plan executability.

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

When a review surface was part of the accepted plan, refresh it before final
acceptance and make it the operator-facing evidence. The final response should
point to the current artifact and summarize the gates it supports, not reproduce
the whole context trail.

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
- review findings accepted or rejected, when applicable;
- unresolved risks or intentionally rejected verifier findings.

Lead with blockers when any remain.
