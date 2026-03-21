from __future__ import annotations

WORKSPACE_DIRNAME = ".openmath"

WORKSPACE_DIRECTORIES = [
    "graph/views",
    "sources/manifests",
    "sources/extracted",
    "sources/annotations",
    "runs",
    "sessions/transcripts",
    "sessions/summaries",
    "approvals",
    "experiments/baselines",
    "backends",
    "cache",
    "exports",
]


def _toml_array(values: list[str]) -> str:
    rendered = ", ".join(f'"{value}"' for value in values)
    return f"[{rendered}]"


def render_project_toml(
    name: str,
    objective: str,
    entry_docs: list[str],
    lean_project: str,
) -> str:
    return f"""[project]
name = "{name}"
objective = "{objective}"
workspace = "."
entry_docs = {_toml_array(entry_docs)}
lean_project = "{lean_project}"

[web]
port = 31789
host = "127.0.0.1"

[lean]
backend = "lsp"
auto_build = true

[research]
program = ".openmath/program.md"
metrics = ".openmath/metrics.toml"

[agents]
default_mode = "single"

[agents.conductor]
enabled = true

[agents.explorer]
enabled = true

[agents.formalizer]
enabled = true

[agents.prover]
enabled = true

[agents.critic]
enabled = true

[backends.native]
enabled = true

[backends.ulam]
enabled = true
command = "ulam"
mode = "cli"

[backends.aristotle]
enabled = true
command = "aristotle"
mode = "cli"
api_key_env = "ARISTOTLE_API_KEY"
"""


def render_program_md(name: str, objective: str) -> str:
    return f"""# Program

## Objective

{objective}

## Project

- Name: {name}
- Scope: bootstrap the OpenMath workspace, gateway, UI, and native project flow
- Read-only files: none yet
- Approval rule: require human review before accepting semantic Lean changes

## Research policy

1. Preserve all durable state in `.openmath/`.
2. Treat Lean as the final source of truth.
3. Prefer small, reviewable runs over invisible agent behavior.
4. Log experiments before promoting results to canonical files.
"""


def render_metrics_toml() -> str:
    return """[bundle]
primary = "solved_declarations"
secondary = "review_burden"
tie_breaker = "proof_complexity"

[constraints]
build_regressions = 0
unsafe_axioms = 0

[metrics.solved_declarations]
kind = "count"
direction = "maximize"

[metrics.review_burden]
kind = "estimate"
direction = "minimize"

[metrics.proof_complexity]
kind = "penalty"
direction = "minimize"
"""
