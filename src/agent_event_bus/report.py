"""Dark-theme HTML side-effect audit report (no JS, no network)."""
from __future__ import annotations

import html


def render(result: dict) -> str:
    ok = result["pass"]
    se = result["side_effects"]
    pa = result["public_actions"]
    tip = result.get("tip_hash") or ""
    tip_short = tip[:16] + "…" if len(tip) > 16 else tip

    gates = "".join(
        f'<li class="{"ok" if g["ok"] else "bad"}">{"✔" if g["ok"] else "✘"} '
        f'{html.escape(g["name"])} <b>{html.escape(str(g["value"]))}</b></li>'
        for g in result["gates"]
    )

    # Side-effect bars
    max_se = max(se.values()) if se else 1
    colors = {
        "network": "#3b82f6",
        "write": "#f59e0b",
        "exec": "#ef4444",
        "identity": "#a855f7",
        "none": "#64748b",
        "other": "#94a3b8",
    }

    def bar(label, n, color):
        w = max(2, int(420 * n / max_se)) if max_se else 2
        return (
            f'<div class="bar"><span class="bl">{html.escape(label)}</span>'
            f'<span class="bv" style="width:{w}px;background:{color}"></span>'
            f'<span class="bn">{n}</span></div>'
        )

    bars = "".join(bar(k, se.get(k, 0), colors.get(k, "#94a3b8"))
                   for k in ("network", "write", "exec", "identity", "none", "other")
                   if se.get(k, 0) or k in ("network", "none", "identity"))

    type_rows = "".join(
        f'<tr><td>{html.escape(t)}</td><td class="n">{c}</td>'
        f'<td>{html.escape(next((e["side_effect_kind"] for e in result["events_list"] if e["type"]==t), ""))}</td></tr>'
        for t, c in sorted(result["by_type"].items(), key=lambda x: (-x[1], x[0]))
    )

    pub = " · ".join(f"{k} {v}" for k, v in pa.items() if v) or "none"
    routines = ", ".join(result.get("routine_names") or []) or "—"

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>agent-event-bus · {html.escape(str(result.get('bus') or ''))}</title>
<style>
body{{font:15px/1.45 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;margin:0;background:#0b1220;color:#e2e8f0}}
.wrap{{max-width:960px;margin:0 auto;padding:28px 32px}}
h1{{font-size:22px;margin:0 0 4px;color:#f8fafc}} .sub{{color:#94a3b8;margin:0 0 18px;font-size:13px}}
.cards{{display:flex;gap:14px;margin:0 0 18px;flex-wrap:wrap}}
.card{{flex:1;min-width:140px;background:#111827;border:1px solid #1f2937;border-radius:12px;padding:14px 16px}}
.card .k{{font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}}
.card .v{{font-size:28px;font-weight:700;margin-top:4px}}
.pass{{color:#22c55e}} .fail{{color:#ef4444}}
.bar{{display:flex;align-items:center;gap:10px;margin:6px 0}}
.bl{{width:90px;font-size:13px;color:#cbd5e1}} .bv{{height:16px;border-radius:4px;display:inline-block}}
.bn{{font-variant-numeric:tabular-nums;font-size:13px;color:#e2e8f0}}
ul.g{{list-style:none;padding:0;margin:12px 0 18px}} ul.g li{{margin:5px 0;font-size:14px}}
li.ok{{color:#4ade80}} li.bad{{color:#f87171}}
.note{{background:#1e293b;border-left:4px solid #3b82f6;padding:10px 14px;border-radius:8px;font-size:13px;color:#cbd5e1;margin:0 0 18px}}
table{{border-collapse:collapse;width:100%;font-size:13px;background:#111827;border-radius:10px;overflow:hidden}}
th{{background:#1e293b;color:#94a3b8;font-weight:600;text-transform:uppercase;font-size:11px;letter-spacing:.04em}}
td,th{{padding:8px 10px;border-bottom:1px solid #1f2937;text-align:left}}
td.n{{text-align:right;font-variant-numeric:tabular-nums}}
.mono{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;color:#93c5fd}}
.foot{{color:#64748b;font-size:12px;margin-top:18px}}
h3{{margin:18px 0 8px;font-size:15px;color:#f1f5f9}}
</style></head><body><div class="wrap">
<h1>agent-event-bus · {html.escape(str(result.get('bus') or ''))}</h1>
<p class="sub">Hash-chained append-only log of what the agent actually did · fixture is our real X-agent day (structure only, no post bodies) · {html.escape(str(result.get('source') or ''))}</p>
<div class="cards">
<div class="card"><div class="k">Result</div><div class="v {'pass' if ok else 'fail'}">{'PASS' if ok else 'FAIL'}</div></div>
<div class="card"><div class="k">Events</div><div class="v">{result['events']}</div></div>
<div class="card"><div class="k">Chain</div><div class="v {'pass' if result['chain']=='intact' else 'fail'}">{html.escape(result['chain'])}</div></div>
<div class="card"><div class="k">Network SE</div><div class="v">{se.get('network', 0)}</div></div>
</div>
<p class="note">Lived demo: <b>{result['events']}</b> events from our own agent day · window <b>{html.escape(result['window'])}</b> · public actions <b>{html.escape(pub)}</b> · tip <span class="mono">{html.escape(tip_short)}</span></p>
<ul class="g">{gates}</ul>
<h3>Side-effect breakdown</h3>
{bars}
<h3>Per-type counts</h3>
<table><tr><th>type</th><th>count</th><th>side effect</th></tr>{type_rows}</table>
<p class="sub" style="margin-top:14px">Routines touched: {html.escape(routines)}</p>
<p class="foot">Built with agent-event-bus by Yupeng Lu · AI agent &amp; backend engineer · https://brickerp.github.io/hire/</p>
</div></body></html>"""
