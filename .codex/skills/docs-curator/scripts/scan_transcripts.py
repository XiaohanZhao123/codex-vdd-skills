#!/usr/bin/env python3
"""Scan session transcripts for the Curator's trigger phrases — HUMAN turns only,
each with the human turn before and after for context. Lets the Curator work from
a short candidate list instead of the whole .jsonl, and skips the agent's own
self-narration (which uses the same phrases but isn't a flag).

    python scan_transcripts.py <triggers.txt> <transcript.jsonl> [more.jsonl ...]

Reads only `type:"user"` text turns and greps them for the non-comment phrases in
triggers.txt, printing each match with the human turns immediately before and after.
Machine-authored user-role turns (tool-results, compact-continuation summaries,
slash-command echoes, caveats) are dropped before grepping — their boilerplate
otherwise matches the phrases. Stdlib only (runs under whatever python3 a hook uses).
"""

import json
import re
import sys
import pathlib

# Substrings that mark a type:"user" turn as MACHINE-authored, not human typing.
# The harness wears the user role for tool-results, compact-continuation summaries,
# slash-command echoes, and caveats — their boilerplate vocabulary ("replaced by",
# "instead of", ...) otherwise pollutes the phrase scan. Verified on real
# transcripts: 27% of user turns carry one of these, and they accounted for the
# majority of retire-phrase false hits (and one ADD false hit).
_MACHINE_MARKERS = (
    "<task-notification>",
    "<local-command-caveat>",
    "<command-name>",
    "<command-message>",
    "<command-args>",
    "<user_action>",
)
_MACHINE_PREFIXES = (
    "Base directory for this skill:",
    "This session is being continued",
    "Caveat: The messages below were generated",
    "# AGENTS.md instructions for ",
)
_SYSTEM_REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)


def load_triggers(path):
    out = []
    for line in pathlib.Path(path).read_text().splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            out.append(s.lower())
    return out


def _content_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") in {"text", "input_text"}
        )
    return None


def human_text(obj):
    """The human's typed text for a user turn, else None.

    Skips tool-results (non-user role) AND machine-authored user-role turns
    (task-notifications, compact summaries, slash-command echoes, caveats), then
    strips injected <system-reminder> spans so a real human turn keeps its own text.
    """
    # Claude transcript shape.
    if obj.get("type") == "user":
        msg = obj.get("message") or {}
        if msg.get("role") not in (None, "user"):
            return None
        text = _content_text(msg.get("content"))
    # Codex response item shape: {"type":"response_item","payload":{"type":"message", ...}}.
    elif obj.get("type") == "response_item":
        msg = obj.get("payload") or {}
        if msg.get("type") != "message" or msg.get("role") != "user":
            return None
        text = _content_text(msg.get("content"))
    # Codex event stream shape: {"type":"event_msg","payload":{"type":"user_message", ...}}.
    elif obj.get("type") == "event_msg":
        payload = obj.get("payload") or {}
        if payload.get("type") != "user_message":
            return None
        text = payload.get("message")
    else:
        return None

    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    if any(m in text for m in _MACHINE_MARKERS):
        return None
    if any(text.startswith(p) for p in _MACHINE_PREFIXES):
        return None
    text = _SYSTEM_REMINDER.sub("", text).strip()
    return text or None


def is_subagent_transcript(path: pathlib.Path) -> bool:
    """True when Codex metadata marks the transcript as a subagent thread."""
    try:
        for line in path.read_text(errors="replace").splitlines()[:50]:
            s = line.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
            except Exception:
                continue
            if obj.get("type") != "session_meta":
                continue
            payload = obj.get("payload") or {}
            source = payload.get("source") or {}
            return (
                payload.get("thread_source") == "subagent"
                or bool(source.get("subagent"))
            )
    except Exception:
        return False
    return False


def main(argv):
    if len(argv) < 2:
        print(
            "usage: scan_transcripts.py <triggers.txt> <transcript.jsonl> [more.jsonl ...]",
            file=sys.stderr,
        )
        return 2
    triggers = load_triggers(argv[0])
    for tf in argv[1:]:
        path = pathlib.Path(tf)
        if "subagents" in path.parts or is_subagent_transcript(path):
            continue
        turns = []
        for line in path.read_text(errors="replace").splitlines():
            s = line.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
            except Exception:
                continue
            t = human_text(obj)
            if t is not None:
                if turns and turns[-1] == t:
                    continue
                turns.append(t)
        name = path.name
        for i, text in enumerate(turns):
            lower_text = text.lower()
            hit = next((p for p in triggers if p in lower_text), None)
            if not hit:
                continue
            print(f"=== {name}  human-turn {i}  matched: {hit!r} ===")
            if i > 0:
                print(f"[before] {turns[i - 1][:400]}")
            print(f">>> {text[:800]}")
            if i + 1 < len(turns):
                print(f"[after]  {turns[i + 1][:400]}")
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
