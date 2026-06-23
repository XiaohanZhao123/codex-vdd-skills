# Codex Workflow Skills

Reusable Codex skills for two high-leverage repo workflows:

- **Planboard**: turns a complex implementation request into a browser-reviewable plan with accept/edit/reject annotations.
- **Wrap**: closes a work session by proposing documentation updates, waiting for human acceptance, then applying only accepted items.

The repository is intentionally small. It contains only Codex skill folders, custom agent role files, and thin helper scripts.

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
primary agent instruction file to the installed planboard and wrap skills.
Preserve existing content; relocate or link it instead of deleting it.
```

Review the diff before committing. This is a one-time setup step; normal session
wraps should still use the Curator -> human acceptance -> Librarian flow below.

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
