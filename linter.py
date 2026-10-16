#!/usr/bin/env python3
"""tool-schema-linter: static lint for agent tool schemas.

A tool schema is the JSON Schema describing one agent tool (its name,
description, and parameter object). Sloppy schemas make LLMs (large language
models) misuse tools: missing descriptions lead to hallucinated arguments,
untyped arrays crash runtimes, undocumented optionality breaks required-field
contracts. This linter catches those contract smells statically, before any
agent ever touches the tools.

Deterministic: every lint run returns findings sorted by
(rule_id, path, message), with no dependence on dict iteration order.

Rule families:
  NAM-*  naming (tool + parameter names)
  DESC-* descriptions (presence, length, placeholders, copy-paste repeats)
  EX-*   examples (presence, type-correctness, enum coverage)
  REQ-*  required-vs-optional hygiene
  SML-*  schema smells (untyped objects, missing items, formats, patterns...)
  RISK-* risky names without the documented "sensitive" marker
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

Tool = Dict[str, Any]
Schema = Dict[str, Any]


@dataclass(frozen=True)
class Finding:
    """One lint finding. severity is one of: error | warn | info."""

    rule_id: str
    severity: str
    path: str  # JSONPath-ish, e.g. $.tools[0].parameters.properties.qty
    message: str
    fix: str  # suggested fix

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SNAKE_RE = re.compile(r"^[a-z][a-z0-9_]*$")

GENERIC_TOOL_NAMES = frozenset(
    {
        "tool", "tool1", "tool2", "fn", "func", "function", "helper",
        "utils", "util", "test", "demo", "do", "run", "execute",
        "process", "handler", "main", "thing", "stuff", "wrapper",
    }
)

# Bare single-letter parameter names allowed because they are documented,
# conventional coordinate names. Every other single letter is a smell.
DOCUMENTED_SINGLE_LETTERS = frozenset({"x", "y"})

MIN_DESCRIPTION_LEN = 12

PLACEHOLDER_PATTERNS = (
    # (?<![\w-]) / (?![\w-]): "todo" inside "todo-list" is a feature name,
    # not a placeholder -- hyphens disqualify the match.
    re.compile(r"(?<![\w-])(todo|fixme|xxx|tbd|to-do)(?![\w-])", re.IGNORECASE),
    re.compile(r"description here", re.IGNORECASE),
    re.compile(r"lorem ipsum", re.IGNORECASE),
    re.compile(r"fill (this|me) in", re.IGNORECASE),
    re.compile(r"your (description|text) here", re.IGNORECASE),
)

# Fires only when the description claims THIS parameter is optional/nullable.
# Bare noun mentions ("toggles the 'optional' extras pack") must NOT fire.
OPTIONAL_CLAIM_PATTERNS = (
    # (?:as\s+)? -- the whole word "as" is optional, so both
    # "is optional" and "marked as optional" match.
    re.compile(r"\b(is|are|was|were|will be|marked?|treated|considered)\s+(?:as\s+)?optional\b", re.IGNORECASE),
    re.compile(r"\(optional\)", re.IGNORECASE),
    re.compile(r"\boptional\s+(parameter|argument|field|input|flag|property|value|attribute)\b", re.IGNORECASE),
    re.compile(r"\bcan\s+be\s+(null|omitted|left\s+out|skipped)\b", re.IGNORECASE),
    re.compile(r"\bmay\s+be\s+null\b", re.IGNORECASE),
    re.compile(r"\bnot\s+required\b", re.IGNORECASE),
    re.compile(r"\bnullable\b", re.IGNORECASE),
)

KNOWN_FORMATS = frozenset(
    {
        "date", "time", "date-time", "duration",
        "email", "idn-email", "hostname", "idn-hostname",
        "ipv4", "ipv6", "uuid",
        "uri", "uri-reference", "uri-template", "url", "iri", "iri-reference",
        "json-pointer", "relative-json-pointer", "regex",
        "int32", "int64", "float", "double", "byte", "binary", "password",
    }
)

# Property names that suggest destructive or secret-handling behavior.
# Such properties must carry the documented "sensitive": true marker.
DANGER_NAME_RE = re.compile(
    r"^(delete|remove|destroy|purge|wipe|drop|erase)"
    r"|password|secret|api[_-]?key|private[_-]?key|\btoken\b|\$env",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _type_of(value: Any) -> str:
    """JSON Schema type name for a Python value (bool before int!)."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "unknown"


