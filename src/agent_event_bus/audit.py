"""Side-effect audit + policy PASS/FAIL gates."""
from __future__ import annotations

from .bus import SIDE_EFFECT_KINDS
from .replay import replay


def _short_ts(ts: str | None) -> str:
    if not ts:
        return "?"
    # 2026-10-14T00:03:45+08:00 -> 2026-10-14T00:03+08
    if "T" in ts:
        date, rest = ts.split("T", 1)
        hm = rest[:5]
        zone = ""
        if "+" in rest:
            zone = "+" + rest.split("+", 1)[1][:2]
        elif rest.endswith("Z"):
            zone = "Z"
        return f"{date}T{hm}{zone}"
    return ts


def audit(bus: dict, policy: dict, source: str = "") -> dict:
    rep = replay(bus)
    events = bus.get("events") or []
    public_types = set(policy.get("public_facing_types") or ["reply", "post", "quote"])
    public_counts = {}
    for t in sorted(public_types):
        public_counts[t] = sum(1 for e in events if e["type"] == t)
    public_total = sum(public_counts.values())

    # Side-effect counts with stable key order
    side = {k: int(rep["by_side_effect"].get(k, 0)) for k in SIDE_EFFECT_KINDS}

    # Contiguous seq already checked in verify_chain; surface explicitly
    seq_ok = all(e.get("seq") == i for i, e in enumerate(events, start=1))

    gates_cfg = policy.get("gates") or {}
    min_events = int(gates_cfg.get("min_events", 50))
    gates = []

    if gates_cfg.get("require_intact_chain", True):
        gates.append({
            "name": "hash chain intact",
            "ok": bool(rep["chain_ok"]),
            "value": rep["chain_detail"],
        })
    if gates_cfg.get("require_contiguous_seq", True):
        gates.append({
            "name": "no orphan events (seq contiguous from 1)",
            "ok": seq_ok and rep["count"] == len(events),
            "value": f"1..{rep['count']}" if seq_ok else "gap",
        })
    if gates_cfg.get("require_public_side_effect_if_public_actions", True):
        networkish = side.get("network", 0) + side.get("write", 0) + side.get("exec", 0)
        if public_total == 0:
            ok_pub = True
            val = "no public actions"
        else:
            ok_pub = networkish > 0
            val = f"public_actions={public_total} recorded_side_effects(network+write+exec)={networkish}"
        gates.append({
            "name": "public-facing side effects recorded when reply/post/quote/like present",
            "ok": ok_pub,
            "value": val,
        })
    gates.append({
        "name": f"demo day has ≥{min_events} events",
        "ok": rep["count"] >= min_events,
        "value": str(rep["count"]),
    })

    passed = all(g["ok"] for g in gates)
    result = {
        "pass": passed,
        "bus": bus.get("bus"),
        "source": source,
        "events": rep["count"],
        "chain": "intact" if rep["chain_ok"] else "BROKEN",
        "chain_detail": rep["chain_detail"],
        "side_effects": side,
        "public_actions": public_counts,
        "by_type": rep["by_type"],
        "routines": rep["routine_count"],
        "routine_names": rep["routines"],
        "slot_count": rep["slot_count"],
        "first_ts": rep["first_ts"],
        "last_ts": rep["last_ts"],
        "window": f"{_short_ts(rep['first_ts'])} → {_short_ts(rep['last_ts'])}",
        "tip_hash": rep["tip_hash"],
        "gates": gates,
        "events_list": events,
    }
    return result


def summary_text(result: dict) -> str:
    se = result["side_effects"]
    pa = result["public_actions"]
    # Stable public-action order: reply, quote, post, like, then rest
    order = ["reply", "quote", "post", "like"]
    keys = [k for k in order if pa.get(k)] + [k for k in pa if k not in order and pa.get(k)]
    pub_bits = " ".join(f"{k}={pa[k]}" for k in keys)
    # Compact window: drop repeated date on the end side
    window = result["window"]
    if " → " in window:
        a, b = window.split(" → ", 1)
        if "T" in a and "T" in b and a.split("T", 1)[0] == b.split("T", 1)[0]:
            window = f"{a} → {b.split('T', 1)[1]}"
    lines = [
        f"RESULT: {'PASS' if result['pass'] else 'FAIL'}",
        f"  bus={result['bus']}  events={result['events']}  chain={result['chain']}",
        (f"  side_effects: network={se.get('network', 0)}  write={se.get('write', 0)}  "
         f"exec={se.get('exec', 0)}  identity={se.get('identity', 0)}  none={se.get('none', 0)}"),
        f"  public_actions: {pub_bits}" if pub_bits else "  public_actions: (none)",
        f"  routines={result['routines']}  window={window}",
    ]
    for g in result["gates"]:
        mark = "ok" if g["ok"] else "FAIL"
        lines.append(f"  [{mark}] {g['name']} ({g['value']})")
    return "\n".join(lines)
