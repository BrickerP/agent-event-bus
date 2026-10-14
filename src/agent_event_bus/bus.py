"""Hash-chained append-only event bus (stdlib only)."""
from __future__ import annotations

import hashlib
import json
from typing import Any


GENESIS = "0" * 64
SIDE_EFFECT_KINDS = ("none", "network", "write", "exec", "identity", "other")


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_hash(payload: dict) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def event_hash(seq: int, ts: str, typ: str, routine: str | None,
               side_effect_kind: str, phash: str, prev_hash: str) -> str:
    material = {
        "seq": seq,
        "ts": ts,
        "type": typ,
        "routine": routine,
        "side_effect_kind": side_effect_kind,
        "payload_hash": phash,
        "prev_hash": prev_hash,
    }
    return hashlib.sha256(_canonical(material).encode("utf-8")).hexdigest()


def classify_side_effect(typ: str, policy: dict) -> str:
    mapping = policy.get("side_effect_by_type") or {}
    kind = mapping.get(typ, policy.get("default_side_effect", "other"))
    if kind not in SIDE_EFFECT_KINDS:
        kind = "other"
    return kind


def append_event(raw: dict, seq: int, prev_hash: str, policy: dict) -> dict:
    """Turn one actions_log-shaped record into a chained bus event."""
    typ = str(raw.get("type") or "unknown")
    ts = str(raw.get("ts") or "")
    routine = raw.get("routine")
    side = classify_side_effect(typ, policy)

    # Structure-only payload: drop free-text bodies if present; keep hints.
    payload = {k: v for k, v in raw.items() if k not in ("text", "body", "content")}
    phash = payload_hash(payload)
    ehash = event_hash(seq, ts, typ, routine, side, phash, prev_hash)
    return {
        "seq": seq,
        "ts": ts,
        "type": typ,
        "routine": routine,
        "side_effect_kind": side,
        "payload_hash": phash,
        "prev_hash": prev_hash,
        "event_hash": ehash,
        "slot": raw.get("slot"),
        "status": raw.get("status"),
    }


def build_bus(raw_events: list[dict], policy: dict, bus_id: str = "bus") -> dict:
    events = []
    prev = GENESIS
    for i, raw in enumerate(raw_events, start=1):
        ev = append_event(raw, i, prev, policy)
        events.append(ev)
        prev = ev["event_hash"]
    return {
        "bus": bus_id,
        "genesis": GENESIS,
        "tip_hash": prev if events else GENESIS,
        "events": events,
        "count": len(events),
    }


def verify_chain(bus: dict) -> tuple[bool, str]:
    """Walk the chain; return (ok, detail)."""
    events = bus.get("events") or []
    prev = bus.get("genesis") or GENESIS
    for i, ev in enumerate(events, start=1):
        if ev.get("seq") != i:
            return False, f"seq gap at position {i}: got seq={ev.get('seq')}"
        if ev.get("prev_hash") != prev:
            return False, f"prev_hash mismatch at seq={i}"
        expected = event_hash(
            ev["seq"], ev["ts"], ev["type"], ev.get("routine"),
            ev["side_effect_kind"], ev["payload_hash"], ev["prev_hash"],
        )
        if ev.get("event_hash") != expected:
            return False, f"event_hash mismatch at seq={i} (mutated or forged)"
        prev = ev["event_hash"]
    tip = bus.get("tip_hash")
    if events and tip != events[-1]["event_hash"]:
        return False, "tip_hash does not match last event"
    if not events and tip != (bus.get("genesis") or GENESIS):
        return False, "empty bus tip_hash != genesis"
    return True, "intact"
