#!/usr/bin/env python3
"""CLI for tool-schema-linter.

Subcommands:
  lint  FILE        human-readable report (always exits 0)
  check FILE        CI gate: exit 0 clean, 1 warnings, 2 errors
  demo              one-command end-to-end demo (asserts internally)
  serve [--port N]  tiny stdlib JSON API: POST /lint {tool|tools} -> findings

FILE is JSON: a single tool object {"name","description","parameters":{...}},
an object {"tools": [...]}, or a bare JSON Schema (linted anonymously).
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List, Tuple

from linter import Finding, lint_tool, lint_tools

Tool = Dict[str, Any]
DEFAULT_PORT = 8471


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------

def load_tools(path: str) -> List[Tool]:
    """Load one tool, {"tools": [...]}, or a bare schema from a JSON file."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and isinstance(data.get("tools"), list):
        return data["tools"]
    if isinstance(data, dict) and "parameters" in data:
        return [data]
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # bare JSON Schema: lint it anonymously
        return [{"name": "(anonymous)", "description": "(bare schema)",
                 "parameters": data}]
    raise SystemExit(f"error: {path} does not contain a tool schema")


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _counts(findings: List[Finding]) -> Tuple[int, int, int]:
    e = sum(1 for f in findings if f.severity == "error")
    w = sum(1 for f in findings if f.severity == "warn")
    i = sum(1 for f in findings if f.severity == "info")
    return e, w, i


def human_report(findings: List[Finding], n_tools: int) -> str:
    e, w, i = _counts(findings)
    lines = [f"tool-schema-linter: {n_tools} tool(s), "
             f"{len(findings)} finding(s): {e} error, {w} warn, {i} info"]
    for f in findings:
        lines.append(f"[{f.severity.upper():5}] {f.rule_id} {f.path}")
        lines.append(f"          {f.message}")
        lines.append(f"          fix: {f.fix}")
    if not findings:
        lines.append("clean: no findings.")
    return "\n".join(lines)


def exit_code_for(findings: List[Finding]) -> int:
    """CI gate: 0 = clean (info-only is clean), 1 = warnings, 2 = errors."""
    e, w, _ = _counts(findings)
    if e:
        return 2
    if w:
        return 1
    return 0


# ---------------------------------------------------------------------------
# serve: tiny stdlib JSON API
# ---------------------------------------------------------------------------

def handle_lint_request(body: bytes) -> Tuple[int, Dict[str, Any]]:
    """Core of POST /lint. Pure function (no sockets) so tests stay hermetic."""
    try:
        data = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        return 400, {"error": f"invalid JSON: {exc}"}
    if isinstance(data, dict) and isinstance(data.get("tools"), list):
        tools = data["tools"]
    elif isinstance(data, dict) and "parameters" in data:
        tools = [data]
    elif isinstance(data, dict) and "tool" in data and isinstance(data["tool"], dict):
        tools = [data["tool"]]
    else:
        return 400, {"error": "body must be {\"tool\": {...}} or {\"tools\": [...]}"}
    findings = lint_tools(tools)
    e, w, i = _counts(findings)
    return 200, {
        "tools": len(tools),
        "summary": {"error": e, "warn": w, "info": i},
        "findings": [f.to_dict() for f in findings],
    }


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:  # keep output quiet
        pass

    def _send(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802 (stdlib naming)
        if self.path != "/lint":
            self._send(404, {"error": "POST /lint only"})
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        status, payload = handle_lint_request(body)
        self._send(status, payload)

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        if self.path == "/health":
            self._send(200, {"ok": True, "service": "tool-schema-linter"})
        else:
            self._send(404, {"error": "try POST /lint or GET /health"})


def serve(port: int) -> None:
    server = HTTPServer(("127.0.0.1", port), _Handler)
    print(f"tool-schema-linter serving on http://127.0.0.1:{port} "
          f"(POST /lint, GET /health). Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cli.py",
                                description="Static lint for agent tool schemas.")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("lint", help="human-readable lint report")
    pl.add_argument("file", help="JSON file with tool schema(s)")

    pc = sub.add_parser("check", help="CI gate: exit 0/1/2")
    pc.add_argument("file", help="JSON file with tool schema(s)")

    sub.add_parser("demo", help="one-command end-to-end demo")

    ps = sub.add_parser("serve", help="tiny stdlib JSON API")
    ps.add_argument("--port", type=int, default=DEFAULT_PORT)
    return p


def main(argv: List[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "demo":
        import demo  # noqa: PLC0415
        demo.main()
        return 0
    if args.cmd == "serve":
        serve(args.port)
        return 0
    tools = load_tools(args.file)
    findings = lint_tools(tools)
    print(human_report(findings, len(tools)))
    if args.cmd == "check":
        return exit_code_for(findings)
    return 0


if __name__ == "__main__":
    sys.exit(main())
