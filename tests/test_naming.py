"""Tests for the NAM-* naming rules."""
from __future__ import annotations

import unittest

from linter import lint_tool
from tests.helpers import by_rule, prop, rule_ids, tool


class TestToolNaming(unittest.TestCase):
    def test_good_snake_name_passes(self):
        f = lint_tool(tool("helios_place_order"))
        self.assertNotIn("NAM-001", rule_ids(f))
        self.assertNotIn("NAM-002", rule_ids(f))

    def test_camelcase_name_fires(self):
        f = lint_tool(tool("heliosPlaceOrder"))
        hit = by_rule(f, "NAM-001")
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0].severity, "error")
        self.assertEqual(hit[0].path, "$.tools[0].name")

    def test_uppercase_name_fires(self):
        f = lint_tool(tool("HELIOS_PING"))
        self.assertIn("NAM-001", rule_ids(f))

    def test_name_with_dash_fires(self):
        f = lint_tool(tool("helios-ping"))
        self.assertIn("NAM-001", rule_ids(f))

    def test_generic_name_warns(self):
        f = lint_tool(tool("tool1"))
        hit = by_rule(f, "NAM-002")
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0].severity, "warn")

    def test_generic_fn_warns(self):
        f = lint_tool(tool("helper"))
        self.assertIn("NAM-002", rule_ids(f))

    def test_malformed_name_reports_nam001_not_nam002(self):
        # "Tool1" is both non-snake and generic: only the structural rule fires
        f = lint_tool(tool("Tool1"))
        self.assertIn("NAM-001", rule_ids(f))
        self.assertNotIn("NAM-002", rule_ids(f))


class TestParamNaming(unittest.TestCase):
    def test_good_param_name_passes(self):
        f = lint_tool(tool(properties={"device_id": prop()}))
        self.assertNotIn("NAM-003", rule_ids(f))
        self.assertNotIn("NAM-004", rule_ids(f))

    def test_camelcase_param_fires(self):
        f = lint_tool(tool(properties={"deviceId": prop()}))
        hit = by_rule(f, "NAM-003")
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0].severity, "error")

    def test_single_letter_param_warns(self):
        f = lint_tool(tool(properties={"q": prop()}))
        hit = by_rule(f, "NAM-004")
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0].severity, "warn")

    def test_documented_single_letters_pass(self):
        f = lint_tool(tool(properties={"x": prop(), "y": prop()}))
        self.assertNotIn("NAM-004", rule_ids(f))

    def test_nested_param_naming_checked(self):
        f = lint_tool(tool(properties={
            "address": {"type": "object",
                        "description": "Where to ship the order.",
                        "examples": [{}],
                        "properties": {"zipCode": prop()},
                        "additionalProperties": False},
        }))
        hit = by_rule(f, "NAM-003")
        self.assertEqual(len(hit), 1)
        self.assertTrue(hit[0].path.endswith("properties.zipCode"))


if __name__ == "__main__":
    unittest.main()
