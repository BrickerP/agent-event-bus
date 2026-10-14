"""Replay a bus: verify hashes and rebuild counts."""
from __future__ import annotations

from collections import Counter

from .bus import verify_chain


def replay(bus: dict) -> dict:
    ok, detail = verify_chain(bus)
    events = bus.get("events") or []
    by_type = Counter(e["type"] for e in events)
    by_side = Counter(e["side_effect_kind"] for e in events)
    routines = sorted({(e.get("routine") or "") for e in events if e.get("routine")})
    slots = sorted({(e.get("slot") or "") for e in events})  # includes "" for unslotted
    first_ts = events[0]["ts"] if events else None
    last_ts = events[-1]["ts"] if events else None
    return {
        "chain_ok": ok,
        "chain_detail": detail,
        "count": len(events),
        "by_type": dict(by_type),
        "by_side_effect": dict(by_side),
        "routines": routines,
        "routine_count": len(routines),
        "slot_count": len(slots),
        "first_ts": first_ts,
        "last_ts": last_ts,
        "tip_hash": bus.get("tip_hash"),
        "bus": bus.get("bus"),
    }
