"""Tests for cli.py: lint/check/serve request handling."""
from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout

import cli
from fixtures import HELIOS_BAD, HELIOS_GOOD


def _write(tmpdir: str, name: str, obj) -> str:
    path = os.path.join(tmpdir, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)
    return path


class TestCli(unittest.TestCase):
    def test_lint_clean_prints_report_and_exits_zero(self):
        with tempfile.TemporaryDirectory() as td:
            p = _write(td, "good.json", HELIOS_GOOD)
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.main(["lint", p])
            self.assertEqual(code, 0)
            self.assertIn("0 finding", buf.getvalue())

    def test_lint_bad_prints_findings(self):
        with tempfile.TemporaryDirectory() as td:
            p = _write(td, "bad.json", HELIOS_BAD)
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.main(["lint", p])
            self.assertEqual(code, 0)
            self.assertIn("NAM-001", buf.getvalue())
            self.assertIn("fix:", buf.getvalue())

    def test_check_clean_exits_zero(self):
        with tempfile.TemporaryDirectory() as td:
            p = _write(td, "good.json", HELIOS_GOOD)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(["check", p]), 0)

    def test_check_errors_exits_two(self):
        with tempfile.TemporaryDirectory() as td:
            p = _write(td, "bad.json", HELIOS_BAD)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(["check", p]), 2)

    def test_check_warnings_only_exits_one(self):
        warn_only = {
            "name": "helios_status",
            "description": "Reports the Helios device status to the caller.",
            "parameters": {"type": "object", "properties": {
                "device_id": {"type": "string",
                              "description": "The device identifier to look up."}}},
        }
        with tempfile.TemporaryDirectory() as td:
            p = _write(td, "warn.json", warn_only)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(["check", p]), 1)

    def test_load_tools_accepts_tools_wrapper(self):
        with tempfile.TemporaryDirectory() as td:
            p = _write(td, "wrap.json", {"tools": [HELIOS_GOOD, HELIOS_GOOD]})
            self.assertEqual(len(cli.load_tools(p)), 2)

    def test_load_tools_accepts_list(self):
        with tempfile.TemporaryDirectory() as td:
            p = _write(td, "list.json", [HELIOS_GOOD])
            self.assertEqual(len(cli.load_tools(p)), 1)

    def test_load_tools_accepts_bare_schema(self):
        bare = {"type": "object", "properties": {}}
        with tempfile.TemporaryDirectory() as td:
            p = _write(td, "bare.json", bare)
            tools = cli.load_tools(p)
            self.assertEqual(tools[0]["name"], "(anonymous)")


class TestLintApi(unittest.TestCase):
    def test_handle_lint_request_tool_shape(self):
        status, payload = cli.handle_lint_request(
            json.dumps({"tool": HELIOS_BAD}).encode())
        self.assertEqual(status, 200)
        self.assertEqual(payload["tools"], 1)
        self.assertGreater(payload["summary"]["error"], 0)
        self.assertEqual(len(payload["findings"]),
                         payload["summary"]["error"]
                         + payload["summary"]["warn"]
                         + payload["summary"]["info"])

    def test_handle_lint_request_tools_shape(self):
        status, payload = cli.handle_lint_request(
            json.dumps({"tools": [HELIOS_GOOD]}).encode())
        self.assertEqual(status, 200)
        self.assertEqual(payload["findings"], [])

    def test_handle_lint_request_bad_json(self):
        status, payload = cli.handle_lint_request(b"not json{")
        self.assertEqual(status, 400)
        self.assertIn("error", payload)

    def test_handle_lint_request_wrong_shape(self):
        status, payload = cli.handle_lint_request(
            json.dumps({"hello": 1}).encode())
        self.assertEqual(status, 400)

    def test_finding_dicts_json_serializable(self):
        status, payload = cli.handle_lint_request(
            json.dumps({"tool": HELIOS_BAD}).encode())
        json.dumps(payload)  # must not raise


if __name__ == "__main__":
    unittest.main()
