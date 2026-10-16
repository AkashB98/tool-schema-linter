#!/usr/bin/env python3
"""One-command end-to-end demo for tool-schema-linter.

Fully offline on the fictional Helios Home / Helios Cloud fixtures.
Each stage asserts what it expects, so the demo doubles as a smoke test:

  1. the clean Helios Cloud tool lints with zero findings
  2. the sloppy Helios Home tool triggers every rule family
  3. `check` maps findings to the right CI exit codes (0 / 1 / 2)
  4. the /lint HTTP API round-trips a schema (live local server)
  5. linting is deterministic (two runs, byte-identical)
"""

from __future__ import annotations

import http.client
import json
import os
import tempfile
import threading

import cli
from fixtures import HELIOS_BAD, HELIOS_GOOD
from linter import lint_tool


def _here(*parts: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), *parts)


def main() -> None:
    # 1. clean fixture: zero findings
    good = lint_tool(HELIOS_GOOD)
    assert good == [], f"expected 0 findings, got {len(good)}: {good[:3]}"
    print(f"1. helios_place_order (Helios Cloud): clean, {len(good)} findings")

    # 2. sloppy fixture: every rule family fires
    bad = lint_tool(HELIOS_BAD)
    families = {f.rule_id.split("-")[0] for f in bad}
    assert families == {"NAM", "DESC", "EX", "REQ", "SML", "RISK"}, families
    ids = {f.rule_id for f in bad}
    for must in ("NAM-001", "DESC-001", "EX-002", "REQ-001", "REQ-003",
                 "SML-002", "RISK-001"):
        assert must in ids, f"expected {must} to fire"
    n_err = sum(1 for f in bad if f.severity == "error")
    print(f"2. Tool1 (Helios Home): {len(bad)} findings "
          f"({n_err} errors), all 6 rule families fire")

    # 3. check exit codes: 0 clean / 1 warnings / 2 errors
    with tempfile.TemporaryDirectory() as td:
        good_path = os.path.join(td, "good.json")
        bad_path = os.path.join(td, "bad.json")
        with open(good_path, "w") as fh:
            json.dump(HELIOS_GOOD, fh)
        with open(bad_path, "w") as fh:
            json.dump(HELIOS_BAD, fh)
        assert cli.main(["check", good_path]) == 0
        assert cli.main(["check", bad_path]) == 2
        warn_only = {
            "name": "helios_status",
            "description": "Reports the Helios device status to the caller.",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "The device identifier to look up.",
                    },
                },
            },
        }
        warn_path = os.path.join(td, "warn.json")
        with open(warn_path, "w") as fh:
            json.dump(warn_only, fh)
        assert cli.main(["check", warn_path]) == 1
    print("3. check exit codes: 0 (clean) / 1 (warnings) / 2 (errors) -- ok")

    # 4. live /lint API round-trip (localhost only)
    from http.server import HTTPServer  # noqa: PLC0415
    server = HTTPServer(("127.0.0.1", 0), cli._Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        body = json.dumps({"tool": HELIOS_BAD}).encode()
        conn.request("POST", "/lint", body=body,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        payload = json.loads(resp.read().decode())
        assert resp.status == 200, resp.status
        assert payload["summary"]["error"] == n_err, payload["summary"]
        assert len(payload["findings"]) == len(bad)
    finally:
        server.shutdown()
        thread.join()
    print(f"4. POST /lint round-trip: {len(bad)} findings served as JSON -- ok")

    # 5. determinism: byte-identical across runs
    run1 = json.dumps([f.to_dict() for f in lint_tool(HELIOS_BAD)], sort_keys=True)
    run2 = json.dumps([f.to_dict() for f in lint_tool(HELIOS_BAD)], sort_keys=True)
    assert run1 == run2
    print("5. determinism: two runs byte-identical -- ok")

    print("\ndemo passed: lint the schema before the agent ever touches the tools.")


if __name__ == "__main__":
    main()