def _declared_types(schema: Schema) -> List[str]:
    """Type names declared by a schema ("type" may be a string or a list)."""
    t = schema.get("type")
    if t is None:
        return []
    return [t] if isinstance(t, str) else list(t)


def _example_matches_type(schema: Schema, example: Any) -> bool:
    """Top-level type check of one example against its schema."""
    declared = _declared_types(schema)
    if not declared:
        return True  # untyped: nothing to check against
    actual = _type_of(example)
    if actual == "integer" and "number" in declared:
        return True  # JSON Schema: integers are valid numbers
    if actual in declared:
        return True
    if actual == "null" and any(b.get("type") == "null" for b in schema.get("oneOf", []) + schema.get("anyOf", [])):
        return True
    # oneOf/anyOf: example is fine if it matches any branch's declared type
    for branch in schema.get("oneOf", []) + schema.get("anyOf", []):
        if isinstance(branch, dict) and _example_matches_type(branch, example):
            return True
    return False


def _has_null_branch(schema: Schema) -> bool:
    """True if schema allows null via oneOf/anyOf branch or type list."""
    if "null" in _declared_types(schema):
        return True
    for branch in schema.get("oneOf", []) + schema.get("anyOf", []):
        if isinstance(branch, dict) and "null" in _declared_types(branch):
            return True
    return False


def _iter_subschemas(schema: Schema, base_path: str):
    """Yield (path, subschema) for every nested property / item / branch.

    Sorted by path so traversal order is deterministic regardless of the
    input dict's insertion order.
    """
    if not isinstance(schema, dict):
        return
    for key in ("properties",):
        props = schema.get(key)
        if isinstance(props, dict):
            for name in sorted(props):
                sub = props[name]
                path = f"{base_path}.{key}.{name}"
                yield path, sub
                yield from _iter_subschemas(sub, path)
    items = schema.get("items")
    if isinstance(items, dict):
        path = f"{base_path}.items"
        yield path, items
        yield from _iter_subschemas(items, path)
    for comb in ("anyOf", "oneOf"):
        branches = schema.get(comb)
        if isinstance(branches, list):
            for i, branch in enumerate(branches):
                if isinstance(branch, dict):
                    path = f"{base_path}.{comb}[{i}]"
                    yield path, branch
                    yield from _iter_subschemas(branch, path)


def _parameters_schema(tool: Tool) -> Tuple[Schema, str]:
    """Return (parameters schema dict, parameters path)."""
    params = tool.get("parameters")
    if isinstance(params, dict):
        return params, "$.TOOL.parameters"
    return {}, "$.TOOL.parameters"


# ---------------------------------------------------------------------------
# Rule family 1: naming
# ---------------------------------------------------------------------------

def _rule_naming(tools: List[Tool]) -> List[Finding]:
    out: List[Finding] = []
    for i, tool in enumerate(tools):
        base = f"$.tools[{i}]"
        name = tool.get("name", "")
        if not isinstance(name, str) or not SNAKE_RE.match(name):
            out.append(Finding(
                "NAM-001", "error", f"{base}.name",
                f"tool name {name!r} is not snake_case/lowercase",
                "rename to lowercase snake_case, e.g. 'helios_place_order'"))
        elif name in GENERIC_TOOL_NAMES:
            out.append(Finding(
                "NAM-002", "warn", f"{base}.name",
                f"tool name {name!r} is generic and non-descriptive",
                "use a name that says what the tool does, e.g. 'helios_place_order'"))
        params, params_path = _parameters_schema(tool)
        ppath = params_path.replace("$.TOOL", base)
        for path, sub in _iter_subschemas(params, ppath):
            m = re.search(r"\.properties\.([^\.]+)$", path)
            if not m:
                continue
            pname = m.group(1)
            if not SNAKE_RE.match(pname):
                out.append(Finding(
                    "NAM-003", "error", path,
                    f"parameter name {pname!r} is not snake_case/lowercase",
                    "rename to lowercase snake_case"))
            elif len(pname) == 1 and pname not in DOCUMENTED_SINGLE_LETTERS:
                out.append(Finding(
                    "NAM-004", "warn", path,
                    f"bare single-letter parameter name {pname!r}",
                    "use a descriptive name (documented exceptions: x, y)"))
    return out


