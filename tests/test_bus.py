import json
import os
import tempfile
import unittest

from agent_event_bus.audit import audit
from agent_event_bus.bus import GENESIS, append_event, build_bus, verify_chain
from agent_event_bus.ingest import from_actions_log, load_events_file, load_policy
from agent_event_bus.replay import replay

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POLICY = load_policy(os.path.join(ROOT, "fixtures", "policy.json"))
FIXTURE = os.path.join(ROOT, "fixtures", "our_agent_day_2026-10-14.json")


class TestChain(unittest.TestCase):
    def test_genesis_and_link(self):
        bus = build_bus(
            [{"ts": "2026-10-14T00:00:00+08:00", "type": "like", "routine": "3·互动"}],
            POLICY,
            bus_id="t",
        )
        self.assertEqual(bus["events"][0]["prev_hash"], GENESIS)
        self.assertEqual(bus["events"][0]["seq"], 1)
        ok, detail = verify_chain(bus)
        self.assertTrue(ok, detail)

    def test_mutation_breaks_chain(self):
        bus = build_bus(
            [
                {"ts": "2026-10-14T00:00:00+08:00", "type": "like"},
                {"ts": "2026-10-14T00:01:00+08:00", "type": "reply"},
            ],
            POLICY,
        )
        bus["events"][1]["type"] = "post"  # mutate without rehash
        ok, detail = verify_chain(bus)
        self.assertFalse(ok)
        self.assertIn("mismatch", detail)

    def test_seq_must_be_contiguous(self):
        bus = build_bus(
            [{"ts": "2026-10-14T00:00:00+08:00", "type": "like"}],
            POLICY,
        )
        bus["events"][0]["seq"] = 2
        # event_hash still old — verify catches hash or seq
        ok, _ = verify_chain(bus)
        self.assertFalse(ok)


class TestDemoFixture(unittest.TestCase):
    def test_demo_passes(self):
        bus_id, source, raw = load_events_file(FIXTURE)
        bus = build_bus(raw, POLICY, bus_id=bus_id)
        result = audit(bus, POLICY, source=source)
        self.assertTrue(result["pass"], result["gates"])
        self.assertEqual(result["events"], 64)
        self.assertEqual(result["chain"], "intact")
        self.assertGreaterEqual(result["side_effects"]["network"], 1)
        self.assertEqual(result["public_actions"]["reply"], 8)
        self.assertEqual(result["public_actions"]["like"], 25)
        self.assertEqual(result["public_actions"]["quote"], 3)
        self.assertEqual(result["public_actions"]["post"], 1)

    def test_replay_rebuilds_counts(self):
        _, _, raw = load_events_file(FIXTURE)
        bus = build_bus(raw, POLICY, bus_id="x")
        rep = replay(bus)
        self.assertTrue(rep["chain_ok"])
        self.assertEqual(rep["count"], 64)
        self.assertEqual(sum(rep["by_type"].values()), 64)


class TestFromLog(unittest.TestCase):
    def test_day_filter(self):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps({"ts": "2026-10-14T01:00:00+08:00", "type": "like", "text": "SECRET"}) + "\n")
            f.write(json.dumps({"ts": "2026-10-13T01:00:00+08:00", "type": "post", "text": "old"}) + "\n")
            path = f.name
        try:
            bus_id, source, raw = from_actions_log(path, "2026-10-14")
            self.assertEqual(len(raw), 1)
            self.assertNotIn("text", raw[0])
            self.assertEqual(raw[0].get("text_chars"), 6)
            bus = build_bus(raw, POLICY, bus_id=bus_id)
            self.assertTrue(verify_chain(bus)[0])
        finally:
            os.unlink(path)


class TestPublicGate(unittest.TestCase):
    def test_public_without_side_effect_fails(self):
        # Force reply to be classified as none → gate should fail
        policy = {
            "side_effect_by_type": {"reply": "none"},
            "default_side_effect": "none",
            "public_facing_types": ["reply"],
            "gates": {
                "min_events": 1,
                "require_intact_chain": True,
                "require_contiguous_seq": True,
                "require_public_side_effect_if_public_actions": True,
            },
        }
        bus = build_bus([{"ts": "2026-10-14T00:00:00+08:00", "type": "reply"}], policy)
        result = audit(bus, policy)
        self.assertFalse(result["pass"])


if __name__ == "__main__":
    unittest.main()
