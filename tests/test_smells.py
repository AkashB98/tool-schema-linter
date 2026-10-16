"""Tests for the SML-* schema smell rules."""
from __future__ import annotations

import unittest

from linter import lint_tool
from tests.helpers import by_rule, prop, rule_ids, tool


class TestSmells(unittest.TestCase):
    def test_untyped_object_warns(self):
        bad = {"type": "object", "description": "A blob of stuff."}
        f = lint_tool(tool(properties={"blob": bad}))
        hit = by_rule(f, "SML-001")
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0].severity, "warn")

    def test_typed_object_passes(self):
        ok = {"type": "object", "description": "Shipping address block.",
              "additionalProperties": False,
              "properties": {"street": prop()},
              "examples": [{"street": "x"}]}
        f = lint_tool(tool(properties={"address": ok}))
        self.assertNotIn("SML-001", rule_ids(f))

    def test_array_without_items_errors(self):
        bad = prop(type="array", examples=[[1, 2]],
                   description="List of identifiers.")
        f = lint_tool(tool(properties={"ids": bad}))
        hit = by_rule(f, "SML-002")
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0].severity, "error")

    def test_array_with_items_passes(self):
        ok = prop(type="array", items={"type": "integer"},
                  examples=[[1, 2]], description="List of identifiers.")
        f = lint_tool(tool(properties={"ids": ok}))
        self.assertNotIn("SML-002", rule_ids(f))

    def test_additional_properties_unset_is_info(self):
        bad = {"type": "object", "description": "Metadata bag.",
               "properties": {"source": prop()},
               "examples": [{"source": "web"}]}
        f = lint_tool(tool(properties={"meta": bad}))
        hit = by_rule(f, "SML-003")
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0].severity, "info")

    def test_additional_properties_set_passes(self):
        ok = {"type": "object", "description": "Metadata bag.",
              "additionalProperties": False,
              "properties": {"source": prop()},
              "examples": [{"source": "web"}]}
        f = lint_tool(tool(properties={"meta": ok}))
        self.assertNotIn("SML-003", rule_ids(f))

    def test_anyof_without_discriminator_warns(self):
        bad = {"anyOf": [{"type": "string"}, {"type": "integer"}],
               "description": "Pick a string or an integer.",
               "examples": ["seven"]}
        f = lint_tool(tool(properties={"choice": bad}))
        hit = by_rule(f, "SML-004")
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0].severity, "warn")

    def test_anyof_with_discriminator_passes(self):
        ok = {"anyOf": [{"type": "string"}, {"type": "integer"}],
              "discriminator": {"propertyName": "kind"},
              "description": "Pick a string or an integer.",
              "examples": ["seven"]}
        f = lint_tool(tool(properties={"choice": ok}))
        self.assertNotIn("SML-004", rule_ids(f))

    def test_nullable_oneof_does_not_fire_discriminator_rule(self):
        # nullable idiom is REQ-004's job, not SML-004's
        bad = {"oneOf": [{"type": "string"}, {"type": "null"}],
               "description": "Identifier that may be null.",
               "examples": ["id-1"]}
        f = lint_tool(tool(properties={"uid": bad}))
        self.assertNotIn("SML-004", rule_ids(f))

    def test_unknown_format_warns(self):
        bad = prop(format="email-address")
        f = lint_tool(tool(properties={"contact": bad}))
        hit = by_rule(f, "SML-005")
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0].severity, "warn")

    def test_known_formats_pass(self):
        for fmt in ("date-time", "uuid", "email", "uri", "ipv4"):
            ok = prop(format=fmt)
            f = lint_tool(tool(properties={"contact": ok}))
            self.assertNotIn("SML-005", rule_ids(f), fmt)

    def test_pattern_without_example_warns(self):
        bad = {"type": "string", "pattern": "^[0-9]{5}$",
               "description": "Five-digit ZIP code."}
        f = lint_tool(tool(properties={"zip_code": bad}))
        hit = by_rule(f, "SML-006")
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0].severity, "warn")

    def test_pattern_with_valid_example_passes(self):
        ok = {"type": "string", "pattern": "^[0-9]{5}$",
              "description": "Five-digit ZIP code.",
              "examples": ["75201"]}
        f = lint_tool(tool(properties={"zip_code": ok}))
        self.assertNotIn("SML-006", rule_ids(f))

    def test_pattern_with_bad_example_warns(self):
        bad = {"type": "string", "pattern": "^[0-9]{5}$",
               "description": "Five-digit ZIP code.",
               "examples": ["abc"]}
        f = lint_tool(tool(properties={"zip_code": bad}))
        self.assertIn("SML-006", rule_ids(f))

    def test_ref_is_info_not_error(self):
        bad = {"$ref": "#/defs/address",
               "description": "Address reference."}
        f = lint_tool(tool(properties={"address_ref": bad}))
        hit = by_rule(f, "SML-007")
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0].severity, "info")

    def test_pattern_properties_is_info(self):
        bad = {"type": "object",
               "patternProperties": {"^x-": {"type": "string"}},
               "description": "Custom labels.",
               "examples": [{"x-team": "ops"}]}
        f = lint_tool(tool(properties={"labels": bad}))
        self.assertIn("SML-007", rule_ids(f))
        # patternProperties counts as the constraint: no SML-001 on top
        self.assertNotIn("SML-001", rule_ids(f))


if __name__ == "__main__":
    unittest.main()