# ---------------------------------------------------------------------------
# Rule family 2: descriptions
# ---------------------------------------------------------------------------

def _rule_descriptions(tools: List[Tool]) -> List[Finding]:
    out: List[Finding] = []
    for i, tool in enumerate(tools):
        base = f"$.tools[{i}]"
        seen: Dict[str, List[str]] = {}  # normalized description -> paths
        desc = tool.get("description")
        if not isinstance(desc, str) or not desc.strip():
            out.append(Finding(
                "DESC-001", "error", f"{base}.description",
                "tool has no description",
                "write one sentence saying what the tool does and when to use it"))
        params, params_path = _parameters_schema(tool)
        ppath = params_path.replace("$.TOOL", base)
        for path, sub in _iter_subschemas(params, ppath):
            m = re.search(r"\.properties\.([^\.]+)$", path)
            if not m or not isinstance(sub, dict):
                continue
            d = sub.get("description")
            dpath = f"{path}.description"
            if not isinstance(d, str) or not d.strip():
                out.append(Finding(
                    "DESC-002", "error", dpath,
                    f"parameter {m.group(1)!r} has no description",
                    "describe what the parameter means and what values it takes"))
                continue
            if any(p.search(d) for p in PLACEHOLDER_PATTERNS):
                out.append(Finding(
                    "DESC-004", "error", dpath,
                    f"parameter {m.group(1)!r} description looks like a placeholder",
                    "replace the placeholder with a real description"))
            elif len(d.strip()) < MIN_DESCRIPTION_LEN:
                out.append(Finding(
                    "DESC-003", "warn", dpath,
                    f"parameter {m.group(1)!r} description is very short "
                    f"({len(d.strip())} chars < {MIN_DESCRIPTION_LEN})",
                    "write at least one full sentence"))
            seen.setdefault(" ".join(d.split()).lower(), []).append(dpath)
    # copy-paste repeats: same description text on multiple properties
    for text, paths in seen.items():
        if len(paths) > 1:
            for dup in sorted(paths)[1:]:
                out.append(Finding(
                    "DESC-005", "warn", dup,
                    f"description is copy-pasted from another parameter ({text[:40]!r}...)",
                    "write a description specific to this parameter"))
    return out


# ---------------------------------------------------------------------------
# Rule family 3: examples
# ---------------------------------------------------------------------------

def _rule_examples(tools: List[Tool]) -> List[Finding]:
    out: List[Finding] = []
    for i, tool in enumerate(tools):
        base = f"$.tools[{i}]"
        params, params_path = _parameters_schema(tool)
        ppath = params_path.replace("$.TOOL", base)
        for path, sub in _iter_subschemas(params, ppath):
            m = re.search(r"\.properties\.([^\.]+)$", path)
            if not m or not isinstance(sub, dict):
                continue
            pname = m.group(1)
            examples = sub.get("examples")
            enum = sub.get("enum")
            if not isinstance(examples, list) or not examples:
                out.append(Finding(
                    "EX-001", "warn", path,
                    f"parameter {pname!r} has no examples",
                    "add an 'examples' array with 1-3 realistic values"))
                continue
            for ex in examples:
                if not _example_matches_type(sub, ex):
                    out.append(Finding(
                        "EX-002", "error", path,
                        f"example {ex!r} does not match the schema type "
                        f"({_type_of(ex)} vs {_declared_types(sub) or 'untyped'})",
                        "fix the example or the declared type"))
                elif isinstance(enum, list) and ex not in enum:
                    out.append(Finding(
                        "EX-002", "error", path,
                        f"example {ex!r} is not one of the enum values {enum}",
                        "use a value from the enum, or widen the enum"))
            if isinstance(enum, list):
                desc = sub.get("description") or ""
                covered = [v for v in enum
                           if v in examples or str(v) in str(desc)]
                if len(covered) < len(enum):
                    missing = [v for v in enum if v not in covered]
                    out.append(Finding(
                        "EX-003", "info", path,
                        f"enum values {missing} never appear in an example or the description",
                        "show every enum value in an example so the model sees the full range"))
    return out


