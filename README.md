# tool-schema-linter

**The pitch:** every serious agent team lints its tool schemas before an agent ever touches them — because a sloppy schema is how you get hallucinated arguments, crashed runtimes, and agents confidently calling the wrong tool. This is the static contract lint for agent **tool schemas** — the **JSON Schemas** that describe each tool a **function-calling agent** can use. It catches the naming, description, example, and shape smells that make **LLMs** — large language models — misuse tools, and it gates releases in **CI** — continuous integration, the automated checks that run on every code change. It pairs with its sibling `tool-contract-checker`: **lint the schema, gate the versions.**

Built as a portfolio project for forward-deployed engineering roles: the kind of unglamorous reliability tooling that **FDE** — forward deployed engineering, engineers embedded with customers to ship working AI systems — teams actually run in production.

---

## Words to know

- **JSON Schema** — a JSON document that describes the allowed shape of other JSON data (field names, types, which fields are required).
- **Tool schema** — a JSON Schema describing one agent tool: its name, what it does, and its parameters.
- **Function-calling agent** — an LLM wired up so it can invoke software tools by emitting structured JSON arguments.
- **Linter** — a program that statically analyzes code or config and reports suspicious patterns without running it.
- **Static analysis** — examining code/config without executing it.
- **LLM** — large language model, e.g. GPT / Claude / Llama.
- **FDE** — forward deployed engineering: engineers who embed with customers and ship working AI systems on real data.
- **CI** — continuous integration: automated tests and checks that run on every proposed code change.
- **snake_case** — naming style with lowercase words joined by underscores, e.g. `place_order`.
- **JSONPath** — a query/pointer syntax for addressing parts of a JSON document (this linter reports finding locations in a JSONPath-ish form like `$.tools[0].parameters.properties.qty`).
- **Enum** — a fixed list of allowed values, e.g. `["standard", "express", "overnight"]`.
- **Discriminator** — a field (common in OpenAPI) that tells the reader which branch of an `anyOf`/`oneOf` applies.
- **`$ref`** — a JSON Schema keyword that references another schema by pointer instead of inlining it.
- **`patternProperties`** — a JSON Schema keyword constraining object keys by regex.
- **`additionalProperties`** — a JSON Schema keyword controlling whether an object may carry keys beyond those declared.
- **Nullable** — allowed to be `null` (empty/absent value).
- **Hermetic** — self-contained; tests that need no network, no keys, no external services.
- **Fixture** — canned sample input used by tests and demos.
- **Golden eval** — a test that pins exact expected output for a fixed input corpus, so any behavior change is caught.
- **Determinism** — same input always produces byte-identical output.
- **False positive (FP)** — the linter flagging something that is actually fine.
- **Stdlib** — Python's standard library (no third-party packages needed).
- **Gate** — a check that blocks progress when it fails (e.g. a CI gate blocks a release).
- **Exit code** — the number a program returns when it finishes; `0` means success.
- **Smoke test** — a quick check that the basic flow works at all.
- **Hallucination** — when a model invents plausible-sounding but wrong content.
- **Pure function** — a function with no side effects: same input, same output, touches nothing outside itself.
- **I/O** — input/output: reading files, network, or other outside resources.
- **OpenAPI** — the standard format for describing web APIs.
- **GitHub Actions** — GitHub's built-in CI runner: it executes your checks on every change.

---

## Quickstart

```bash
# lint a tool schema file, human-readable report
python3 cli.py lint my_tool.json

# CI gate: exit 0 = clean, 1 = warnings, 2 = errors
python3 cli.py check my_tool.json

# one-command end-to-end demo (asserts internally)
python3 cli.py demo

# tiny JSON API (stdlib http.server): POST /lint {"tool": {...}}
python3 cli.py serve --port 8471
```

`my_tool.json` is a tool object (`{"name", "description", "parameters": {...}}`),
a `{"tools": [...]}` wrapper, a JSON list of tools, or a bare JSON Schema
(linted anonymously).

Example output:

