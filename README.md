# OpenMath

OpenMath is a local mathematical research workbench: a multi-project Web UI, CLI, chat-driven agent launcher, run tracker, and Lean-oriented workspace format in one repository.

This repository is still early, but it is already usable as a control room for project folders with multiple research threads and provider-backed agent runs.

## Current version

**Version:** `0.1.1`

`0.1.1` currently gives you:

- a local web app for multiple OpenMath project folders
- per-project chat threads with rename/delete
- provider-backed chats for `Codex`, `Claude Code`, `Gemini`, and `Ollama`
- an engine layer with `None`, `UlamAI`, `Aristotle`, and `lean4-skills`
- top-right Settings for CLI connection guidance, Ollama base URL, and Aristotle API key
- persisted runs, active-agent stream, and autoresearch loops
- project state on disk under `.openmath/`

For the longer product/design document, see [overview.md](./overview.md).

## What OpenMath is

OpenMath is meant to sit between a theorem-proving IDE, a research notebook, and an agent control panel.

The practical model is:

- each research folder is its own OpenMath project
- each project has multiple chat threads
- each thread can launch independent agent runs
- runs are persisted and inspectable
- external engines and providers are optional, not the whole product

## Quick start

### Requirements

- `python3`
- `node`
- optional providers:
  - `codex`
  - `claude`
  - `gemini`
  - `ollama`
- optional engines/backends:
  - `ulam`
  - Aristotle API key and/or CLI
  - `lean` and `lake`

### Create a project

```bash
python3 -m openmath init .
```

Or create several sibling projects:

```bash
python3 -m openmath init ../hadamard
python3 -m openmath init ../formalization-lab
python3 -m openmath web ..
```

### Start the web UI

```bash
python3 -m openmath web .
```

Then open the local URL printed by the server.

## How to use it

1. Open a project from the left rail.
2. Create or select a thread.
3. In the composer row, choose:
   - `Engine`
   - `Provider` / `Connect to`
   - `Model`
   - `Reasoning`
4. Use `Settings` in the top right to:
   - connect Codex / Claude Code / Gemini CLI from your terminal
   - point OpenMath at an Ollama server
   - save the Aristotle API key
5. Run a single turn or switch to `Autoresearch` for looped runs.
6. Watch active agents on the right and inspect persisted runs in the `Runs` view.

## Useful commands

```bash
python3 -m openmath doctor
python3 -m openmath backend detect .
python3 -m openmath web .
python3 -m unittest discover -s tests
```

## Workspace layout

Each project stores local state in `.openmath/`, including:

- chat transcripts and summaries
- run manifests, logs, and artifacts
- graph state
- metrics and program control files

This directory is intentionally ignored by git.

## What is in the pipeline

The next major slices are:

- deeper UlamAI and Aristotle adapter execution, not just engine profiles
- richer Lean workbench integration
- better graph/source workflows for mathematical claims and artifacts
- terminal tabs and backend-specific job panels
- stronger benchmark and evaluation workflows

## Status

OpenMath is still pre-`1.0`. The UI, runtime model, and integrations are moving quickly, but the current version is already useful for local project-based agent research.
