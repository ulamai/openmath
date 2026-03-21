# Bootstrap Slice

This repository now contains the first runnable OpenMath slice. It is intentionally
small, but it already aligns with the architecture in the root README.

## Implemented

- Python package and CLI entrypoint
- `.openmath/` workspace initialization
- project discovery from disk
- persisted chat/session transcripts and summaries
- graph and run loading from workspace files
- backend detection for native Lean, UlamAI, and Aristotle
- local HTTP gateway serving both JSON API and Web UI
- multi-project browser shell with per-project chat threads

## Deferred

- WebSocket event streaming
- Lean LSP integration and `lake build` orchestration
- structured agent runtime and approvals workflow
- source ingestion pipelines
- terminal multiplexing inside the browser
- adapter execution for UlamAI and Aristotle

## Current usage

```bash
python3 -m openmath init .
python3 -m openmath doctor
python3 -m openmath web
```

The current UI is intentionally closer to a project picker plus chat workspace than a
dashboard-only shell. Research views like runs, graph, and backends now sit beside
threads instead of replacing them.