# ---------------------------------------------------------------------------
# Rule family 4: required-vs-optional hygiene
# ---------------------------------------------------------------------------

def _check_required_block(required: Any, properties: Any,
                        req_path: str, props_base: str,
                        out: List[Finding]) -> None:
    """Apply REQ-001..REQ-004 to one required/properties block."""
    if not isinstance(required, list):
        required = []
    if not isinstance(properties, dict):
        properties = {}
    for rname in sorted(set(str(r) for r in required)):
        if rname not in properties:
            out.append(Finding(
                "REQ-001", "error", req_path,
                f"required {rname!r} is not declared in properties",
                "add the property, or remove it from 'required'"))
            continue
        sub = properties[rname]
        if not isinstance(sub, dict):
            continue
        prop_path = f"{props_base}.{rname}"
        if "default" in sub:
            out.append(Finding(
                "REQ-003", "error", prop_path,
                f"parameter {rname!r} is required but has a default "
                f"({sub['default']!r})",
                "either drop 'required' (it is optional) or drop 'default'"))
        desc = sub.get("description") or ""
        if isinstance(desc, str) and any(p.search(desc) for p in OPTIONAL_CLAIM_PATTERNS):
            out.append(Finding(
                "REQ-002", "warn", prop_path,
                f"parameter {rname!r} is required but its description "
                f"claims it is optional/nullable",
                "decide: optional (remove from 'required') or truly required (fix the description)"))
        if _has_null_branch(sub):
            out.append(Finding(
                "REQ-004", "warn", prop_path,
                f"parameter {rname!r} is required but allows null via a "
                f"nullable oneOf/anyOf branch",
                "either make it optional-with-default, or drop the null branch"))


def _rule_required(tools: List[Tool]) -> List[Finding]:
    out: List[Finding] = []
    for i, tool in enumerate(tools):
        base = f"$.tools[{i}]"
        params, params_path = _parameters_schema(tool)
        ppath = params_path.replace("$.TOOL", base)
        # top-level parameters block
        _check_required_block(params.get("required"), params.get("properties"),
                              f"{ppath}.required", f"{ppath}.properties", out)
        # nested object blocks (e.g. $.parameters.properties.address.required)
        for path, sub in _iter_subschemas(params, ppath):
            if isinstance(sub, dict) and "required" in sub and "properties" in sub:
                _check_required_block(sub.get("required"), sub.get("properties"),
                                      f"{path}.required", f"{path}.properties", out)
    return out


# ---------------------------------------------------------------------------
# Rule family 5: schema smells
# ---------------------------------------------------------------------------

