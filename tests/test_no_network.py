"""No-network enforcement: core flows work with sockets stubbed out.

We stub socket.socket and socket.create_connection to raise, then run the
linter, fixtures, CLI report paths, and the /lint request handler. The live
server smoke test lives in demo.py instead (localhost, manual run).
"""
from __future__ import annotations

import json
import socket
import unittest
from unittest import mock

import cli
import demo  # noqa: F401  (import only; demo.main runs the live server)
from fixtures import HELIOS_BAD, HELIOS_GOOD
from linter import lint_tool


def _raising_socket(*args, **kwargs):
    raise AssertionError("network socket used during hermetic test")


class TestNoNetwork(unittest.TestCase):
    def setUp(self):
        self._sock = mock.patch.object(socket, "socket", _raising_socket)
        self._conn = mock.patch.object(socket, "create_connection", _raising_socket)
        self._sock.start()
        self._conn.start()

    def tearDown(self):
        self._sock.stop()
        self._conn.stop()

    def test_lint_good_offline(self):
        self.assertEqual(lint_tool(HELIOS_GOOD), [])

    def test_lint_bad_offline(self):
        findings = lint_tool(HELIOS_BAD)
        self.assertGreater(len(findings), 20)
        self.assertTrue(all(f.fix for f in findings))

    def test_lint_api_handler_offline(self):
        status, payload = cli.handle_lint_request(
            json.dumps({"tool": HELIOS_BAD}).encode())
        self.assertEqual(status, 200)
        self.assertGreater(len(payload["findings"]), 20)

    def test_exit_code_mapping_offline(self):
        self.assertEqual(cli.exit_code_for([]), 0)
        self.assertEqual(cli.exit_code_for(lint_tool(HELIOS_BAD)), 2)


if __name__ == "__main__":
    unittest.main()
