"""Tests for the RISK-* rule and the lint engine core."""
from __future__ import annotations

import unittest

from linter import lint_tool, lint_tools
from tests.helpers import by_rule, prop, rule_ids, tool


class TestRisk(unittest.TestCase):
    def test_password_without_marker_warns(self):
        bad = prop(description="Customer password.")
        f = lint_tool(tool(properties={"customer_password": bad}))
        hit = by_rule(f, "RISK-001")
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0].severity, "warn")

    def test_password_with_marker_passes(self):
        ok = prop(description="Customer password.", sensitive=True)
        f = lint_tool(tool(properties={"customer_password": ok}))
        self.assertNotIn("RISK-001", rule_ids(f))

    def test_delete_prefix_warns(self):
        bad = prop(type="boolean", examples=[True],
                   description="Delete everything.")
        f = lint_tool(tool(properties={"delete_all": bad}))
        self.assertIn("RISK-001", rule_ids(f))

    def test_api_key_warns(self):
        bad = prop(description="Third-party API key.")
        f = lint_tool(tool(properties={"api_key": bad}))
        self.assertIn("RISK-001", rule_ids(f))

    def test_env_var_warns(self):
        bad = prop(description="Environment variable name.")
        f = lint_tool(tool(properties={"$env": bad}))
        self.assertIn("RISK-001", rule_ids(f))

    def test_innocent_name_passes(self):
        f = lint_tool(tool(properties={"device_id": prop()}))
        self.assertNotIn("RISK-001", rule_ids(f))


class TestEngine(unittest.TestCase):
    def test_findings_sorted_by_rule_path_message(self):
        f = lint_tool(tool("Tool1", properties={"q": {"type": "string"}}))
        keys = [(x.rule_id, x.path, x.message) for x in f]
        self.assertEqual(keys, sorted(keys))

    def test_finding_has_all_fields(self):
        f = lint_tool(tool("Tool1"))
        self.assertTrue(f)
        for x in f:
            self.assertTrue(x.rule_id and x.severity and x.path)
            self.assertTrue(x.message and x.fix)
            self.assertIn(x.severity, ("error", "warn", "info"))

    def test_dict_order_does_not_matter(self):
        props_a = {"b_prop": prop(description="Second property here."),
                   "a_prop": prop(description="First property here.")}
        props_b = {"a_prop": prop(description="First property here."),
                   "b_prop": prop(description="Second property here.")}
        fa = lint_tool(tool(properties=props_a))
        fb = lint_tool(tool(properties=props_b))
        self.assertEqual([x.to_dict() for x in fa],
                         [x.to_dict() for x in fb])

    def test_multiple_tools_indexed_in_path(self):
        tools = [tool("helios_ping"), tool("Tool2")]
        f = lint_tools(tools)
        paths = {x.path for x in f}
        self.assertTrue(any(p.startswith("$.tools[1]") for p in paths))
        self.assertFalse(any(p.startswith("$.tools[0]") for p in paths))

    def test_to_dict_round_trip(self):
        f = lint_tool(tool("Tool1"))
        d = f[0].to_dict()
        self.assertEqual(set(d), {"rule_id", "severity", "path", "message", "fix"})


if __name__ == "__main__":
    unittest.main()
