#!/usr/bin/env python3
"""planboard renderer: structured plan JSON -> annotatable review HTML.

Durable infrastructure for the `planboard` skill (NOT one-shot). The page is
review-first: every step keeps a short scannable `summary`, but long Chinese
context remains comfortably readable when the reviewer expands "详情".

Usage:
    python3 render_planboard.py <plan.json> <out.html> [--slug SLUG]

stdlib only.
"""

import argparse
import datetime
import hashlib
import html
import json
import os
import re
import sys

VERDICT_LABEL = {"accept": "采纳", "edit": "改", "reject": "砍"}


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


def render_step(step: dict, idx: int) -> str:
    sid = esc(step.get("id") or f"step-{idx + 1}")
    title = esc(step.get("title") or "")
    summary = (step.get("summary") or "").strip()
    what = (step.get("what") or "").strip()
    if not summary:  # back-compat: plans with no summary fall back to a clipped what
        summary = what if len(what) <= 130 else what[:128].rstrip() + "…"
    why = step.get("why")
    files = step.get("files") or []
    commands = [c for c in (step.get("commands") or []) if str(c).strip()]
    risk = step.get("risk")
    verification = step.get("verification")
    depends = [d for d in (step.get("depends_on") or []) if str(d).strip()]

    files_html = f'<div class="files">{chips(files, "fchip")}</div>' if files else ""

    drows = []
    if what and what != summary:
        drows.append(
            f'<div class="drow"><span class="k">做什么</span><div class="v">{esc(what)}</div></div>'
        )
    if why:
        drows.append(
            f'<div class="drow"><span class="k">为什么</span><div class="v">{esc(why)}</div></div>'
        )
    if commands:
        body = "\n".join(esc(c) for c in commands)
        drows.append(
            f'<div class="drow"><span class="k">命令</span><div class="v"><pre class="cmd">{body}</pre></div></div>'
        )
    if verification:
        drows.append(
            f'<div class="drow"><span class="k vk">验证</span><div class="v">{esc(verification)}</div></div>'
        )
    if risk:
        drows.append(
            f'<div class="drow"><span class="k rk">风险</span><div class="v">{esc(risk)}</div></div>'
        )
    if depends:
        drows.append(
            f'<div class="drow"><span class="k">依赖</span><div class="v">{chips(depends, "dchip")}</div></div>'
        )
    detail_html = ""
    if drows:
        detail_html = f'<details class="detail"><summary>详情</summary><div class="dbody">{"".join(drows)}</div></details>'

    return f"""    <div class="step" data-id="{sid}">
      <div class="sline"><span class="sid">{sid}</span><h4>{title}</h4></div>
      <p class="summary">{esc(summary)}</p>
      {files_html}
      <div class="seg" role="group" aria-label="对这一步的处置">
        <button type="button" data-v="accept">✓ 采纳</button><button type="button" data-v="edit">✎ 改</button><button type="button" data-v="reject">✗ 砍</button>
      </div>
      {detail_html}
      <textarea data-note placeholder="批注（改成什么 / 为什么砍 / 补充约束）…"></textarea>
    </div>"""


def render_deferred(items) -> str:
    items = [i for i in (items or []) if str(i).strip()]
    if not items:
        return ""
    lis = "".join(f"<li>{esc(i)}</li>" for i in items)
    return f"""  <details>
    <summary>暂缓 / 砍出主线（{len(items)}）— 研究里看到但没纳入这版的</summary>
    <div class="body"><ul class="tight">{lis}</ul></div>
  </details>"""


def render_alternatives(alts) -> str:
    alts = alts or []
    if not alts:
        return ""
    rows = "".join(
        f'<div class="opt"><div class="h">{esc(a.get("approach", ""))}</div>'
        f'<div class="mut">不选的原因：{esc(a.get("why_not", ""))}</div></div>'
        for a in alts
    )
    return f"""  <details>
    <summary>考虑过但没选的方案（{len(alts)}）</summary>
    <div class="body">{rows}</div>
  </details>"""


