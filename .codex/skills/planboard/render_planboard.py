#!/usr/bin/env python3
"""planboard renderer: L1 acceptance-spec JSON -> annotatable review HTML.

Durable infrastructure for the `planboard` skill (NOT one-shot). The page is
review-first: every requirement keeps a one-line scannable head (requirement +
gate + strength badge), with the full brief, examples, and mutants under 详情.
A coverage header at the top says whether the spec is trustworthy at a glance.

The core unit is a `requirement` fused to its acceptance `gate`; decisions carry an
A/B/C radio; scopes are a read-only grouping band. A legacy `steps[]` plan still
renders through a thin back-compat path.

Usage:
    python3 render_planboard.py <spec.json> <out.html> [--slug SLUG]

stdlib only.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import html
import json
import os
import re
import sys

VERDICT_LABEL = {"strong": "强", "weak": "暂定", "open": "易空转"}
VERDICT_CLS = {"strong": "badge-strong", "weak": "badge-weak", "open": "badge-open"}


def esc(x) -> str:
    return html.escape("" if x is None else str(x))


def js_json(value) -> str:
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c")


def fill_template(template: str, values: dict) -> str:
    pattern = re.compile("|".join(re.escape(k) for k in sorted(values, key=len, reverse=True)))
    return pattern.sub(lambda match: values[match.group(0)], template)


def slugify(text: str) -> str:
    raw = text or "plan"
    text = raw.strip().lower()
    if not text:
        return "plan"
    text = re.sub(r"[^a-z0-9一-鿿]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    ascii_only = re.sub(r"[^a-z0-9-]+", "", text).strip("-")
    if ascii_only:
        return ascii_only[:48]
    return "plan-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def first_sentence(text: str, cap: int = 160) -> str:
    text = (text or "").strip()
    parts = re.split(r"(?<=[。.!?！？])\s*", text, maxsplit=1)
    head = parts[0] if parts else text
    if len(head) > cap:
        head = head[: cap - 1].rstrip() + "…"
    return head


def chips(items, cls) -> str:
    items = [i for i in (items or []) if str(i).strip()]
    if not items:
        return ""
    return "".join(f'<code class="{cls}">{esc(i)}</code> ' for i in items)


def verdict_badge(verdict: str) -> str:
    v = verdict or "open"
    if v not in VERDICT_LABEL:
        v = "open"
    return f'<span class="vbadge {VERDICT_CLS[v]}">{VERDICT_LABEL[v]}</span>'


def gate_oneline(gate: dict) -> str:
    gate = gate or {}
    sot = (gate.get("source_of_truth") or "").strip()
    sig = (gate.get("signal") or "").strip()
    if sot or sig:
        return " · ".join(x for x in (sot, sig) if x)
    return (gate.get("criterion") or "").strip()


def unit_anchor_id(uid: str) -> str:
    return "pb-" + slugify(uid or "unit")


def validate_unit_ids(plan: dict) -> None:
    """Reject ids that would corrupt annotations or revision anchors."""
    if not plan.get("requirements") and plan.get("steps"):
        groups = (("step", plan.get("steps") or [], None),)
    else:
        groups = (
            ("requirement", plan.get("requirements") or [], "req-"),
            ("decision", plan.get("decisions") or [], "dec-"),
            ("scope", plan.get("scopes") or [], "scope-"),
        )

    raw_seen = {}
    anchor_seen = {}
    errors = []
    for kind, units, prefix in groups:
        for index, unit in enumerate(units, start=1):
            if not isinstance(unit, dict):
                errors.append(f"{kind}[{index}] must be an object")
                continue
            uid = str(unit.get("id") or "").strip()
            if not uid:
                errors.append(f"{kind}[{index}] is missing id")
                continue
            if prefix and not uid.startswith(prefix):
                errors.append(f"{kind} id {uid!r} must start with {prefix!r}")
            if uid in raw_seen:
                errors.append(f"duplicate id {uid!r} ({raw_seen[uid]} and {kind})")
            else:
                raw_seen[uid] = kind
            anchor = unit_anchor_id(uid)
            if anchor in anchor_seen and anchor_seen[anchor] != uid:
                errors.append(
                    f"ids {anchor_seen[anchor]!r} and {uid!r} share anchor {anchor!r}"
                )
            else:
                anchor_seen[anchor] = uid
    if errors:
        raise ValueError("; ".join(errors))


def effective_gate_verdict(req: dict) -> str:
    """Return an earned verdict; never trust a hand-written `strong` alone."""
    gs = req.get("gate_strength") or {}
    declared = gs.get("verdict") or "open"
    if declared not in VERDICT_LABEL:
        declared = "open"

    gate = req.get("gate") or {}
    required = (
        "criterion",
        "failure_class",
        "source_of_truth",
        "input_form",
        "signal",
        "failure_response",
        "verifier_form",
        "lifecycle",
    )
    if any(not str(gate.get(key) or "").strip() for key in required):
        return "open"
    if gate.get("verifier_form") not in {
        "code",
        "script",
        "data-check",
        "preview",
        "subagent",
        "human",
    }:
        return "open"
    if gate.get("lifecycle") not in {"one-shot", "reusable", "wrap-decides"}:
        return "open"

    mutants = gs.get("mutants") or []
    if not mutants:
        return "open"
    if any(
        not isinstance(m, dict)
        or not str(m.get("mutant") or "").strip()
        or m.get("caught_by_gate") is not True
        for m in mutants
    ):
        return "weak"
    coverage = req.get("coverage")
    if coverage == "gap":
        return "weak"
    if coverage != "covered":
        return "open"
    return declared


def normalise_revision_changes(items) -> list[dict]:
    out = []
    for raw in (items or []):
        if not raw:
            continue
        if isinstance(raw, dict):
            uid = raw.get("unit_id") or raw.get("step_id") or raw.get("id") or ""
            status = raw.get("status") or raw.get("verdict") or ""
            change = raw.get("change") or raw.get("summary") or raw.get("note") or ""
        else:
            uid, status, change = "", "", str(raw)
        if not str(change).strip():
            continue
        out.append(
            {
                "unit_id": str(uid).strip(),
                "status": str(status).strip(),
                "change": str(change).strip(),
            }
        )
    return out


def render_seg(kind: str) -> str:
    return (
        '<div class="seg" role="group" aria-label="处置">'
        '<button type="button" data-v="accept">✓ 采纳</button>'
        '<button type="button" data-v="edit">✎ 改</button>'
        '<button type="button" data-v="reject">✗ 砍</button></div>'
    )


def examples_html(examples) -> str:
    rows = []
    for ex in examples or []:
        if not isinstance(ex, dict):
            continue
        kind = (ex.get("kind") or "").strip()
        tag = f'<span class="exk">{esc(kind)}</span>' if kind else ""
        g, w, t = ex.get("given"), ex.get("when"), ex.get("then")
        parts = []
        if g:
            parts.append(f'<span class="gw">Given</span> {esc(g)}')
        if w:
            parts.append(f'<span class="gw">When</span> {esc(w)}')
        if t:
            parts.append(f'<span class="gw">Then</span> {esc(t)}')
        rows.append(f'<div class="ex">{tag}{"<br>".join(parts)}</div>')
    return "".join(rows)


def gate_brief_html(gate: dict) -> str:
    gate = gate or {}
    order = [
        ("criterion", "判据"), ("failure_class", "抓的失败"),
        ("source_of_truth", "事实来源"), ("input_form", "输入/fixture"),
        ("signal", "通过信号"), ("failure_response", "失败处理"),
        ("verifier_form", "verifier"),
        ("lifecycle", "生命周期"), ("reuse", "可复用"),
    ]
    rows = []
    for key, label in order:
        val = gate.get(key)
        if val is None or str(val).strip() == "":
            continue
        rows.append(f'<div class="grow"><span class="gk">{label}</span><span class="gv">{esc(val)}</span></div>')
    return f'<div class="gate">{"".join(rows)}</div>' if rows else ""


def mutants_html(gate_strength: dict) -> str:
    gs = gate_strength or {}
    muts = gs.get("mutants") or []
    smells = [s for s in (gs.get("smells") or []) if str(s).strip()]
    out = []
    for m in muts:
        if not isinstance(m, dict):
            continue
        caught = m.get("caught_by_gate")
        mark = '<span class="mok">拦住</span>' if caught else '<span class="mbad">存活</span>'
        hard = m.get("hardening")
        hh = f' — 加固：{esc(hard)}' if hard and not caught else ""
        out.append(f'<div class="mut-row">{mark} {esc(m.get("mutant",""))}{hh}</div>')
    body = "".join(out)
    if smells:
        body += f'<div class="smell">smells：{chips(smells, "schip")}</div>'
    return body


def render_requirement(req: dict, idx: int, revision: dict = None) -> str:
    rid_text = str(req.get("id") or f"req-{idx + 1}")
    rid = esc(rid_text)
    anchor = esc(unit_anchor_id(rid_text))
    requirement = esc(req.get("requirement") or req.get("title") or "")
    why = req.get("why")
    gate = req.get("gate") or {}
    gs = req.get("gate_strength") or {}
    verdict = effective_gate_verdict(req)
    coverage = req.get("coverage")
    one = esc(gate_oneline(gate)) or "<span class=\"mut\">（gate 待补）</span>"

    unit_class = "unit req"
    rev_badge = ""
    rev_note = ""
    if revision:
        unit_class += " changed-unit"
        status = revision.get("status") or "改动"
        change = revision.get("change") or ""
        rev_badge = f'<span class="unitrevtag">本轮 {esc(status)}</span>'
        if change:
            rev_note = f'<div class="unitchange"><span>本轮改动</span><div>{esc(change)}</div></div>'

    drows = []
    if why:
        drows.append(f'<div class="drow"><span class="k">为什么</span><div class="v">{esc(why)}</div></div>')
    exh = examples_html(req.get("examples"))
    if exh:
        drows.append(f'<div class="drow"><span class="k">例子</span><div class="v">{exh}</div></div>')
    gbh = gate_brief_html(gate)
    if gbh:
        drows.append(f'<div class="drow"><span class="k vk">验收门</span><div class="v">{gbh}</div></div>')
    mh = mutants_html(gs)
    if mh:
        drows.append(f'<div class="drow"><span class="k rk">对抗</span><div class="v">{mh}</div></div>')
    if coverage:
        cov = "已覆盖" if coverage == "covered" else "缺口"
        drows.append(f'<div class="drow"><span class="k">覆盖</span><div class="v">{esc(cov)}</div></div>')
    detail = ""
    if drows:
        detail = f'<details class="detail"><summary>详情</summary><div class="dbody">{"".join(drows)}</div></details>'

    return f"""    <div class="{unit_class}" id="{anchor}" data-id="{rid}" data-kind="req" data-verdict="{esc(verdict)}">
      <div class="uline"><span class="uid">{rid}</span><h4>{requirement}</h4>{verdict_badge(verdict)}{rev_badge}</div>
      <p class="gline"><span class="glbl">gate</span> {one}</p>
      {rev_note}
      {render_seg("req")}
      {detail}
      <textarea data-note placeholder="批注（改成什么 / 为什么砍 / gate 太弱 / 补要求）…"></textarea>
    </div>"""


def render_step_legacy(step: dict, idx: int, revision: dict = None) -> str:
    """Back-compat: a legacy steps[] plan renders as a requirement-like unit."""
    sid_text = str(step.get("id") or f"step-{idx + 1}")
    sid = esc(sid_text)
    anchor = esc(unit_anchor_id(sid_text))
    title = esc(step.get("title") or "")
    summary = (step.get("summary") or step.get("what") or "").strip()
    if len(summary) > 140:
        summary = summary[:138].rstrip() + "…"
    drows = []
    for key, label, cls in [("what", "做什么", ""), ("why", "为什么", ""),
                            ("verification", "验证", "vk"), ("risk", "风险", "rk")]:
        val = step.get(key)
        if val:
            drows.append(f'<div class="drow"><span class="k {cls}">{label}</span><div class="v">{esc(val)}</div></div>')
    files = chips(step.get("files"), "fchip")
    if files:
        drows.append(f'<div class="drow"><span class="k">文件</span><div class="v">{files}</div></div>')
    dependencies = chips(step.get("depends_on"), "dchip")
    if dependencies:
        drows.append(f'<div class="drow"><span class="k">依赖</span><div class="v">{dependencies}</div></div>')
    commands = step.get("commands") or []
    if isinstance(commands, str):
        commands = [commands]
    commands = [str(command) for command in commands if str(command).strip()]
    if commands:
        drows.append(
            '<div class="drow"><span class="k vk">命令</span>'
            f'<div class="v"><pre class="legacy-cmds">{esc(chr(10).join(commands))}</pre></div></div>'
        )
    detail = f'<details class="detail"><summary>详情</summary><div class="dbody">{"".join(drows)}</div></details>' if drows else ""
    unit_class = "unit req changed-unit" if revision else "unit req"
    rev_badge = ""
    rev_note = ""
    if revision:
        status = revision.get("status") or "改动"
        change = revision.get("change") or ""
        rev_badge = f'<span class="unitrevtag">本轮 {esc(status)}</span>'
        if change:
            rev_note = f'<div class="unitchange"><span>本轮改动</span><div>{esc(change)}</div></div>'
    return f"""    <div class="{unit_class}" id="{anchor}" data-id="{sid}" data-kind="req" data-verdict="open">
      <div class="uline"><span class="uid">{sid}</span><h4>{title}</h4>{rev_badge}</div>
      <p class="gline">{esc(summary)}</p>
      {rev_note}
      {render_seg("req")}
      {detail}
      <textarea data-note placeholder="批注…"></textarea>
    </div>"""


def render_decision(dec: dict, idx: int, revision: dict = None) -> str:
    did_text = str(dec.get("id") or f"dec-{idx + 1}")
    did = esc(did_text)
    anchor = esc(unit_anchor_id(did_text))
    decision = esc(dec.get("decision") or "")
    status = (dec.get("status") or "").strip()
    rec = str(dec.get("recommendation") or "").strip()
    options = dec.get("options") or []
    status_badge = f'<span class="vbadge badge-open">{esc(status)}</span>' if status else ""

    radios = []
    opt_detail = []
    for o in options:
        if not isinstance(o, dict):
            continue
        lab = str(o.get("label") or "").strip()
        if not lab:
            continue
        checked = "checked" if lab == rec else ""
        rec_mark = ' <span class="recmark">推荐</span>' if lab == rec else ""
        radios.append(
            f'<label class="ropt"><input type="radio" name="{did}" value="{esc(lab)}" {checked}>'
            f'<b>{esc(lab)}</b>{rec_mark}</label>'
        )
        shape = esc(o.get("shape") or "")
        impl = o.get("implication")
        impl_h = f' <span class="mut">→ {esc(impl)}</span>' if impl else ""
        opt_detail.append(f'<div class="opt"><b>{esc(lab)}</b> {shape}{impl_h}</div>')

    drows = []
    if dec.get("reason"):
        drows.append(f'<div class="drow"><span class="k">推荐理由</span><div class="v">{esc(dec.get("reason"))}</div></div>')
    if opt_detail:
        drows.append(f'<div class="drow"><span class="k">选项</span><div class="v">{"".join(opt_detail)}</div></div>')
    affects = [a for a in (dec.get("affects") or []) if str(a).strip()]
    if affects:
        drows.append(f'<div class="drow"><span class="k">影响</span><div class="v">{chips(affects, "dchip")}</div></div>')
    detail = ""
    if drows:
        detail = f'<details class="detail"><summary>详情</summary><div class="dbody">{"".join(drows)}</div></details>'

    unit_class = "unit dec changed-unit" if revision else "unit dec"
    rev_badge = ""
    if revision:
        rev_badge = f'<span class="unitrevtag">本轮 {esc(revision.get("status") or "改动")}</span>'
    return f"""    <div class="{unit_class}" id="{anchor}" data-id="{did}" data-kind="dec">
      <div class="uline"><span class="uid">{did}</span><h4>{decision}</h4>{status_badge}{rev_badge}</div>
      <div class="radios">{"".join(radios)}</div>
      {detail}
      <textarea data-note placeholder="批注（选哪个 / 都不选、想怎么改 / 补充约束）…"></textarea>
    </div>"""


def render_scope(scope: dict, reqs_html: str, revision: dict = None) -> str:
    sid_text = str(scope.get("id") or "scope")
    anchor = esc(unit_anchor_id(sid_text))
    name = esc(scope.get("name") or scope.get("id") or "")
    outcome = esc(scope.get("outcome") or "")
    appetite = (scope.get("appetite") or "").strip()
    ap = f'<span class="appetite">{esc(appetite)}</span>' if appetite else ""
    rabbit = [r for r in (scope.get("rabbit_holes") or []) if str(r).strip()]
    rh = f'<div class="rabbit">避坑：{chips(rabbit, "rchip")}</div>' if rabbit else ""
    scope_class = "scope changed-scope" if revision else "scope"
    rev_badge = ""
    if revision:
        rev_badge = f'<span class="unitrevtag">本轮 {esc(revision.get("status") or "改动")}</span>'
    return f"""  <div class="{scope_class}" id="{anchor}">
    <div class="scope-head"><span class="scope-tag">scope</span><h3>{name}</h3>{rev_badge}{ap}</div>
    <p class="scope-outcome">{outcome}</p>
    {rh}
    <div class="scope-reqs">{reqs_html}</div>
  </div>"""


def render_coverage(plan: dict) -> str:
    reqs = plan.get("requirements") or []
    if not reqs:
        return ""
    total = len(reqs)
    strong = sum(1 for r in reqs if effective_gate_verdict(r) == "strong")
    weakopen = total - strong
    raw_uncovered = plan.get("uncovered_failure_modes")
    coverage_recorded = isinstance(raw_uncovered, list)
    uncovered = [u for u in (raw_uncovered or []) if str(u).strip()] if coverage_recorded else []
    clean = weakopen == 0 and not uncovered and coverage_recorded
    cls = "cov-ok" if clean else "cov-warn"
    unc = ""
    if not coverage_recorded:
        unc = (
            '<div class="cov-unc"><span class="lbl">'
            '缺少 P5 覆盖检查结果；当前规格还不能批准。'
            "</span></div>"
        )
    elif uncovered:
        lis = "".join(f"<li>{esc(u)}</li>" for u in uncovered)
        unc = f'<div class="cov-unc"><span class="lbl">没有 gate 的失败模式（出货前必须清零或解释）</span><ul>{lis}</ul></div>'
    return f"""  <div class="coverage {cls}">
    <div class="cov-nums">
      <span class="cov-metric"><b>{total}</b> 要求</span>
      <span class="cov-metric ok"><b>{strong}</b> 强 gate</span>
      <span class="cov-metric warn"><b>{weakopen}</b> 弱/待补</span>
      <span class="cov-metric bad"><b>{len(uncovered)}</b> 失败模式无 gate</span>
    </div>
    {unc}
  </div>"""


def render_non_goals(items) -> str:
    items = [i for i in (items or []) if str(i).strip()]
    if not items:
        return ""
    lis = "".join(f"<li>{esc(i)}</li>" for i in items)
    return f"""  <details>
    <summary>明确不做 / non-goals（{len(items)}）</summary>
    <div class="body"><ul class="tight">{lis}</ul></div>
  </details>"""


def render_legacy_alternatives(items) -> str:
    rows = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        approach = item.get("approach") or ""
        reason = item.get("why_not") or ""
        if not str(approach).strip() and not str(reason).strip():
            continue
        rows.append(
            f'<div class="opt"><b>{esc(approach)}</b>'
            f'<div class="mut">不选的原因：{esc(reason)}</div></div>'
        )
    if not rows:
        return ""
    return f"""  <details>
    <summary>考虑过但没选的方案（{len(rows)}）</summary>
    <div class="body">{"".join(rows)}</div>
  </details>"""


def render_questions(qs) -> str:
    qs = [q for q in (qs or []) if str(q).strip()]
    if not qs:
        return ""
    lis = "".join(f'<li><span class="qtext">{esc(q)}</span></li>' for q in qs)
    return f"""  <div class="qbox">
    <div class="lbl">开放问题（建造期才知道的未知）</div>
    <ol>{lis}</ol>
  </div>"""


def render_revision_changes(items, linkable_ids=None) -> str:
    items = normalise_revision_changes(items)
    linkable_ids = set(linkable_ids or [])
    if not items:
        return ""
    cards = []
    for raw in items:
        uid = raw.get("unit_id") or ""
        status = raw.get("status") or ""
        change = raw.get("change") or ""
        head = ""
        if uid and uid in linkable_ids:
            head += f'<a class="revlink" href="#{esc(unit_anchor_id(uid))}"><code class="dchip">{esc(uid)}</code></a>'
        elif uid:
            head += f'<code class="dchip">{esc(uid)}</code>'
        if status:
            head += f'<span class="revtag">{esc(status)}</span>'
        cards.append(
            f'<div class="revitem"><div class="revhead">{head}</div>'
            f'<div class="revtext">{esc(change)}</div></div>'
        )
    return f"""  <div class="revbox">
    <div class="lbl">本轮改动（打开页面先看这里）</div>
    <div class="revgrid">{"".join(cards)}</div>
  </div>"""


def render_units(plan: dict, revision_by_unit: dict = None) -> str:
    """Requirements grouped by scope; then decisions. Legacy steps[] fall back."""
    revision_by_unit = revision_by_unit or {}
    reqs = plan.get("requirements")
    if not reqs and plan.get("steps"):
        steps = plan.get("steps") or []
        return "\n".join(
            render_step_legacy(
                s,
                i,
                revision_by_unit.get(str(s.get("id") or f"step-{i + 1}")),
            )
            for i, s in enumerate(steps)
        )

    reqs = reqs or []
    by_scope = {}
    for i, r in enumerate(reqs):
        by_scope.setdefault(r.get("scope_id") or "", []).append((i, r))

    blocks = []
    scopes = plan.get("scopes") or []
    seen = set()
    for scope in scopes:
        sid = scope.get("id") or ""
        members = by_scope.get(sid, [])
        seen.add(sid)
        rh = "\n".join(
            render_requirement(r, i, revision_by_unit.get(str(r.get("id") or f"req-{i + 1}")))
            for i, r in members
        )
        blocks.append(render_scope(scope, rh, revision_by_unit.get(str(sid))))
    # requirements whose scope has no scope card (or no scope_id)
    leftover = []
    for sid, members in by_scope.items():
        if sid in seen:
            continue
        leftover.extend(members)
    if leftover:
        rh = "\n".join(
            render_requirement(r, i, revision_by_unit.get(str(r.get("id") or f"req-{i + 1}")))
            for i, r in leftover
        )
        if scopes:
            blocks.append(f'<div class="scope-reqs ungrouped">{rh}</div>')
        else:
            blocks.append(rh)

    decisions = plan.get("decisions") or []
    if decisions:
        dh = "\n".join(
            render_decision(d, i, revision_by_unit.get(str(d.get("id") or f"dec-{i + 1}")))
            for i, d in enumerate(decisions)
        )
        blocks.append(f'<div class="declist"><div class="lbl declbl">决策（选一个 / 或在批注里说清）</div>{dh}</div>')
    return "\n".join(blocks)


def build_html(plan: dict, slug: str) -> str:
    task = plan.get("task") or ""
    rnd = int(plan.get("round") or 1)
    headline = (plan.get("headline") or "").strip()
    intent = (plan.get("intent") or plan.get("approach_summary") or "").strip()
    if not headline:
        headline = first_sentence(intent) or "（无 headline）"
    intent_block = ""
    if intent and intent != headline:
        intent_block = (
            '<details class="detail"><summary>意图 / GQM goal</summary>'
            f'<div class="dbody"><div class="v">{esc(intent)}</div></div></details>'
        )

    date = datetime.date.today().isoformat()
    lskey = f"planboard_{slug}_r{rnd}"
    revision_changes = normalise_revision_changes(plan.get("changes_from_previous_round"))
    revision_by_unit = {
        item["unit_id"]: item for item in revision_changes if item.get("unit_id")
    }
    if not plan.get("requirements") and plan.get("steps"):
        linkable_ids = {
            str(unit.get("id"))
            for unit in (plan.get("steps") or [])
            if isinstance(unit, dict) and unit.get("id")
        }
    else:
        linkable_ids = {
            str(unit.get("id"))
            for key in ("requirements", "decisions", "scopes")
            for unit in (plan.get(key) or [])
            if isinstance(unit, dict) and unit.get("id")
        }

    tmpl = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>planboard · __TASK_T__ · round __ROUND__</title>
<style>
  :root{
    --bg:#0e1117; --panel:#171c25; --card:#1c2330; --ink:#eef2f8; --mut:#aab4c3;
    --line:#303846; --softline:#26303d; --acc:#74b7ff; --acc2:#b89cff; --good:#58d6b4; --warn:#e9bf63; --bad:#ec8179;
  }
  *{box-sizing:border-box}
  html{scroll-behavior:smooth}
  html{scroll-behavior:smooth}
  body{margin:0;background:var(--bg);color:var(--ink);
    font:17px/1.72 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;}
  .wrap{max-width:1160px;margin:0 auto;padding:42px 34px 110px}
  h1{font-size:30px;margin:0 0 6px;font-weight:780}
  .sub{color:var(--mut);margin:0 0 22px;font-size:15px}
  .lead{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--acc);
    border-radius:8px;padding:18px 22px;margin:8px 0 16px}
  .lead .headline{font-size:19px;color:var(--ink);line-height:1.62;font-weight:680}
  .lbl{font-size:13px;color:var(--mut);margin:0 0 8px;font-weight:760}
  .mut{color:var(--mut)}
  code{background:#0b0f15;border:1px solid var(--line);border-radius:5px;padding:2px 6px;font-size:13px;
    font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
  /* ---- coverage header ---- */
  .coverage{border:1px solid var(--line);border-radius:8px;padding:14px 20px;margin:0 0 20px;background:var(--panel)}
  .coverage.cov-ok{border-left:3px solid var(--good)}
  .coverage.cov-warn{border-left:3px solid var(--warn)}
  .cov-nums{display:flex;gap:22px;flex-wrap:wrap;font-size:14px;color:var(--mut)}
  .cov-metric b{font-size:20px;color:var(--ink);margin-right:4px}
  .cov-metric.ok b{color:var(--good)}.cov-metric.warn b{color:var(--warn)}.cov-metric.bad b{color:var(--bad)}
  .cov-unc{margin-top:12px;border-top:1px solid var(--softline);padding-top:10px}
  .cov-unc .lbl{color:var(--bad)}
  .cov-unc ul{margin:6px 0 0;padding-left:22px}.cov-unc li{color:#e4ebf4;margin:5px 0}
  /* ---- scope band (read-only) ---- */
  .scope{margin:22px 0 6px;scroll-margin-top:18px}
  .scope.changed-scope{border-left:3px solid var(--warn);padding-left:12px}
  .scope-head{display:flex;align-items:center;gap:10px}
  .scope-tag{font:760 11px/1 ui-monospace,Menlo,monospace;color:var(--acc);background:rgba(116,183,255,.12);
    border:1px solid rgba(116,183,255,.35);border-radius:999px;padding:5px 9px}
  .scope-head h3{margin:0;font-size:18px;font-weight:760}
  .appetite{margin-left:auto;font-size:12px;color:var(--mut);border:1px solid var(--line);border-radius:999px;padding:3px 9px}
  .scope-outcome{color:var(--mut);margin:4px 0 6px;font-size:15px}
  .rabbit{color:var(--mut);font-size:13px;margin:2px 0 4px}.rchip{color:var(--warn)}
  .scope-reqs{border-left:2px solid var(--softline);padding-left:14px;margin-left:4px}
  .scope-reqs.ungrouped{border-left:0;padding-left:0;margin-left:0}
  /* ---- unit card (requirement / decision) ---- */
  .unit{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:16px 18px;margin:14px 0;scroll-margin-top:18px}
  .unit.changed-unit{border-color:rgba(233,191,99,.68);box-shadow:0 0 0 1px rgba(233,191,99,.10)}
  .unit .uline{display:flex;align-items:center;gap:11px;flex-wrap:wrap}
  .unit .uid{font:760 12px/1 ui-monospace,Menlo,monospace;color:var(--acc2);
    background:rgba(184,156,255,.13);border:1px solid rgba(184,156,255,.36);border-radius:999px;padding:6px 10px;white-space:nowrap}
  .unit h4{margin:0;font-size:18px;flex:1;font-weight:740;color:var(--ink);min-width:200px}
  .gline{margin:11px 0 12px;font-size:15px;color:#d7dfeb;line-height:1.6}
  .gline .glbl{font:760 11px/1 ui-monospace,Menlo,monospace;color:var(--good);background:rgba(88,214,180,.12);
    border:1px solid rgba(88,214,180,.32);border-radius:5px;padding:3px 7px;margin-right:7px}
  .vbadge{font-size:12px;font-weight:760;border-radius:999px;padding:3px 10px;white-space:nowrap}
  .badge-strong{color:var(--good);background:rgba(88,214,180,.14);border:1px solid rgba(88,214,180,.4)}
  .badge-weak{color:var(--warn);background:rgba(233,191,99,.14);border:1px solid rgba(233,191,99,.42)}
  .badge-open{color:var(--mut);background:rgba(170,180,195,.1);border:1px solid var(--line)}
  .unitrevtag{font-size:12px;font-weight:780;color:var(--warn);border:1px solid rgba(233,191,99,.44);
    background:rgba(233,191,99,.13);border-radius:999px;padding:4px 9px;white-space:nowrap}
  .unitchange{display:grid;grid-template-columns:76px 1fr;gap:12px;align-items:start;
    background:rgba(233,191,99,.08);border:1px solid rgba(233,191,99,.25);border-radius:8px;
    padding:10px 12px;margin:10px 0 12px;color:#e9edf5;font-size:15px;line-height:1.58}
  .unitchange span{color:var(--warn);font-size:13px;font-weight:780;padding-top:1px}
  .seg{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden}
  .seg button{background:transparent;border:0;color:var(--mut);padding:9px 18px;font-size:15px;cursor:pointer;font-weight:720}
  .seg button+button{border-left:1px solid var(--line)}
  .seg button.on[data-v="accept"]{background:rgba(78,201,168,.18);color:var(--good)}
  .seg button.on[data-v="edit"]{background:rgba(226,182,92,.18);color:var(--warn)}
  .seg button.on[data-v="reject"]{background:rgba(227,118,111,.18);color:var(--bad)}
  /* ---- decision radios ---- */
  .radios{display:flex;gap:10px;flex-wrap:wrap;margin:4px 0 2px}
  .ropt{display:inline-flex;align-items:center;gap:7px;border:1px solid var(--line);border-radius:8px;
    padding:8px 13px;cursor:pointer;font-size:15px;color:#d7dfeb}
  .ropt input{accent-color:var(--acc)}
  .ropt b{color:var(--ink)}
  .recmark{font-size:11px;color:var(--good);border:1px solid rgba(88,214,180,.4);border-radius:999px;padding:1px 7px}
  .declist{margin-top:26px}.declbl{font-size:15px;color:var(--acc);margin-bottom:2px}
  textarea{width:100%;background:#0b0f15;border:1px solid var(--line);border-radius:8px;color:var(--ink);
    padding:11px 13px;font:15px/1.55 inherit;margin-top:12px;resize:vertical;min-height:44px}
  textarea:focus{outline:none;border-color:var(--acc)}
  /* ---- detail toggle ---- */
  details.detail{background:transparent;border:0;margin:12px 0 0}
  details.detail>summary{cursor:pointer;list-style:none;padding:8px 0;font-size:14px;color:var(--mut);font-weight:720}
  details.detail>summary::-webkit-details-marker{display:none}
  details.detail>summary::before{content:"\25b8 详情展开";color:var(--mut)}
  details.detail[open]>summary{font-size:0}
  details.detail[open]>summary::before{content:"\25be 收起";font-size:14px}
  details.detail .dbody{padding:10px 0 2px;border-top:1px solid var(--softline)}
  .drow{display:grid;grid-template-columns:76px 1fr;gap:14px;margin:10px 0;font-size:15px}
  .drow .k{color:var(--mut);font-weight:760;font-size:13px;padding-top:2px}
  .drow .k.vk{color:var(--good)}.drow .k.rk{color:var(--warn)}
  .drow .v{color:#d7dfeb;line-height:1.64;overflow-wrap:anywhere}
  .ex{margin:6px 0;padding:8px 11px;background:#0b0f15;border:1px solid var(--softline);border-radius:7px;font-size:14px}
  .ex .gw{color:var(--acc);font-weight:720;font-size:12px}
  .ex .exk{font-size:11px;color:var(--mut);border:1px solid var(--line);border-radius:999px;padding:1px 7px;margin-right:6px}
  .gate{display:flex;flex-direction:column;gap:5px}
  .grow{display:grid;grid-template-columns:88px 1fr;gap:10px;font-size:14px}
  .grow .gk{color:var(--mut);font-weight:720}.grow .gv{color:#d7dfeb;overflow-wrap:anywhere}
  .mut-row{margin:4px 0;font-size:14px;color:#d7dfeb}
  .mok{color:var(--good);font-weight:720;font-size:12px}.mbad{color:var(--bad);font-weight:720;font-size:12px}
  .smell{margin-top:6px;font-size:13px;color:var(--warn)}.schip{color:var(--warn)}
  .opt{background:#0b0f15;border:1px solid var(--softline);border-radius:7px;padding:9px 12px;margin:6px 0;font-size:14px}
  .dchip{color:var(--acc2)}.fchip{color:#cdd6e4}
  .legacy-cmds{margin:0;white-space:pre-wrap;color:#cdd6e4;font-size:13px;
    font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
  /* ---- tail sections ---- */
  details:not(.detail){background:var(--panel);border:1px solid var(--line);border-radius:8px;margin:18px 0;overflow:hidden}
  details:not(.detail)>summary{cursor:pointer;list-style:none;padding:15px 20px;font-weight:720;font-size:16px}
  details:not(.detail)>summary::-webkit-details-marker{display:none}
  details:not(.detail)>summary::before{content:"\25b8";color:var(--mut);margin-right:8px}
  details:not(.detail)[open]>summary::before{content:"\25be"}
  details:not(.detail) .body{padding:6px 20px 18px;border-top:1px solid var(--line)}
  ul.tight{margin:8px 0;padding-left:24px}ul.tight li{margin:8px 0;color:var(--mut)}
  .qbox{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--warn);border-radius:8px;padding:16px 20px;margin:18px 0}
  .qbox ol{margin:6px 0 0;padding-left:24px}.qbox li{margin:10px 0;color:var(--mut)}.qbox .qtext{color:#d7dfeb}
  .revbox{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--warn);border-radius:8px;padding:16px 20px;margin:18px 0}
  .revgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px}
  .revitem{background:var(--card);border:1px solid var(--softline);border-radius:8px;padding:12px 14px}
  .revhead{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:6px}
  .revlink{text-decoration:none}.revlink:hover code{border-color:var(--acc);color:var(--acc)}
  .revtag{font-size:12px;font-weight:760;color:var(--warn);border:1px solid rgba(233,191,99,.42);background:rgba(233,191,99,.12);border-radius:999px;padding:2px 8px}
  .revtext{font-size:15px;line-height:1.56;color:#e4ebf4}
  /* ---- sticky action bar ---- */
  .actions{position:sticky;bottom:0;background:linear-gradient(180deg,rgba(15,17,21,0),var(--bg) 36%);
    padding:22px 0 8px;margin-top:22px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;z-index:10}
  .btn{background:var(--acc);color:#08111f;border:0;border-radius:8px;padding:11px 20px;font-size:15px;font-weight:780;cursor:pointer}
  .btn:hover{filter:brightness(1.08)}
  .btn.ghost{background:transparent;color:var(--mut);border:1px solid var(--line)}
  .st{color:var(--good);font-size:14px;font-weight:720;opacity:0;transition:opacity .2s}
  .st.show{opacity:1}
  .counts{color:var(--mut);font-size:14px;margin-left:auto}
  pre.out{background:#0b0f15;border:1px solid var(--line);border-radius:8px;padding:14px;margin-top:13px;
    font-size:13px;white-space:pre-wrap;color:var(--mut);max-height:260px;overflow:auto}
  .foot{margin-top:24px;padding-top:15px;border-top:1px solid var(--line);color:var(--mut);font-size:13px}
  @media (max-width: 720px){
    body{font-size:16px}.wrap{padding:24px 16px 90px}h1{font-size:25px}
    .unit{padding:14px 13px}.drow,.grow{grid-template-columns:1fr;gap:4px}
    .seg{display:grid;grid-template-columns:repeat(3,1fr);width:100%}.seg button{padding:10px 6px}
    .cov-nums{gap:14px}.counts{width:100%;margin-left:0}
  }
</style>
</head>
<body>
<div class="wrap">
  <h1>planboard · round __ROUND__</h1>
  <p class="sub">__TASK__ · __DATE__ · 逐条 requirement / decision 处置后点「复制批注」粘回 chat，我据此修订出 round __NEXTROUND__</p>

  <div class="lead">
    <div class="headline">__HEADLINE__</div>
    __INTENT_BLOCK__
  </div>

__COVERAGE__

__CHANGES__

__UNITS__

__NONGOALS__

__QUESTIONS__

__LEGACY_ALTS__

  <div class="actions">
    <button class="btn" id="copyBtn">复制批注</button>
    <button class="btn ghost" id="dlBtn">下载</button>
    <button class="btn ghost" id="acceptAllBtn">全部采纳</button>
    <button class="btn ghost" id="clearBtn">清空草稿</button>
    <span class="st" id="stat">已复制 ✓</span>
    <span class="counts" id="counts"></span>
  </div>
  <pre class="out" id="preview" aria-live="polite"></pre>

  <div class="foot">planboard · L1 验收规格 · 渲染于 __DATE__ · gate 徽章：强 / 暂定 / 易空转 · 草稿自动存浏览器（刷新不丢）</div>
</div>

<script>
(function(){
  var KEY = "__LSKEY__";
  var TASK = __TASK_JSON__;
  var ROUND = __ROUND__;
  var VMAP = {accept:"采纳", edit:"改", reject:"砍"};
  var units = Array.prototype.slice.call(document.querySelectorAll(".unit[data-id]"));
  var preview = document.getElementById("preview");
  var stat = document.getElementById("stat");
  var counts = document.getElementById("counts");

  function choiceOf(u){ var c=u.querySelector('.radios input:checked'); return c?c.value:""; }
  function verdictOf(u){ var on=u.querySelector(".seg button.on"); return on?on.getAttribute("data-v"):""; }
  function noteOf(u){ var t=u.querySelector("textarea[data-note]"); return t?t.value:""; }

  function serialize(){
    var lines = ["# planboard 批注 · " + TASK + " · round " + ROUND, ""];
    units.forEach(function(u){
      var id=u.getAttribute("data-id"), kind=u.getAttribute("data-kind");
      var n=noteOf(u).trim(); var tail=n?"  ｜ "+n:"";
      if(kind==="dec"){
        var ch=choiceOf(u); lines.push("- ["+id+"] 选 "+(ch||"—未选—")+tail);
      } else {
        var v=verdictOf(u); lines.push("- ["+id+"] "+(v?VMAP[v]:"—未选—")+tail);
      }
    });
    lines.push(""); lines.push("全局备注: " + (gnote() || "（无）"));
    return lines.join("\n");
  }
  function gnote(){ var g=document.getElementById("globalNote"); return g?g.value.trim():""; }
  function tally(){
    var a=0,e=0,r=0,d=0,u2=0;
    units.forEach(function(u){
      var kind=u.getAttribute("data-kind");
      if(kind==="dec"){ if(choiceOf(u))d++; else u2++; }
      else { var v=verdictOf(u); if(v==="accept")a++;else if(v==="edit")e++;else if(v==="reject")r++;else u2++; }
    });
    counts.textContent="采纳 "+a+" · 改 "+e+" · 砍 "+r+" · 决策 "+d+" · 未选 "+u2;
  }
  function refresh(){ preview.textContent=serialize(); tally(); save(); }

  function save(){
    var data={g:gnote(), units:{}};
    units.forEach(function(u){
      data.units[u.getAttribute("data-id")]={v:verdictOf(u), c:choiceOf(u), n:noteOf(u)};
    });
    try{ localStorage.setItem(KEY, JSON.stringify(data)); }catch(e){}
  }
  function restore(){
    try{
      var d=JSON.parse(localStorage.getItem(KEY)||"{}");
      var g=document.getElementById("globalNote"); if(g&&d.g) g.value=d.g;
      units.forEach(function(u){
        var rec=(d.units||{})[u.getAttribute("data-id")]; if(!rec) return;
        if(rec.v){ var b=u.querySelector('.seg button[data-v="'+rec.v+'"]'); if(b) b.classList.add("on"); }
        if(rec.c){ var r=u.querySelector('.radios input[value="'+rec.c+'"]'); if(r) r.checked=true; }
        if(rec.n){ var t=u.querySelector("textarea[data-note]"); if(t) t.value=rec.n; }
      });
    }catch(e){}
  }

  var gWrap=document.createElement("div");
  gWrap.innerHTML='<div class="lbl" style="margin-top:18px">全局备注（整体方向 / 漏掉的要求 / 哪个 gate 太弱 / 约束）</div>'
    +'<textarea id="globalNote" placeholder="例如：整体 OK，但 req-3 的 gate 会空转、req-5 砍掉；dec-1 选 B…"></textarea>';
  var actions=document.querySelector(".actions");
  actions.parentNode.insertBefore(gWrap, actions);

  units.forEach(function(u){
    u.querySelectorAll(".seg button").forEach(function(b){
      b.addEventListener("click", function(){
        var was=b.classList.contains("on");
        u.querySelectorAll(".seg button").forEach(function(x){x.classList.remove("on");});
        if(!was) b.classList.add("on");
        refresh();
      });
    });
    u.querySelectorAll('.radios input').forEach(function(r){ r.addEventListener("change", refresh); });
    var t=u.querySelector("textarea[data-note]"); if(t) t.addEventListener("input", refresh);
  });
  document.getElementById("globalNote").addEventListener("input", refresh);

  function flash(m){ stat.textContent=m; stat.classList.add("show"); setTimeout(function(){stat.classList.remove("show");},1600); }
  function copyText(txt){
    if(navigator.clipboard&&navigator.clipboard.writeText){
      navigator.clipboard.writeText(txt).then(function(){flash("已复制 ✓");}, function(){legacy(txt);});
    } else { legacy(txt); }
  }
  function legacy(txt){
    var ta=document.createElement("textarea"); ta.value=txt; document.body.appendChild(ta); ta.select();
    try{document.execCommand("copy"); flash("已复制 ✓");}catch(e){flash("请手动选中下方文本复制");}
    document.body.removeChild(ta);
  }
  document.getElementById("copyBtn").addEventListener("click", function(){ copyText(serialize()); });
  document.getElementById("dlBtn").addEventListener("click", function(){
    var blob=new Blob([serialize()],{type:"text/markdown"});
    var a=document.createElement("a"); a.href=URL.createObjectURL(blob);
    a.download="planboard-annotations-r"+ROUND+".md"; a.click(); flash("已下载 ✓");
  });
  document.getElementById("acceptAllBtn").addEventListener("click", function(){
    var weak=units.some(function(u){ return u.getAttribute("data-kind")==="req" && u.getAttribute("data-verdict")!=="strong"; });
    if(weak && !window.confirm("有 requirement 的 gate 还是 弱/待补（非 strong）。全部采纳等于批准一份还不可信的规格，确定？")) return;
    units.forEach(function(u){
      if(u.getAttribute("data-kind")!=="req") return;
      u.querySelectorAll(".seg button").forEach(function(x){x.classList.remove("on");});
      var b=u.querySelector('.seg button[data-v="accept"]'); if(b) b.classList.add("on");
    });
    refresh(); flash("requirement 已全部采纳 ✓");
  });
  document.getElementById("clearBtn").addEventListener("click", function(){
    try{localStorage.removeItem(KEY);}catch(e){}
    document.getElementById("globalNote").value="";
    units.forEach(function(u){
      u.querySelectorAll(".seg button").forEach(function(x){x.classList.remove("on");});
      u.querySelectorAll('.radios input').forEach(function(r){r.checked=false;});
      var t=u.querySelector("textarea[data-note]"); if(t) t.value="";
    });
    refresh(); flash("已清空 ✓");
  });

  restore(); refresh();
})();
</script>
</body>
</html>"""

    task_t = (task[:40] + "…") if len(task) > 41 else task
    return fill_template(
        tmpl,
        {
            "__ROUND__": str(rnd),
            "__NEXTROUND__": str(rnd + 1),
            "__DATE__": date,
            "__LSKEY__": lskey,
            "__HEADLINE__": esc(headline),
            "__INTENT_BLOCK__": intent_block,
            "__COVERAGE__": render_coverage(plan),
            "__CHANGES__": render_revision_changes(revision_changes, linkable_ids),
            "__UNITS__": render_units(plan, revision_by_unit),
            "__NONGOALS__": render_non_goals(plan.get("non_goals") or plan.get("deferred")),
            "__QUESTIONS__": render_questions(plan.get("open_questions")),
            "__LEGACY_ALTS__": render_legacy_alternatives(plan.get("alternatives_considered"))
            if not plan.get("requirements") and plan.get("steps")
            else "",
            "__TASK__": esc(task),
            "__TASK_T__": esc(task_t),
            "__TASK_JSON__": js_json(task),
        },
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render a planboard acceptance-spec JSON to annotatable HTML.")
    ap.add_argument("plan_json", help="path to the spec JSON file")
    ap.add_argument("out_html", help="path to write the HTML file")
    ap.add_argument("--slug", default=None, help="short slug for filename/localStorage key")
    args = ap.parse_args(argv)

    with open(args.plan_json, "r", encoding="utf-8") as f:
        plan = json.load(f)

    try:
        validate_unit_ids(plan)
    except ValueError as exc:
        print(f"planboard: invalid unit ids: {exc}", file=sys.stderr)
        return 2

    slug = slugify(args.slug or plan.get("task", ""))
    html_out = build_html(plan, slug)

    out_dir = os.path.dirname(os.path.abspath(args.out_html))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.out_html, "w", encoding="utf-8") as f:
        f.write(html_out)

    nreq = len(plan.get("requirements") or plan.get("steps") or [])
    nsc = len(plan.get("scopes") or [])
    nunc = len([u for u in (plan.get("uncovered_failure_modes") or []) if str(u).strip()])
    print(f"planboard: wrote {args.out_html} ({nreq} requirements, {nsc} scopes, {nunc} uncovered, round {plan.get('round', 1)}, slug={slug})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
