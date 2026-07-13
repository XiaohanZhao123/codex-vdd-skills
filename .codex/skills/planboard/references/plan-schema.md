# planboard spec JSON schema

The contract between the planboard Orchestrator (producer) and `render_planboard.py`
(consumer). Both sides assume this shape; keep them in sync.

The artifact is an **L1 acceptance spec**, not an implementation plan. The core unit is
a `requirement` fused to its acceptance `gate` — a SET, grouped by scope, **unordered**.
There are no `steps`, no `depends_on`, no `commands`, no `files` (those are L2,
deferred to VDD/implementation).

```jsonc
{
  "task": "string — the thing being planned, verbatim",
  "round": 1,                          // int, increments each revision round
  "task_class": "code | data",         // P0 result; research/docs never reach the renderer

  "headline": "string — the whole spec grasped in one breath",
  "intent": "string — the GQM Goal in the operator's words; the source of truth every gate serves",

  "changes_from_previous_round": [      // optional; required for revision rounds
    {
      "unit_id": "req-2",               // stable id across req-/dec-/scope-
      "status": "改|新增|砍|补约束|保留|决策已定",
      "change": "string — what changed and why it needs a re-look"
    }
  ],

  "requirements": [                     // THE SET — grouped by scope_id, UNORDERED (no depends_on)
    {
      "id": "req-1",                    // stable across rounds; never renumber a survivor
      "scope_id": "scope-1",            // grouping only, not order
      "requirement": "string — what must be true about the outcome; solution-agnostic",
      "why": "string — the GQM intent it serves",
      "examples": [                     // Specification by Example / Given-When-Then
        { "given": "…", "when": "…", "then": "…", "kind": "happy|edge|negative" }
      ],
      "gate": {                         // the acceptance gate = a VDD verifier BRIEF (stop here; not test code)
        "criterion": "string — measurable, observable, implementation-agnostic Given-When-Then pass condition",
        "failure_class": "string — the error/drift this must catch",
        "source_of_truth": "string — metric / fixture / existing scorer / human — who decides pass/fail",
        "input_form": "string — fixture/mock/input-artifact form; prefer a real fixture",
        "signal": "string — the pass/fail signal: threshold / exact-match / invariant",
        "failure_response": "string — what VDD must do on failure: block / repair / regenerate / filter-drop / warn / escalate",
        "verifier_form": "code | script | data-check | preview | subagent | human",
        "lifecycle": "one-shot | reusable | wrap-decides",
        "reuse": "string|null — an extendable existing verifier/test path, else null"
      },
      "gate_strength": {                // P4 mutation record — the spine; earned, not asserted
        "mutants": [ { "mutant": "a concrete way to violate the requirement", "caught_by_gate": true, "hardening": "what was added if it survived" } ],
        "verdict": "strong | weak | open",   // strong = no surviving mutant; open = mutants not yet listed
        "smells": [ "tautological | assertion-free | shape-only | happy-path-only" ]
      },
      "coverage": "covered | gap"        // completeness-critic result
    }
  ],

  "scopes": [                           // Shape Up — coarse fat-marker outcomes, NOT tasks (read-only grouping)
    {
      "id": "scope-1",
      "name": "string — coarse outcome name",
      "outcome": "string — the thin vertical slice delivered",
      "appetite": "S | M | L",          // time-box, not an estimate
      "requirement_ids": [ "req-1", "req-2" ],
      "rabbit_holes": [ "string" ]        // known traps to avoid (optional)
    }
  ],

  "decisions": [                        // ADR — one decision per record (absorbs the old alternatives_considered)
    {
      "id": "dec-1",
      "decision": "string — the call to make",
      "options": [ { "label": "A", "shape": "…", "implication": "…" } ],
      "recommendation": "A",            // preselected in the radio
      "reason": "string",
      "status": "recommended | open | accepted | needs-operator",
      "affects": [ "req-1", "scope-1" ]  // which requirements hang on it
    }
  ],

  "non_goals": [ "string — explicitly out of scope (absorbs the won't-do half of the old deferred)" ],
  "uncovered_failure_modes": [ "string — an intent-named failure mode with no gate; must be empty or explained before ship" ],
  "open_questions": [ "string — genuine unknowns found while building (<= 3)" ]
}
```

## Invariants