def render_questions(qs) -> str:
    qs = [q for q in (qs or []) if str(q).strip()]
    if not qs:
        return ""
    lis = "".join(f'<li><span class="qtext">{esc(q)}</span></li>' for q in qs)
    return f"""  <div class="qbox">
    <div class="lbl">决策项 / 开放问题</div>
    <ol>{lis}</ol>
    </div>"""


def render_revision_changes(items) -> str:
    items = [i for i in (items or []) if i]
    if not items:
        return ""
    cards = []
    for raw in items:
        if isinstance(raw, dict):
            sid = raw.get("step_id") or raw.get("id") or raw.get("step") or ""
            status = raw.get("status") or raw.get("verdict") or raw.get("kind") or ""
            change = raw.get("change") or raw.get("summary") or raw.get("note") or ""
        else:
            sid = ""
            status = ""
            change = str(raw)
        head_bits = []
        if sid:
            head_bits.append(f'<code class="dchip">{esc(sid)}</code>')
        if status:
            head_bits.append(f'<span class="revtag">{esc(status)}</span>')
        head = "".join(head_bits)
        cards.append(
            f'<div class="revitem"><div class="revhead">{head}</div>'
            f'<div class="revtext">{esc(change)}</div></div>'
        )
    return f"""  <div class="revbox">
    <div class="lbl">本轮改动（打开页面先看这里）</div>
    <div class="revgrid">{"".join(cards)}</div>
  </div>"""


