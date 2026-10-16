"""Tests for the EX-* example rules."""
from __future__ import annotations

import unittest

from linter import lint_tool
from tests.helpers import by_rule, prop, rule_ids, tool


class TestExamples(unittest.TestCase):
    def test_missing_examples_warns(self):
        bad = {"type": "string", "description": "A proper description here."}
        f = lint_tool(tool(properties={"device_id": bad}))
        hit = by_rule(f, "EX-001")
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0].severity, "warn")

    def test_empty_examples_warns(self):
        bad = prop(examples=[])
        f = lint_tool(tool(properties={"device_id": bad}))
        self.assertIn("EX-001", rule_ids(f))

    def test_matching_example_passes(self):
        f = lint_tool(tool(properties={"count": prop(type="integer", examples=[3])}))
        for rid in ("EX-001", "EX-002", "EX-003"):
            self.assertNotIn(rid, rule_ids(f))

    def test_wrong_type_example_errors(self):
        bad = prop(type="integer", examples=["three"])
        f = lint_tool(tool(properties={"count": bad}))
        hit = by_rule(f, "EX-002")
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0].severity, "error")

    def test_bool_is_not_integer_example(self):
        bad = prop(type="integer", examples=[True])
        f = lint_tool(tool(properties={"count": bad}))
        self.assertIn("EX-002", rule_ids(f))

    def test_integer_ok_for_number_type(self):
        ok = prop(type="number", examples=[3])
        f = lint_tool(tool(properties={"amount": ok}))
        self.assertNotIn("EX-002", rule_ids(f))

    def test_example_outside_enum_errors(self):
        bad = prop(type="string", enum=["a", "b"], examples=["z"],
                   description="Pick a or b for the mode.")
        f = lint_tool(tool(properties={"mode": bad}))
        self.assertIn("EX-002", rule_ids(f))

    def test_enum_fully_covered_passes(self):
        ok = prop(type="string", enum=["standard", "express"],
                  examples=["standard", "express"],
                  description="Delivery speed choice.")
        f = lint_tool(tool(properties={"speed": ok}))
        self.assertNotIn("EX-003", rule_ids(f))

    def test_enum_covered_by_description_passes(self):
        ok = prop(type="string", enum=["standard", "express"],
                  examples=["standard"],
                  description="Delivery speed: standard or express.")
        f = lint_tool(tool(properties={"speed": ok}))
        self.assertNotIn("EX-003", rule_ids(f))

    def test_uncovered_enum_value_is_info(self):
        bad = prop(type="string", enum=["a", "b", "c"], examples=["a"],
                   description="The mode selector.")
        f = lint_tool(tool(properties={"mode": bad}))
        hit = by_rule(f, "EX-003")
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0].severity, "info")
        self.assertIn("b", hit[0].message)

    def test_oneof_example_matching_branch_passes(self):
        ok = prop(oneOf=[{"type": "string"}, {"type": "null"}],
                  description="Identifier that may be null.",
                  examples=["id-1"])
        ok.pop("type")
        f = lint_tool(tool(properties={"uid": ok}))
        self.assertNotIn("EX-002", rule_ids(f))


if __name__ == "__main__":
    unittest.main()
