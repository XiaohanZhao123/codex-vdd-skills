---
name: wrap
description: End-of-session documentation reconcile. Runs the Curator to propose a short ADD/RETIRE/PROMOTE list, waits for the human to accept or reject, then runs the Librarian to apply only the survivors. Invoke as /wrap when finishing a working session. User-invoked; never auto-run.
---

# /wrap — reconcile the docs before you stop

A working session adds knowledge and outdates some of what's written; `/wrap` closes that loop while it's fresh. Two sub-agents run in order with your judgment between them — the Curator proposes, you accept or reject, the Librarian applies. Nothing touches a doc without your accept. Run it from the repo root at the end of a session.

## Sub-agent contract
`/wrap` is a sub-agent workflow. The main agent must keep transcript scanning,
doc archaeology, and doc editing out of its own context.

Use the project custom agents:
- `wrap-curator` for proposal work.
- `wrap-librarian` for accepted-item application.

If Codex cannot spawn those custom agents, stop and report the blocker. Do not
inline the Curator or Librarian work in the main agent as a fallback.

## 1 · Curator proposes
Dispatch ONE `wrap-curator` sub-agent. Its custom agent config owns the detailed
Curator manual. It reads this session's transcript and the docs and returns a
short list in three moves:
- **ADD** — what you flagged out loud (it greps your own turns for the trigger phrases).
- **RETIRE** — what the repo outgrew (doc lines citing git-deleted paths, via `scan_dead_refs.py`).
- **PROMOTE** — a prose rule that earned a hook/lint, or a code-structure flag.

Show its list back **verbatim, numbered, grouped by move** — one line per action. Apply nothing yet. This list spends the scarce thing here, your attention, so pass it on as short as the Curator made it; don't pad it with your own inferred extras.

## 2 · You accept or reject
Wait for the human. They reply by number — `1,3`, `all`, `none`, or a tweak (`2 but file it under docs/foo.md`). Don't infer past what they said: a line they didn't accept is dropped, and silence on a line means drop it. Sparse beats wrong — most of all for RETIRE, where a wrong cut costs more than a missed one.

## 3 · Librarian applies the survivors
Dispatch ONE `wrap-librarian` sub-agent, handing it **only the accepted items**.
Its custom agent config owns the detailed Librarian manual. It relocates prose
into the doc that owns the topic, keeps `docs/README.md` and
`.codex/hooks/doc-map.json` in sync, runs the bundled `add_doc_link.py` /
`add_lint.py` for any accepted wiring, and flags any code-structure promotion
for you to build deliberately. It relocates and wires; it never drops unique
information.

Close with one short summary of what landed — and, if the Curator flagged a code-structure promotion, say it's waiting on you.

## Order is fixed
Curator → human → Librarian, every time. The Librarian runs last so the session ends tidy, and each next `/wrap`'s Curator inherits clean ground. If the human accepts nothing, say so and stop — an empty wrap is a fine wrap.