- **Each unit is an L1 decision the operator owns** — a `requirement+gate`, a `decision`,
  or a `scope`. `requirement` states what must be true; `gate` states how it is proven.
  Which class/file/call-order realizes it is L2 and stays off the board.
- **Required per requirement:** `id`, `requirement`, and these gate fields:
  `criterion`, `failure_class`, `source_of_truth`, `input_form`, `signal`,
  `failure_response`, `verifier_form`, and `lifecycle`. `reuse` is optional.
  `examples`, `gate_strength`, and `coverage` are added by later phases; missing them
  renders degraded but valid.
- **The gate is a brief, not a test.** Runnable assertions inside a gate are a VDD-boundary
  smell; pull them back to the brief.
- **Gate strength is earned.** `verdict:"strong"` requires every required gate field,
  at least one listed mutant, and no surviving mutant. The renderer recomputes this effective
  verdict: missing gate fields or no mutants render as `open`; a surviving mutant or
  `coverage:"gap"` renders as `weak`, even if the JSON claims `strong`. An irredeemably
  vacuous gate (mutants always survive, no oracle) is not kept as a weak requirement — the
  requirement is **downgraded into a `decisions[]` entry** with `status:"needs-operator"`.
- **The coverage header is an invariant.** A requirement with no gate, or a gate whose verdict
  is not `strong`, a missing/invalid `coverage` result, a missing P5
  `uncovered_failure_modes` list, or a non-empty `uncovered_failure_modes`, is a spec defect the
  renderer must surface at the top — never hide it.
- **Applicability is per requirement.** A research-flavored requirement with no writable verifier
  goes to `non_goals` or carries `verifier_form:"human"`; the rest of the spec still ships. Decline
  the whole request only when no requirement is verifier-writable.
- **Stable ids are load-bearing.** The HTML keys per-unit annotations by `id` (`req-`/`dec-`/`scope-`),
  and revision rounds match 采纳/改/砍 verdicts and decision choices back by `id`. IDs must be
  non-empty, globally unique across all unit kinds, use their kind prefix, and produce unique
  renderer anchors. Never renumber a survivor.
- **Distillation budget:** ≤ 8 requirements, ≤ 4 scopes. Overflow goes to `non_goals` / `open_questions`,
  never a synthetic requirement.
- The renderer escapes all text; it degrades gracefully on a missing `headline` (uses the first
  sentence of `intent`) or `summary` fields.

## Scan / detail split

The HTML renders in two layers so the operator grasps the whole spec without reading prose:

- **Scan (always visible):** per requirement — `requirement` (one line) + the gate in one line
  (`gate.source_of_truth` + `gate.signal`, or `gate.criterion`) + the `gate_strength.verdict`
  badge (强 / 暂定 / 易空转) + the 采纳/改/砍 control. Per decision — `decision` + status badge +
  an A/B/C radio preselecting `recommendation`. Plus the coverage header at the top.
- **Detail (collapsed, 详情):** `why`, `examples` (Given-When-Then), the full gate brief,
  `gate_strength.mutants` + `smells`, `coverage`, `reuse`.
- **Read-only:** `scopes` render as a grouping band (name / outcome / appetite + requirement-id
  chips) with no verdict control; `non_goals` and `open_questions` as tail sections.

## Migration from the step-era schema

| Old (`steps[]` era) | New |
|---|---|
| `steps[]` (a sequence) | `requirements[]` (a set, grouped by `scope_id`, unordered) |
| `step.verification` (prose) | structured `gate{}` (brief) + `gate_strength{}` (mutation record) |
| `step.risk` | `gate.failure_class` or `scope.rabbit_holes` |
| `depends_on` / `commands` / `files` / build order | dropped from the operator view (L2, to VDD/implementation) |
| `alternatives_considered` | folded into `decisions[].options` (ADR, one per record) |
| `deferred` | split into `non_goals[]` (won't-do) and `open_questions[]` (unknowns) |
| `minimal/robust/impact` synthesis + `judge` | Example-Mapping elicitation → gate-designer → mutation-adversary → completeness-critic |
| stop = "≤ 6 steps" | stop = every requirement has a `strong` gate + zero orphan/uncovered |

The renderer keeps a thin backward-compat path: a JSON that still carries `steps[]` and no
`requirements[]` renders through the legacy step path so old plans still open.