def build_html(plan: dict, slug: str) -> str:
    task = plan.get("task") or ""
    rnd = int(plan.get("round") or 1)
    headline = (plan.get("headline") or "").strip()
    approach = (plan.get("approach_summary") or "").strip()
    if not headline:
        headline = first_sentence(approach) or "（无 headline）"
    approach_block = ""
    if approach and approach != headline:
        approach_block = (
            '<details class="detail"><summary>整体思路 / 背景</summary>'
            f'<div class="dbody"><div class="v">{esc(approach)}</div></div></details>'
        )

    steps = plan.get("steps") or []
    date = datetime.date.today().isoformat()
    lskey = f"planboard_{slug}_r{rnd}"

    steps_html = "\n".join(render_step(s, i) for i, s in enumerate(steps))
    changes_html = render_revision_changes(plan.get("changes_from_previous_round"))
    deferred_html = render_deferred(plan.get("deferred"))
    alts_html = render_alternatives(plan.get("alternatives_considered"))
    q_html = render_questions(plan.get("open_questions"))

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
  body{margin:0;background:var(--bg);color:var(--ink);
    font:17px/1.72 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;}
  .wrap{max-width:1160px;margin:0 auto;padding:42px 34px 110px}
  h1{font-size:30px;margin:0 0 6px;letter-spacing:0;font-weight:780}
  .sub{color:var(--mut);margin:0 0 22px;font-size:15px}
  .lead{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--acc);
    border-radius:8px;padding:18px 22px;margin:8px 0 20px}
  .lead .headline{font-size:19px;color:var(--ink);line-height:1.62;font-weight:680}
  .lbl{font-size:13px;letter-spacing:.2px;color:var(--mut);margin:0 0 8px;font-weight:760}
  .mut{color:var(--mut)}
  code{background:#0b0f15;border:1px solid var(--line);border-radius:5px;padding:2px 6px;font-size:13px;
    font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
  /* ---- step card: summary-first, detail collapsed ---- */
  .step{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:18px 20px;margin:16px 0}
  .step .sline{display:flex;align-items:center;gap:12px}
  .step .sid{font:760 12px/1 ui-monospace,Menlo,monospace;color:var(--acc2);
    background:rgba(184,156,255,.13);border:1px solid rgba(184,156,255,.36);border-radius:999px;padding:6px 10px;white-space:nowrap}
  .step h4{margin:0;font-size:19px;flex:1;font-weight:760;color:var(--ink);letter-spacing:0}
  .step .summary{margin:12px 0 12px;font-size:17px;color:#e4ebf4;line-height:1.66}
  .step .files{margin:4px 0 12px}
  .fchip{color:#cdd6e4}.dchip{color:var(--acc2)}
  .seg{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden}
  .seg button{background:transparent;border:0;color:var(--mut);padding:9px 18px;font-size:15px;cursor:pointer;font-weight:720}
  .seg button+button{border-left:1px solid var(--line)}
  .seg button.on[data-v="accept"]{background:rgba(78,201,168,.18);color:var(--good)}
  .seg button.on[data-v="edit"]{background:rgba(226,182,92,.18);color:var(--warn)}
  .seg button.on[data-v="reject"]{background:rgba(227,118,111,.18);color:var(--bad)}
  textarea{width:100%;background:#0b0f15;border:1px solid var(--line);border-radius:8px;color:var(--ink);
    padding:11px 13px;font:15px/1.55 inherit;margin-top:12px;resize:vertical;min-height:48px}
  textarea:focus{outline:none;border-color:var(--acc)}
  /* ---- step detail (lightweight toggle, not a box) ---- */
  details.detail{background:transparent;border:0;border-radius:0;margin:12px 0 0;overflow:visible}
  details.detail>summary{cursor:pointer;list-style:none;padding:8px 0;font-size:14px;color:var(--mut);font-weight:720}
  details.detail>summary::-webkit-details-marker{display:none}
  details.detail>summary::before{content:"\25b8 详情展开";color:var(--mut);font-weight:600}
  details.detail[open]>summary{font-size:0}
  details.detail[open]>summary::before{content:"\25be 收起";font-size:14px}
  details.detail .dbody{padding:10px 0 2px;border-top:1px solid var(--softline)}
  .drow{display:grid;grid-template-columns:72px 1fr;gap:14px;margin:10px 0;font-size:15px}
  .drow .k{color:var(--mut);font-weight:760;font-size:13px;letter-spacing:0;padding-top:2px}
  .drow .k.vk{color:var(--good)}.drow .k.rk{color:var(--warn)}
  .drow .v{color:#d7dfeb;line-height:1.64;white-space:pre-wrap;overflow-wrap:anywhere}
  pre.cmd{background:#0b0f15;border:1px solid var(--line);border-radius:7px;padding:11px 13px;margin:2px 0;
    font-size:13px;white-space:pre-wrap;color:#d7dfeb;overflow:auto}
  /* ---- collapsible sections (deferred / alts / questions) ---- */
  details:not(.detail){background:var(--panel);border:1px solid var(--line);border-radius:8px;margin:18px 0;overflow:hidden}
  details:not(.detail)>summary{cursor:pointer;list-style:none;padding:15px 20px;font-weight:720;font-size:16px}
  details:not(.detail)>summary::-webkit-details-marker{display:none}
  details:not(.detail)>summary::before{content:"\25b8";color:var(--mut);margin-right:8px}
  details:not(.detail)[open]>summary::before{content:"\25be"}
  details:not(.detail) .body{padding:6px 20px 18px;border-top:1px solid var(--line)}
  ul.tight{margin:8px 0;padding-left:24px}ul.tight li{margin:8px 0;color:var(--mut)}
  .opt{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:13px 15px;margin:10px 0}
  .opt .h{font-weight:720;margin-bottom:3px;color:var(--ink)}
  .qbox{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--warn);border-radius:8px;padding:16px 20px;margin:18px 0}
  .qbox ol{margin:6px 0 0;padding-left:24px}.qbox li{margin:10px 0;color:var(--mut)}
  .qbox .qtext{color:#d7dfeb}
  .revbox{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--warn);
    border-radius:8px;padding:16px 20px;margin:18px 0}
  .revgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px}
  .revitem{background:var(--card);border:1px solid var(--softline);border-radius:8px;padding:12px 14px}
  .revhead{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:6px}
  .revtag{font-size:12px;font-weight:760;color:var(--warn);border:1px solid rgba(233,191,99,.42);
    background:rgba(233,191,99,.12);border-radius:999px;padding:2px 8px}
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
    body{font-size:16px}
    .wrap{padding:24px 16px 90px}
    h1{font-size:25px}
    .step{padding:15px 14px}
    .step .sline{align-items:flex-start;flex-direction:column;gap:8px}
    .step h4{font-size:18px}
    .drow{grid-template-columns:1fr;gap:4px}
    .seg{display:grid;grid-template-columns:repeat(3,1fr);width:100%}
    .seg button{padding:10px 6px}
    .counts{width:100%;margin-left:0}
  }
</style>
</head>
<body>
<div class="wrap">
  <h1>planboard · round __ROUND__</h1>
  <p class="sub">__TASK__ · __DATE__ · 逐步处置后点「复制批注」粘回 chat，我据此修订出 round __NEXTROUND__</p>

  <div class="lead">
    <div class="headline">__HEADLINE__</div>
    __APPROACH_BLOCK__
  </div>

__CHANGES__

__STEPS__

__DEFERRED__

__QUESTIONS__

__ALTS__

  <div class="actions">
    <button class="btn" id="copyBtn">复制批注</button>
    <button class="btn ghost" id="dlBtn">下载</button>
    <button class="btn ghost" id="acceptAllBtn">全部采纳</button>
    <button class="btn ghost" id="clearBtn">清空草稿</button>
    <span class="st" id="stat">已复制 ✓</span>
    <span class="counts" id="counts"></span>
  </div>
  <pre class="out" id="preview" aria-live="polite"></pre>

  <div class="foot">planboard · 渲染于 __DATE__ · 摘要可秒读，详情按需展开 · 草稿自动存浏览器（刷新不丢）</div>
</div>

<script>
(function(){
  var KEY = "__LSKEY__";
  var TASK = __TASK_JSON__;
  var ROUND = __ROUND__;
  var VMAP = {accept:"采纳", edit:"改", reject:"砍"};
  var steps = Array.prototype.slice.call(document.querySelectorAll(".step"));
  var preview = document.getElementById("preview");
  var stat = document.getElementById("stat");
  var counts = document.getElementById("counts");

  function snapshot(){
    var out = [];
    steps.forEach(function(st){
      var on = st.querySelector(".seg button.on");
      out.push({
        id: st.getAttribute("data-id"),
        title: (st.querySelector("h4")||{}).textContent ? st.querySelector("h4").textContent.trim() : "",
        v: on ? on.getAttribute("data-v") : "",
        n: (st.querySelector("textarea[data-note]")||{}).value || ""
      });
    });
    return out;
  }
  function serialize(){
    var snap = snapshot();
    var lines = ["# planboard 批注 · " + TASK + " · round " + ROUND, ""];
    snap.forEach(function(s){
      var v = s.v ? VMAP[s.v] : "—未选—";
      var tail = s.n.trim() ? "  ｜ " + s.n.trim() : "";
      lines.push("- [" + s.id + "] " + v + tail);
    });
    lines.push("");
    lines.push("全局备注: " + (gnote() || "（无）"));
    return lines.join("\n");
  }
  function gnote(){ var g=document.getElementById("globalNote"); return g ? g.value.trim() : ""; }
  function tally(){
    var a=0,e=0,r=0,u=0;
    snapshot().forEach(function(s){ if(s.v==="accept")a++;else if(s.v==="edit")e++;else if(s.v==="reject")r++;else u++; });
    counts.textContent = "采纳 "+a+" · 改 "+e+" · 砍 "+r+" · 未选 "+u;
  }
  function refresh(){ preview.textContent = serialize(); tally(); save(); }

  function save(){
    var data = {g: gnote(), steps:{}};
    steps.forEach(function(st){
      var on = st.querySelector(".seg button.on");
      data.steps[st.getAttribute("data-id")] = {
        v: on ? on.getAttribute("data-v") : "",
        n: (st.querySelector("textarea[data-note]")||{}).value || ""
      };
    });
    try{ localStorage.setItem(KEY, JSON.stringify(data)); }catch(e){}
  }
  function restore(){
    try{
      var d = JSON.parse(localStorage.getItem(KEY) || "{}");
      var g = document.getElementById("globalNote"); if(g && d.g) g.value = d.g;
      steps.forEach(function(st){
        var rec = (d.steps||{})[st.getAttribute("data-id")];
        if(!rec) return;
        if(rec.v){ var b=st.querySelector('.seg button[data-v="'+rec.v+'"]'); if(b) b.classList.add("on"); }
        if(rec.n){ var t=st.querySelector("textarea[data-note]"); if(t) t.value=rec.n; }
      });
    }catch(e){}
  }

  var gWrap = document.createElement("div");
  gWrap.innerHTML = '<div class="lbl" style="margin-top:18px">全局备注（整体方向 / 漏掉的步骤 / 优先级 / 约束）</div>'
    + '<textarea id="globalNote" placeholder="例如：整体 OK，但 step-3 砍掉、step-4 顺序提前；新增一步做回归测试…"></textarea>';
  var actions = document.querySelector(".actions");
  actions.parentNode.insertBefore(gWrap, actions);

  steps.forEach(function(st){
    st.querySelectorAll(".seg button").forEach(function(b){
      b.addEventListener("click", function(){
        var was = b.classList.contains("on");
        st.querySelectorAll(".seg button").forEach(function(x){x.classList.remove("on");});
        if(!was) b.classList.add("on");
        refresh();
      });
    });
    var t = st.querySelector("textarea[data-note]");
    if(t) t.addEventListener("input", refresh);
  });
  document.getElementById("globalNote").addEventListener("input", refresh);

  function flash(m){ stat.textContent=m; stat.classList.add("show"); setTimeout(function(){stat.classList.remove("show");},1600); }
  function copyText(txt){
    if(navigator.clipboard && navigator.clipboard.writeText){
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
    steps.forEach(function(st){
      st.querySelectorAll(".seg button").forEach(function(x){x.classList.remove("on");});
      var b=st.querySelector('.seg button[data-v="accept"]'); if(b) b.classList.add("on");
    });
    refresh(); flash("已全部采纳 ✓");
  });
  document.getElementById("clearBtn").addEventListener("click", function(){
    try{localStorage.removeItem(KEY);}catch(e){}
    document.getElementById("globalNote").value="";
    steps.forEach(function(st){
      st.querySelectorAll(".seg button").forEach(function(x){x.classList.remove("on");});
      var t=st.querySelector("textarea[data-note]"); if(t) t.value="";
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
            "__APPROACH_BLOCK__": approach_block,
            "__CHANGES__": changes_html,
            "__STEPS__": steps_html,
            "__DEFERRED__": deferred_html,
            "__QUESTIONS__": q_html,
            "__ALTS__": alts_html,
            "__TASK__": esc(task),
            "__TASK_T__": esc(task_t),
            "__TASK_JSON__": js_json(task),
        },
    )


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Render a planboard plan JSON to annotatable HTML."
    )
    ap.add_argument("plan_json", help="path to the plan JSON file")
    ap.add_argument("out_html", help="path to write the HTML file")
    ap.add_argument(
        "--slug", default=None, help="short slug for filename/localStorage key"
    )
    args = ap.parse_args(argv)

    with open(args.plan_json, "r", encoding="utf-8") as f:
        plan = json.load(f)

    slug = slugify(args.slug or plan.get("task", ""))
    html_out = build_html(plan, slug)

    out_dir = os.path.dirname(os.path.abspath(args.out_html))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.out_html, "w", encoding="utf-8") as f:
        f.write(html_out)

    n = len(plan.get("steps") or [])
    d = len(plan.get("deferred") or [])
    print(
        f"planboard: wrote {args.out_html} ({n} steps, {d} deferred, round {plan.get('round', 1)}, slug={slug})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
