"""Load actions_log-shaped JSON / JSONL into a raw event list."""
from __future__ import annotations

import json
import os


def load_policy(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_events_file(path: str) -> tuple[str, str, list[dict]]:
    """Return (bus_id, source, raw_events) from a fixture JSON or JSONL."""
    with open(path, encoding="utf-8") as f:
        text = f.read().strip()
    if not text:
        return "empty", path, []

    # JSONL: every non-empty line is an object
    if "\n" in text and not text.lstrip().startswith("{"):
        events = []
        for line in text.splitlines():
            line = line.strip()
            if line:
                events.append(json.loads(line))
        return os.path.basename(path), path, events

    # Could still be JSONL of objects, or a wrapped JSON
    if text.lstrip().startswith("{"):
        # Try full JSON first
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # JSONL of objects
            events = [json.loads(line) for line in text.splitlines() if line.strip()]
            return os.path.basename(path), path, events
        if isinstance(data, dict) and "events" in data:
            bus_id = data.get("bus") or data.get("name") or os.path.basename(path)
            source = data.get("source") or path
            return str(bus_id), str(source), list(data["events"])
        if isinstance(data, dict) and "ts" in data and "type" in data:
            return os.path.basename(path), path, [data]
        if isinstance(data, list):
            return os.path.basename(path), path, data
        raise ValueError(f"unsupported JSON shape in {path}")

    # JSONL
    events = [json.loads(line) for line in text.splitlines() if line.strip()]
    return os.path.basename(path), path, events


def from_actions_log(path: str, day: str) -> tuple[str, str, list[dict]]:
    """Filter a JSONL actions_log to one calendar day (ts prefix)."""
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            ts = str(obj.get("ts") or "")
            if ts.startswith(day):
                # Sanitize: drop free text bodies
                clean = {k: v for k, v in obj.items() if k not in ("text", "body", "content")}
                if "text_chars" not in clean and "text" in obj and isinstance(obj["text"], str):
                    clean["text_chars"] = len(obj["text"])
                events.append(clean)
    bus_id = f"from-log-{day}"
    source = f"{path} day={day}"
    return bus_id, source, events
