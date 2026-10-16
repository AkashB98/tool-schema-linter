"""Tests for the DESC-* description rules."""
from __future__ import annotations

import unittest

from linter import lint_tool
from tests.helpers import by_rule, prop, rule_ids, tool


class TestDescriptions(unittest.TestCase):
    def test_missing_tool_description_fires(self):
        f = lint_tool(tool(description=""))
        hit = by_rule(f, "DESC-001")
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0].severity, "error")

    def test_missing_property_description_fires(self):
        bad = {"type": "string", "examples": ["x"]}
        f = lint_tool(tool(properties={"device_id": bad}))
        hit = by_rule(f, "DESC-002")
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0].severity, "error")

    def test_good_descriptions_pass(self):
        f = lint_tool(tool(properties={"device_id": prop()}))
        for rid in ("DESC-001", "DESC-002", "DESC-003", "DESC-004", "DESC-005"):
            self.assertNotIn(rid, rule_ids(f))

    def test_short_description_warns(self):
        bad = prop(description="The mode.")
        f = lint_tool(tool(properties={"mode": bad}))
        hit = by_rule(f, "DESC-003")
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0].severity, "warn")

    def test_boundary_length_ok(self):
        # exactly 12 chars must NOT fire DESC-003
        ok = prop(description="123456789012")
        f = lint_tool(tool(properties={"mode": ok}))
        self.assertNotIn("DESC-003", rule_ids(f))

    def test_placeholder_todo_fires(self):
        bad = prop(description="TODO: write this later")
        f = lint_tool(tool(properties={"mode": bad}))
        hit = by_rule(f, "DESC-004")
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0].severity, "error")

    def test_placeholder_fixme_fires(self):
        bad = prop(description="FIXME broken")
        f = lint_tool(tool(properties={"mode": bad}))
        self.assertIn("DESC-004", rule_ids(f))

    def test_placeholder_description_here_fires(self):
        bad = prop(description="Enter description here")
        f = lint_tool(tool(properties={"mode": bad}))
        self.assertIn("DESC-004", rule_ids(f))

    def test_placeholder_wins_over_short(self):
        # "TODO" is both a placeholder and <12 chars: one finding, DESC-004
        bad = prop(description="TODO")
        f = lint_tool(tool(properties={"mode": bad}))
        self.assertIn("DESC-004", rule_ids(f))
        self.assertNotIn("DESC-003", rule_ids(f))

    def test_legit_description_mentioning_todo_noun_ok(self):
        ok = prop(description="Runs the todo-list sync for the device.")
        f = lint_tool(tool(properties={"mode": ok}))
        self.assertNotIn("DESC-004", rule_ids(f))

    def test_duplicate_descriptions_warn(self):
        p1 = prop(description="Identifier string.")
        p2 = prop(description="Identifier string.")
        f = lint_tool(tool(properties={"dup_a": p1, "dup_b": p2}))
        hit = by_rule(f, "DESC-005")
        self.assertEqual(len(hit), 1)  # only the second occurrence
        self.assertEqual(hit[0].severity, "warn")
        self.assertTrue(hit[0].path.endswith("dup_b.description"))

    def test_unique_descriptions_pass(self):
        f = lint_tool(tool(properties={
            "dup_a": prop(description="First identifier string."),
            "dup_b": prop(description="Second identifier string."),
        }))
        self.assertNotIn("DESC-005", rule_ids(f))

    def test_duplicate_detection_case_insensitive(self):
        p1 = prop(description="Identifier STRING.")
        p2 = prop(description="identifier string.")
        f = lint_tool(tool(properties={"a": p1, "b": p2}))
        self.assertIn("DESC-005", rule_ids(f))


if __name__ == "__main__":
    unittest.main()
