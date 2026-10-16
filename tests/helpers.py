"""Shared test helpers: tiny schema builders."""
from __future__ import annotations

from typing import Any, Dict, List

from linter import Finding, lint_tool


def prop(**kwargs: Any) -> Dict[str, Any]:
    """A well-formed property: described, with a matching example."""
    base: Dict[str, Any] = {
        "type": "string",
        "description": "A well-formed property description.",
        "examples": ["sample-value"],
    }
    base.update(kwargs)
    return base


def tool(name: str = "helios_ping", properties: Dict[str, Any] | None = None,
         required: List[str] | None = None,
         description: str = "Pings the Helios device and returns status.",
         extra_params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    params: Dict[str, Any] = {"type": "object", "properties": properties or {}}
    if required:
        params["required"] = required
    if extra_params:
        params.update(extra_params)
    return {"name": name, "description": description, "parameters": params}


def rule_ids(findings: List[Finding]) -> List[str]:
    return [f.rule_id for f in findings]


def by_rule(findings: List[Finding], rule_id: str) -> List[Finding]:
    return [f for f in findings if f.rule_id == rule_id]
