# planboard plan JSON schema

The contract between the Codex Orchestrator/subagent planning workflow
(producer) and `render_planboard.py` (consumer). Both sides assume this shape;
keep them in sync.

```jsonc
{
  "task": "string — the thing being planned, verbatim",
  "round": 1,                       // int, increments each revision round

  "headline": "string — ONE sentence, the whole plan grasped in a breath",
  "approach_summary": "string — <= 3 sentences of the essential reasoning",

  "steps": [                        // ordered; ids are STABLE across rounds
    {
      "id": "step-1",               // required, stable; never renumber survivors
      "title": "string",            // required, short imperative
      "summary": "string",          // one line (<= ~90 chars) — the scannable essence
      "what": "string",             // required, the full detail
      "why": "string",              // optional, short
      "files": ["path/a.py"],       // optional, files created/edited
      "commands": ["pytest -q"],    // optional, shell to run
      "risk": "string",             // optional → renders a 风险 tag + detail row
      "verification": "string",     // required, how to confirm this step worked
      "depends_on": ["step-1"]      // optional, step ids
    }
  ],

  "deferred": ["string"],           // one-liners: secondary / cut / gated items
  "open_questions": ["string"],     // <= 3; need the operator, or found while implementing
  "alternatives_considered": [      // <= 3
    { "approach": "string", "why_not": "string" }
  ]
}
```

## The scannable / detail split (why `headline` + `summary` exist)

The HTML is interaction-first, so it renders in two layers:

- **Always visible (scan layer):** `headline`, and each step's `title` + `summary`
  + `files` + the 采纳/改/砍 control. The operator grasps the whole plan without
  reading prose. This layer must be specific enough to choose a verdict without
  opening details; avoid generic labels such as "update docs" or "implement
  changes".
- **Collapsed (context layer):** `approach_summary` (整体思路), and each step's
  `what` / `why` / `commands` / `verification` / `risk` / `depends_on` (详情).
  Available on demand, never dumped.

The final format pass populates `headline`, per-step `summary`, and tightened
`what` text. If a plan is authored by hand without them, the renderer degrades
gracefully: missing `summary` → a clipped `what`; missing `headline` → the first
sentence of `approach_summary`.

## Invariants

- `required` per step: `id`, `title`, `what`, `verification`. `summary` is added
  by the Format phase; everything else is optional and omitted from the render
  when absent.
- Stable `id`s are load-bearing: the HTML keys per-step annotations by `id`, and
  revision rounds match 采纳/改/砍 verdicts back to steps by `id`.
- The renderer escapes all text fields; `commands` render in a `<pre>`, `files`
  and `depends_on` render as inline `<code>` chips.
- Distillation budget: at most six main steps. Anything past that, or cut by
  verification, goes to `deferred` (a one-line tail), never a step.