```
tool-schema-linter: 1 tool(s), 3 finding(s): 1 error, 2 warn, 0 info
[ERROR] REQ-001 $.tools[0].parameters.required
          required "customer_id" is not declared in properties
          fix: add the property, or remove it from 'required'
[WARN ] EX-001 $.tools[0].parameters.properties.notes
          parameter 'notes' has no examples
          fix: add an 'examples' array with 1-3 realistic values
```

---

## Rule catalog

Every finding carries: rule id, severity (`error` | `warn` | `info`), JSON path,
message, and a suggested fix. Findings are sorted by `(rule_id, path, message)`,
so output is deterministic regardless of input dict ordering.

| Rule | Sev | What it catches |
|------|-----|-----------------|
| NAM-001 | error | tool name not lowercase `snake_case` |
| NAM-002 | warn | generic tool name (`tool1`, `fn`, `helper`…) |
| NAM-003 | error | parameter name not lowercase `snake_case` |
| NAM-004 | warn | bare single-letter parameter (documented exceptions: `x`, `y`) |
| DESC-001 | error | tool has no description |
| DESC-002 | error | property has no description |
| DESC-003 | warn | description shorter than 12 chars |
| DESC-004 | error | placeholder text (`TODO`, `fixme`, `description here`…) |
| DESC-005 | warn | copy-pasted duplicate description on another parameter |
| EX-001 | warn | property has no `examples` array |
| EX-002 | error | example fails type-check (or isn't in the `enum`) |
| EX-003 | info | `enum` value never shown in an example or the description |
| REQ-001 | error | `required` names a property that isn't declared |
| REQ-002 | warn | description claims "optional"/"can be null" but it's `required` |
| REQ-003 | error | property has a `default` yet is listed `required` |
| REQ-004 | warn | `required` property allows `null` via a nullable `oneOf`/`anyOf` |
| SML-001 | warn | `type: object` with no `properties` (opaque to the model) |
| SML-002 | error | `type: array` with no `items` schema |
| SML-003 | info | `additionalProperties` unset (LLMs may invent extra keys) |
| SML-004 | warn | `anyOf`/`oneOf` with no `discriminator` (nullable idiom exempt) |
| SML-005 | warn | unknown `format` value |
| SML-006 | warn | `pattern` with no valid matching example |
| SML-007 | info | `$ref` / `patternProperties` present — not analyzed (honest scope) |
| RISK-001 | warn | destructive/secret-ish name (`delete_*`, `password`, `api_key`, `$env`…) without the `"sensitive": true` marker |

### The `"sensitive": true` marker convention

Properties whose names suggest destructive power or secret handling
(`delete_all`, `customer_password`, `api_key`, `$env`, `*secret*`, `*token*`)
must set `"sensitive": true` in their schema. The marker is a convention this
linter enforces so that human reviewers and downstream policy gates can treat
those parameters as high-risk at a glance. A marked property passes RISK-001.

### A note on REQ-002's "optional" detection

REQ-002 only fires on claims about *this parameter*: "is optional",
"(optional)", "optional parameter", "can be null", "not required", etc.
A description that merely mentions the word — *"Toggles the 'optional' extras
pack"* — does not fire. There is a pinned **FP trap** — a test fixture designed
to look suspicious but be innocent — for this in the golden evals.

---

## Architecture

```
cli.py        **argparse** — Python's stdlib command-line parser — subcommands: lint / check / demo / serve (+ the /lint request handler)
linter.py     rule engine: **Finding dataclass** — a small data-holding class — six rule families, deterministic sort
fixtures.py   fictional Helios Home / Helios Cloud tool schemas (good + bad)
demo.py       one-command end-to-end smoke test (asserts internally)
evals/        pinned golden corpus + runner + committed eval_report.json
tests/        90 hermetic unit tests
```

**Rule engine design.** Each rule family is a pure function
`(tools) -> List[Finding]` — no I/O, no global state, no network. `lint_tools`
runs all six families and sorts the combined findings by
`(rule_id, path, message)`, which makes output byte-identical across runs and
independent of input dict ordering (there is a test that shuffles property
order and asserts identical output).

A schema walker (`_iter_subschemas`) yields every nested property, array
`items` schema, and `anyOf`/`oneOf` branch with its JSONPath-ish location, so
rules apply recursively — a misnamed parameter three levels deep is still
caught, with its full path in the finding. Type-checking of examples is
top-level and JSON-Schema-faithful in the ways that matter: integers are valid
`number`s, booleans are never integers, and an example only needs to match one
`oneOf`/`anyOf` branch.

**Why flag-only (no `--fix`).** An autofix that rewrites your tool schemas
sounds helpful until it "fixes" a description by inventing meaning the author
never intended. Schema wording is a semantic contract with the model; changing
it automatically is a semantic change, not a formatting one. This linter reports
precisely and stays out of your files — the honest scope for a tool like this.

---

## CI usage

```bash
python3 cli.py check tools/order.json
echo $?   # 0 = clean, 1 = warnings, 2 = errors
```

Suggested pipeline: fail the build on `2` (errors), and either fail or warn on
`1` depending on how strict you want to be. `info` findings never affect the
exit code. In GitHub Actions:

```yaml
- name: Lint tool schemas
  run: python3 tool-schema-linter/cli.py check tools/
```

---

## Honest scope limits

- **`$ref` is not resolved** (SML-007, info). Inline referenced schemas before linting.
- **`patternProperties` constraints are not analyzed** (SML-007, info). Add an
  explicit example showing the expected key shape.
- **No `--fix` autofix** — flag-only by design (see above).
- Example type-checking is **top-level**: a nested object example is checked
  for being an object, not field-by-field.
- The known-`format` list is pragmatic (`date-time`, `uuid`, `email`, `uri`,
  `ipv4`, …); project-specific formats will warn — treat SML-005 as advisory.
- The linter reads schemas, never calls tools; it cannot catch runtime
  behavior, only contract smells in the schema text.

---

## Dev-loop story: real bugs the tests caught

Three genuine bugs surfaced while building this — all caught by tests or the
fixture smoke run, all fixed before commit:

1. **`as?` is not `(as)?` — REQ-002's "is optional" pattern never fired.**
   The regex `\s+as?\s*optional` was meant to match both "is optional" and
   "marked as optional". But `as?` means "required `a`, optional `s`" — the
   **quantifier** — the `?`/`*`/`+` symbols saying "how many times" in a
   **regex** — regular expression, a pattern language for matching text —
   binds to the `s`, not the word `as`. So the pattern demanded a literal `a`
   after the whitespace and silently never matched plain "is optional".
   `test_optional_claim_but_required_warns` caught it (0 findings where 1 was
   expected). Fix: `\s+(?:as\s+)?optional` — the whole word `as` is now
   genuinely optional. A good reminder that regex quantifiers bind tighter
   than intuition suggests.

2. **Placeholder detector false-positived on "todo-list".**
   `\b(todo)\b` matched inside the hyphenated compound "todo-list" — a
   legitimate feature name ("Runs the todo-list sync for the device."), not a
   placeholder. **Word boundaries** — the regex `\b` anchor, matching between a
   word character and a non-word character — treat `-` as a non-word character,
   so `\b` happily matches there. `test_legit_description_mentioning_todo_noun_ok`
   caught it. Fix: hyphen-aware **lookarounds** — regex tests that peek at
   surrounding characters without consuming them —
   `(?<![\w-])(todo|…)(?![\w-])` — "TODO: write docs" still fires, "todo-list
   sync" no longer does.

3. **SML-004 double-fired on the nullable idiom.**
   The "anyOf/oneOf without discriminator" rule fired on
   `oneOf: [{type: string}, {type: null}]` — but a null branch isn't a branch
   the model must choose between; it's just nullability, already covered by
   REQ-004. The fixture smoke run showed SML-004 firing twice where the
   design called for once. Fix: exempt schemas with a null branch
   (`_has_null_branch`) from SML-004. There is now a pinned golden eval
   (`fp_nullable_oneof_no_discriminator_rule`) locking in that behavior.

---

## Sample data

All fixtures are fictional: the **Helios Home** / **Helios Cloud** product
line was invented for this repo. No real data, no API keys, no personal data —
`fixtures.py` even documents which near-miss wordings are deliberate FP-trap
material.

## License

MIT — see `LICENSE`.
