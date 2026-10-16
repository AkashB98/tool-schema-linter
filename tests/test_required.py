"""Tests for the REQ-* required-vs-optional hygiene rules."""
from __future__ import annotations

import unittest

from linter import lint_tool
from tests.helpers import by_rule, prop, rule_ids, tool


class TestRequired(unittest.TestCase):
    def test_required_subset_passes(self):
        f = lint_tool(tool(properties={"device_id": prop()},
                           required=["device_id"]))
        for rid in ("REQ-001", "REQ-002", "REQ-003", "REQ-004"):
            self.assertNotIn(rid, rule_ids(f))

    def test_required_not_in_properties_errors(self):
        f = lint_tool(tool(properties={"device_id": prop()},
                           required=["device_id", "ghost"]))
        hit = by_rule(f, "REQ-001")
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0].severity, "error")
        self.assertIn("ghost", hit[0].message)

    def test_default_plus_required_errors(self):
        bad = prop(default="auto")
        f = lint_tool(tool(properties={"device_id": bad}, required=["device_id"]))
        hit = by_rule(f, "REQ-003")
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0].severity, "error")

    def test_optional_claim_but_required_warns(self):
        bad = prop(description="The device identifier; this is optional.")
        f = lint_tool(tool(properties={"device_id": bad}, required=["device_id"]))
        hit = by_rule(f, "REQ-002")
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0].severity, "warn")

    def test_can_be_null_claim_but_required_warns(self):
        bad = prop(description="May be null if unknown, else the identifier.")
        f = lint_tool(tool(properties={"device_id": bad}, required=["device_id"]))
        self.assertIn("REQ-002", rule_ids(f))

    def test_optional_word_as_noun_does_not_fire(self):
        # FP trap: "optional" used as a noun phrase, not a claim about the param
        ok = prop(description="Toggles the 'optional' extras pack for the device.")
        f = lint_tool(tool(properties={"extras": ok}, required=["extras"]))
        self.assertNotIn("REQ-002", rule_ids(f))

    def test_optional_claim_not_required_does_not_fire(self):
        ok = prop(description="This is optional and may be omitted.")
        f = lint_tool(tool(properties={"extras": ok}))
        self.assertNotIn("REQ-002", rule_ids(f))

    def test_nullable_oneof_required_warns(self):
        bad = prop(description="Identifier that may be null.")
        bad.pop("type")
        bad["oneOf"] = [{"type": "string"}, {"type": "null"}]
        f = lint_tool(tool(properties={"uid": bad}, required=["uid"]))
        hit = by_rule(f, "REQ-004")
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0].severity, "warn")

    def test_nullable_type_list_required_warns(self):
        bad = prop(type=["string", "null"],
                   description="Identifier that may be null.")
        f = lint_tool(tool(properties={"uid": bad}, required=["uid"]))
        self.assertIn("REQ-004", rule_ids(f))

    def test_nested_required_checked(self):
        f = lint_tool(tool(properties={
            "address": {"type": "object",
                        "description": "Where to ship the order.",
                        "examples": [{"street": "x"}],
                        "properties": {"street": prop()},
                        "required": ["street", "ghost_nested"],
                        "additionalProperties": False},
        }))
        hit = by_rule(f, "REQ-001")
        self.assertEqual(len(hit), 1)
        self.assertIn("ghost_nested", hit[0].message)


if __name__ == "__main__":
    unittest.main()
