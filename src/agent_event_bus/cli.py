import argparse
import json
import os
import sys

from .audit import audit, summary_text
from .bus import build_bus
from .ingest import from_actions_log, load_events_file, load_policy
from .report import render

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))


def _run(bus_id: str, source: str, raw_events: list, policy: dict, report: str | None, as_json: bool) -> int:
    bus = build_bus(raw_events, policy, bus_id=bus_id)
    result = audit(bus, policy, source=source)
    if report:
        os.makedirs(os.path.dirname(os.path.abspath(report)) or ".", exist_ok=True)
        with open(report, "w", encoding="utf-8") as f:
            f.write(render(result))
    if as_json:
        out = {k: v for k, v in result.items() if k != "events_list"}
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(summary_text(result))
        if report:
            print(f"  report -> {report}")
    return 0 if result["pass"] else 1


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="agent-event-bus",
        description="Append-only hash-chained event bus for AI agents: ingest → replay → side-effect audit.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--policy", default=os.path.join(ROOT, "fixtures", "policy.json"))
        p.add_argument("--report", default=None)
        p.add_argument("--json", action="store_true")

    d = sub.add_parser("demo", help="ingest our own agent day fixture and write docs/demo-report.html")
    common(d)
    r = sub.add_parser("run", help="ingest a events JSON (or wrapped fixture) and audit")
    r.add_argument("events")
    common(r)
    i = sub.add_parser("from-log", help="ingest an actions_log.jsonl for one day, then audit")
    i.add_argument("log")
    i.add_argument("--day", required=True, help="YYYY-MM-DD prefix of ts to include")
    common(i)

    a = ap.parse_args(argv)
    policy = load_policy(a.policy)

    if a.cmd == "demo":
        path = os.path.join(ROOT, "fixtures", "our_agent_day_2026-10-14.json")
        bus_id, source, raw = load_events_file(path)
        a.report = a.report or os.path.join(ROOT, "docs", "demo-report.html")
    elif a.cmd == "run":
        bus_id, source, raw = load_events_file(a.events)
    else:
        bus_id, source, raw = from_actions_log(a.log, a.day)

    return _run(bus_id, source, raw, policy, a.report, a.json)


if __name__ == "__main__":
    sys.exit(main())