def _rule_smells(tools: List[Tool]) -> List[Finding]:
    out: List[Finding] = []
    for i, tool in enumerate(tools):
        base = f"$.tools[{i}]"
        params, params_path = _parameters_schema(tool)
        ppath = params_path.replace("$.TOOL", base)
        for path, sub in _iter_subschemas(params, ppath):
            if not isinstance(sub, dict):
                continue
            declared = _declared_types(sub)
            # SML-007: honest scope limits
            if "$ref" in sub:
                out.append(Finding(
                    "SML-007", "info", path,
                    "$ref is not resolved by this linter",
                    "inline the referenced schema (or note it as a known scope limit)"))
            if "patternProperties" in sub:
                out.append(Finding(
                    "SML-007", "info", path,
                    "patternProperties constraints are not analyzed by this linter",
                    "add an explicit example showing the expected key shape"))
            # SML-001: untyped object
            if "object" in declared and not sub.get("properties") \
                    and "patternProperties" not in sub:
                out.append(Finding(
                    "SML-001", "warn", path,
                    "type 'object' with no 'properties' is opaque to the model",
                    "declare the properties, or use additionalProperties with a typed schema"))
            # SML-002: array without items
            if "array" in declared and "items" not in sub:
                out.append(Finding(
                    "SML-002", "error", path,
                    "type 'array' with no 'items' schema",
                    "declare 'items' so the model knows the element type"))
            # SML-003: additionalProperties unset
            if "object" in declared and sub.get("properties") \
                    and "additionalProperties" not in sub:
                out.append(Finding(
                    "SML-003", "info", path,
                    "'additionalProperties' is unset: LLMs may invent extra keys",
                    "set additionalProperties: false to lock the shape, or true if open"))
            # SML-004: anyOf/oneOf without discriminator
            # (skip the nullable idiom: a null branch is not a branch choice,
            # it is nullability -- covered by REQ-004 instead)
            for comb in ("anyOf", "oneOf"):
                branches = sub.get(comb)
                if (isinstance(branches, list) and branches
                        and "discriminator" not in sub
                        and not _has_null_branch(sub)):
                    out.append(Finding(
                        "SML-004", "warn", path,
                        f"{comb} with no 'discriminator': the model must guess the branch",
                        "add a 'discriminator' (propertyName + mapping), "
                        "or a shared enum tag the model can pick"))
            # SML-005: unknown format
            fmt = sub.get("format")
            if isinstance(fmt, str) and fmt not in KNOWN_FORMATS:
                out.append(Finding(
                    "SML-005", "warn", f"{path}.format",
                    f"unknown format {fmt!r}",
                    "use a standard format (date-time, uuid, email, uri...) or drop it"))
            # SML-006: pattern without a valid example
            pattern = sub.get("pattern")
            if isinstance(pattern, str):
                examples = sub.get("examples")
                try:
                    rx = re.compile(pattern)
                except re.error:
                    rx = None
                valid = bool(rx and isinstance(examples, list) and examples
                             and all(isinstance(e, str) and rx.search(e) for e in examples))
                if not valid:
                    out.append(Finding(
                        "SML-006", "warn", path,
                        f"'pattern' {pattern!r} has no valid example proving it works",
                        "add an example that matches the pattern"))
    return out


# ---------------------------------------------------------------------------
# Rule family 6: risk
# ---------------------------------------------------------------------------

def _rule_risk(tools: List[Tool]) -> List[Finding]:
    out: List[Finding] = []
    for i, tool in enumerate(tools):
        base = f"$.tools[{i}]"
        params, params_path = _parameters_schema(tool)
        ppath = params_path.replace("$.TOOL", base)
        for path, sub in _iter_subschemas(params, ppath):
            m = re.search(r"\.properties\.([^\.]+)$", path)
            if not m or not isinstance(sub, dict):
                continue
            pname = m.group(1)
            if DANGER_NAME_RE.search(pname) and sub.get("sensitive") is not True:
                out.append(Finding(
                    "RISK-001", "warn", path,
                    f"parameter {pname!r} looks destructive or secret-bearing "
                    f"but lacks the 'sensitive': true marker",
                    'add "sensitive": true (see README marker convention) so '
                    "reviewers and gates can treat it as high-risk"))
    return out


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

_RULE_FAMILIES = (
    _rule_naming,
    _rule_descriptions,
    _rule_examples,
    _rule_required,
    _rule_smells,
    _rule_risk,
)


def lint_tools(tools: List[Tool]) -> List[Finding]:
    """Lint a list of tool definitions. Fully deterministic."""
    findings: List[Finding] = []
    for family in _RULE_FAMILIES:
        findings.extend(family(tools))
    findings.sort(key=lambda f: (f.rule_id, f.path, f.message))
    return findings


def lint_tool(tool: Tool) -> List[Finding]:
    """Lint a single tool definition."""
    return lint_tools([tool])
