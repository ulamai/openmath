# OpenMath

> A self-contained scientific-research workbench for mathematics: one repository with its own Web UI, CLI, project model, orchestration layer, research memory, Lean workbench, and optional theorem-proving backends.

> **Status:** architecture README / v0.2 repository specification.

OpenMath should be built as **one product in one repository**.

It should own, from scratch:

- its own **Web UI**,
- its own **CLI**,
- its own **HTTP + WebSocket gateway**,
- its own **workspace format**,
- its own **orchestration and multi-agent runtime**,
- its own **research memory model**,
- its own **Lean project workbench**,
- its own **artifact and run model**.

At the same time, OpenMath should **not** waste effort re-implementing the strongest external proving/formalization engines when they can be installed separately.

So the correct design is:

> **OpenMath is self-contained at the product layer, but extensible at the proving layer.**

That means:

- **OpenClaw** is **inspiration only**, not a dependency.
- **OpenGauss** is **inspiration only**, not a dependency.
- **UlamAI** is **optional**, installable separately, and exposed through an OpenMath adapter.
- **Aristotle CLI** is **optional**, installable separately, and usable both through an adapter and directly from the OpenMath Web UI terminal.

OpenMath must work on its own. But when external backends are installed, OpenMath should become significantly more powerful without changing its project model, UI, or commands.

---

## The product promise

OpenMath should let a researcher do all of this in one place:

1. read and annotate mathematical sources,
2. explore examples and counterexamples,
3. create and refine conjectures,
4. draft informal proof sketches,
5. formalize statements and proofs into Lean,
6. run machine-checked proving and repair loops,
7. coordinate multiple agents,
8. compare research runs by metrics,
9. inspect provenance, diffs, and approvals,
10. export results back to Lean files, notes, and papers.

The guiding sentence is:

> **Start from informal mathematical research, end in checked artifacts, and keep the whole process visible, resumable, and reviewable.**

---

## What OpenMath is

OpenMath is a **math-first research operating environment** like LMStudio but for research projects with multiple agents - multiple instances of OpenAI Codex Agents, Claude Code, UlamAI, Aristotle, local models and so on, working at the same time, observable in one webUI with orchestration.

It is not just a theorem prover and not just a chat app. It is closer to a hybrid of:

- a mathematical IDE/webUI 
- a research notebook,
- a theorem-proving control room,
- a paper-to-Lean workbench,
- an experiment tracker,
- and a multi-agent orchestration dashboard.

Its center of gravity is **scientific research**, especially **mathematics**.

That means OpenMath should privilege:

- structured claims,
- proof state,
- Lean diagnostics,
- source alignment,
- benchmarks and metrics,
- artifact provenance,
- and explicit approvals.

Chat is useful, but it is not the main product primitive.

---

## What OpenMath is not

OpenMath must **not** become any of the following:

- a thin wrapper around OpenClaw,
- a clone of OpenGauss,
- a repackaged UlamAI checkout,
- a browser shell that only forwards prompts to an external prover,
- a transcript-first tool where memory is mostly chat history,
- a multi-channel messenger product,
- or a repo that vendors large third-party theorem-proving code just to claim it is “integrated.”

The core product must be native to OpenMath.

---

## The central design decision

OpenMath should own the parts that define the **research experience**:

- project/workspace model,
- Web UI,
- CLI,
- gateway and event protocol,
- research memory,
- claim graph,
- Lean file management,
- source ingestion,
- experiment tracking,
- metric-driven evaluation,
- approvals and merges,
- multi-agent orchestration,
- artifact normalization,
- and backend adapters.

OpenMath should **not** try to out-copy every proving strategy in UlamAI or every backend capability in Aristotle.

Instead:

- OpenMath ships a **minimal native Lean backend** for basic project work,
- OpenMath defines a **stable backend interface**,
- and advanced proving/formalization engines are **pluggable**.

This keeps the repository self-contained while avoiding duplicate complexity.

---

## Inspirations used selectively

OpenMath should borrow ideas, not code ownership, from the following projects.

### UlamAI
Reference: https://github.com/ulamai/ulamai

Use as inspiration for:

- truth-first Lean verification,
- formalization/proving loops,
- resumable runs and artifact directories,
- claim-graph-style decomposition,
- Lean backend abstraction (`dojo`, `cli`, `lsp`),
- and document-to-Lean workflows.

But OpenMath should **not** re-implement UlamAI’s advanced proving machinery just to avoid admitting it is useful. Instead, OpenMath should support **optional UlamAI installation** and expose it as a first-class backend.

### OpenClaw
Reference: https://github.com/openclaw/openclaw
Docs: https://docs.openclaw.ai/

Use as inspiration for:

- one always-on gateway process,
- a browser Control UI served by the same gateway,
- typed tools,
- WebSocket control plane,
- multi-agent routing,
- session-aware orchestration,
- and workspace-centric memory.

But OpenMath should **not** become messaging-first. No WhatsApp/Telegram-first product posture. The OpenMath version of this idea is a **research control plane**, not a personal-assistant gateway.

### OpenGauss
Reference: https://github.com/math-inc/OpenGauss

Use as inspiration for:

- project-scoped commands,
- source-aware formalization workflows,
- and swarm/project task framing.

But OpenMath should own its own orchestration and backend model rather than relying on OpenGauss as an execution layer.

### Karpathy’s `autoresearch`
Reference: https://github.com/karpathy/autoresearch

Use as inspiration for:

- metric-driven closed loops,
- a small “research org” control document (`program.md`-style),
- keep/discard candidate runs,
- experiment logs,
- branch-based iteration,
- and the idea that an autonomous system should be evaluated by **research outcomes**, not by how impressive its prose sounds.

OpenMath should adapt that idea to math by tracking metrics like solved declarations, broken declarations, accepted formalizations, counterexample discoveries, and review burden.

### `bandmaster`
Reference: https://github.com/przchojecki/bandmaster

Use as inspiration for:

- manager/worker role separation,
- project TOML config,
- metric-driven loop execution,
- file-backed swarm coordination,
- claim/publish/sync behavior,
- and session history views.

OpenMath should reframe this for research: the “manager” becomes a **conductor** or **research lead**, the “worker” becomes specialized research agents, and the evaluation command becomes a **Lean build / theorem benchmark / formalization benchmark / custom research harness**.

---

## The correct architecture in one sentence

> **OpenMath should look like OpenClaw at the gateway/UI/orchestration layer, feel like a scientific IDE at the workflow layer, use autoresearch/bandmaster ideas for experiment loops, and treat UlamAI and Aristotle as optional proving engines behind adapters.**

---

## High-level architecture

```text
Browser UI / CLI / Editor extension
                │
                ▼
          openmath.gateway
     HTTP API + WebSocket control plane
                │
                ▼
        openmath.coordinator
   projects • runs • agents • approvals • metrics
                │
     ┌──────────┼──────────┬──────────────┐
     ▼          ▼          ▼              ▼
openmath.memory openmath.lean openmath.lab openmath.backends
claim graph     LSP/lake     examples/CAS native + adapters
notes/indexes   diagnostics  experiments  ulam/aristotle
     │          │          │              │
     └──────────┴──────┬───┴──────────────┘
                       ▼
               .openmath workspace
   sources • runs • sessions • results • diffs • summaries
                       │
                       ▼
                 Lean project / files
```

The **workspace on disk** is the source of truth.

The gateway streams state.
The UI visualizes state.
The agents manipulate state.
The external backends contribute capabilities.
But the durable truth of a project lives in `.openmath/` and the Lean project tree.

---

## Division of responsibility

### OpenMath core owns

- project discovery,
- workspace state,
- source ingestion,
- claim graph,
- research memory,
- session summaries,
- run tracking,
- approvals,
- multi-agent orchestration,
- Lean file editing,
- Lean diagnostics surface,
- experiment metrics,
- backend health detection,
- backend job normalization,
- Web UI,
- CLI,
- HTTP/WS APIs.

### Native OpenMath backend owns

The native backend should be intentionally modest.

It should provide:

- Lean LSP integration,
- `lake build` integration,
- file-level diagnostics,
- declaration discovery,
- source-to-code linking,
- simple retrieval from project + mathlib,
- basic suggestion generation,
- lightweight tactic/term attempts,
- and deterministic repair routines for imports, names, and syntax.

It should **not** attempt to replicate the full advanced proving stack of UlamAI or the cloud proving stack of Aristotle.

### Optional UlamAI backend owns

When installed, UlamAI should handle:

- advanced proving,
- TeX/informal proof drafting,
- document formalization,
- Lean backend routing,
- and deeper repair/proving loops.

### Optional Aristotle backend owns

When installed, Aristotle CLI should handle:

- project-level `sorry` filling,
- remote/autonomous proof jobs,
- formalization of documents,
- and result retrieval for long-running jobs.

### Lean still owns truth

No backend can overrule Lean.
If a proof does not check, it is not accepted.
If a statement changes semantically, downstream artifacts are invalidated.

---

## Repository layout

```text
openmath/
├── README.md
├── pyproject.toml                  # or monorepo root config
├── package.json                    # if frontend/backend split is used
├── apps/
│   ├── gateway/                    # HTTP + WebSocket + auth + background jobs
│   ├── web/                        # React/TypeScript research UI
│   └── cli/                        # openmath command surface
├── openmath/
│   ├── api/
│   │   ├── http/
│   │   ├── ws/
│   │   └── schemas/
│   ├── coordinator/
│   │   ├── projects/
│   │   ├── runs/
│   │   ├── approvals/
│   │   ├── metrics/
│   │   └── agents/
│   ├── memory/
│   │   ├── graph/
│   │   ├── notes/
│   │   ├── summaries/
│   │   ├── retrieval/
│   │   └── provenance/
│   ├── lean/
│   │   ├── lsp/
│   │   ├── lake/
│   │   ├── parser/
│   │   ├── declarations/
│   │   └── diagnostics/
│   ├── lab/
│   │   ├── examples/
│   │   ├── counterexamples/
│   │   ├── python/
│   │   └── symbolic/
│   ├── backends/
│   │   ├── native/
│   │   ├── adapter_api/
│   │   ├── ulam/
│   │   └── aristotle/
│   ├── tools/
│   ├── prompts/
│   ├── agents/
│   └── workspace/
├── docs/
│   ├── architecture/
│   ├── ui/
│   ├── protocol/
│   └── backends/
└── examples/
```

The repository should feel unified even if the implementation is split across Python and TypeScript.

---

## The `.openmath/` workspace format

Every project should contain a `.openmath/` directory.

```text
.openmath/
├── project.toml
├── program.md
├── metrics.toml
├── graph/
│   ├── nodes.jsonl
│   ├── edges.jsonl
│   └── views/
├── sources/
│   ├── manifests/
│   ├── extracted/
│   └── annotations/
├── runs/
│   └── <run-id>/
│       ├── manifest.json
│       ├── events.jsonl
│       ├── summary.json
│       ├── stdout.log
│       ├── stderr.log
│       ├── diffs/
│       └── artifacts/
├── sessions/
│   ├── transcripts/
│   └── summaries/
├── approvals/
├── experiments/
│   ├── results.tsv
│   └── baselines/
├── backends/
│   ├── health.json
│   ├── ulam.json
│   └── aristotle.json
├── cache/
└── exports/
```

### Why this matters

This is where OpenMath imitates the **durability** and **operational clarity** of tools like OpenClaw, `autoresearch`, and `bandmaster`, but reorients them around research.

The workspace should preserve:

- what the agents believed,
- what they tried,
- what Lean accepted,
- what external backends returned,
- what the human approved,
- and which metrics improved or regressed.

---

## The `program.md` concept

OpenMath should adopt a research-control document inspired by `autoresearch`.

Each project has a `.openmath/program.md` that tells the agent organization:

- the research objective,
- what files are in scope,
- which files are read-only,
- what “success” means,
- what metrics matter,
- how aggressively to explore,
- what approval rules apply,
- how to treat complexity cost,
- when to escalate to the human,
- and how to log experiments.

This is essential.

The user should be programming the **research organization**, not only issuing isolated prompts.

---

## The metric model

OpenMath should adapt the metric-driven spirit of `autoresearch` and `bandmaster`, but for math.

There should never be only one metric. Instead, OpenMath should support a **metric bundle**.

Typical metrics:

- number of declarations proved,
- number of declarations broken,
- number of new `sorry`s,
- Lean build pass rate,
- theorem benchmark success rate,
- number of accepted formalizations,
- counterexamples found,
- semantic alignment score,
- proof complexity penalty,
- human review cost estimate,
- time-to-check,
- and token/runtime budget.

OpenMath should let projects define a keep/discard policy such as:

- hard constraints: no build regressions, no unsafe axioms,
- primary objective: maximize solved declarations,
- secondary objective: minimize review burden,
- tie-breaker: simpler code/proofs win.

That is the mathematical analog of `autoresearch`’s “keep if the metric improved.”

---

## Multi-agent model

OpenMath should imitate the useful parts of OpenClaw’s orchestration and memory model, but for research.

### Agent roles

A default OpenMath project should support these roles:

- **Conductor** — manager/orchestrator; decides next steps and delegates work.
- **Explorer** — generates examples, counterexamples, reformulations, and conjectures.
- **Librarian** — retrieves prior notes, theorems, definitions, sources, and related declarations.
- **Formalizer** — converts informal text into Lean skeletons and source-linked declarations.
- **Prover** — tries to discharge Lean goals.
- **Critic** — looks for gaps, false statements, hidden assumptions, and regressions.
- **Merger** — the only role allowed to write the canonical accepted patch to project files.
- **Evaluator** — runs benchmarks and computes metric bundles.

### Rules

1. Every agent has its own session state and scratch memory.
2. Shared truth lives in the project workspace, not in hidden agent chat history.
3. Agents may propose patches, but only the merger applies accepted changes.
4. Statement changes require dependency invalidation.
5. High-impact semantic changes require approval.
6. Every long-running task is represented as a run with artifacts.

### Swarm coordination

Borrowing from `bandmaster`, OpenMath should support a file-backed or DB-backed coordination model with:

- task claiming,
- task publishing,
- best-known-result tracking,
- run summaries,
- and periodic synchronization.

But unlike generic coding swarms, OpenMath should coordinate around **claims, declarations, source segments, and proof obligations**, not just files.

---

## Research memory model

OpenMath should imitate OpenClaw’s notion that a workspace is a kind of memory, but make that memory **research-native**.

### Memory layers

#### 1. Claim memory
Stores definitions, lemmas, theorems, conjectures, proof sketches, counterexamples, and dependencies.

#### 2. Source memory
Stores PDF/TeX/Markdown extracts, source anchors, annotations, and source-to-declaration links.

#### 3. Execution memory
Stores runs, commands, stdout/stderr, backend jobs, metrics, and timings.

#### 4. Session memory
Stores agent transcripts, summaries, decisions, and unresolved questions.

#### 5. Review memory
Stores approvals, rejections, reasons, semantic change notes, and reviewer comments.

#### 6. Experiment memory
Stores branch/runs baselines, `results.tsv`, metric comparisons, and “keep/discard” outcomes.

### Important rule

Chat transcripts are **not** the main memory.

The main memory is structured research state.

---

## The Web UI: exact product shape

OpenMath should have a **native browser UI** served by the gateway, similar in spirit to OpenClaw’s Control UI, but specialized for scientific research and mathematics.

It should feel like a **research console**, not like a generic chatbot.

### Visual style

The UI should look like a serious technical tool:

- dense but legible,
- keyboard-friendly,
- split-pane oriented,
- optimized for long sessions,
- dark mode first, light mode supported,
- strong monospace use for code and proofs,
- graph/timeline views for research state,
- and explicit status colors for build health, proof health, and approvals.

Do **not** make it look like a consumer chat toy.

### Global layout

The default layout should be:

```text
┌──────────────────────────────────────────────────────────────────┐
│ Top bar: project • branch • backend status • run controls • user│
├──────────────┬──────────────────────────────────┬────────────────┤
│ Left nav     │ Main work area                   │ Right inspector│
│ Projects     │ current screen                   │ context        │
│ Dashboard    │                                  │ goal / source  │
│ Graph        │                                  │ run summary    │
│ Sources      │                                  │ approval pane  │
│ Lean         │                                  │ agent notes    │
│ Runs         │                                  │                │
│ Agents       │                                  │                │
│ Metrics      │                                  │                │
│ Backends     │                                  │                │
│ Terminal     │                                  │                │
└──────────────┴──────────────────────────────────┴────────────────┘
Bottom dock: logs • diagnostics • tasks • notifications • terminal tabs
```

### Required routes

The Web UI should expose at least these routes:

- `/` — project picker / recent work.
- `/projects/:id/dashboard` — overall research dashboard.
- `/projects/:id/graph` — claim graph explorer.
- `/projects/:id/sources` — source browser and annotator.
- `/projects/:id/lean` — Lean workbench.
- `/projects/:id/runs` — run history.
- `/projects/:id/runs/:runId` — run inspector.
- `/projects/:id/agents` — multi-agent monitor.
- `/projects/:id/metrics` — evaluation dashboards.
- `/projects/:id/backends` — backend detection, install help, health, capabilities.
- `/projects/:id/terminal` — raw project terminal + backend terminals.
- `/projects/:id/approvals` — pending changes and semantic reviews.

### Screen-by-screen behavior

#### 1. Dashboard
The dashboard is the first screen after opening a project.

It should show:

- active objective,
- current branch,
- build status,
- solved / broken / pending declaration counts,
- open approvals,
- currently running agents,
- recent source imports,
- recent conjectures,
- recent counterexamples,
- recent backend jobs,
- and trend cards for key metrics.

This is the math equivalent of an orchestration dashboard.

#### 2. Claim Graph
The graph view is the heart of the research UI.

Each node can be:

- source passage,
- definition,
- conjecture,
- theorem,
- proof sketch,
- Lean declaration,
- counterexample,
- imported backend result,
- unresolved blocker,
- or benchmark target.

Edges can mean:

- depends on,
- formalizes,
- refutes,
- motivates,
- is equivalent to,
- repairs,
- or is sourced from.

The user must be able to:

- filter by node type,
- collapse subgraphs,
- compare statement variants,
- jump from graph nodes to Lean code or source text,
- and mark nodes as accepted, speculative, broken, or archived.

#### 3. Sources
The source view should be a split screen:

- left: source document text or extracted text,
- center: annotations and extracted claims,
- right: linked declarations / graph nodes / formalization status.

This is where the user sees exactly which sentence generated which Lean declaration.

#### 4. Lean Workbench
This is the most important coding screen.

It should contain:

- project file tree,
- active Lean editor,
- declaration list,
- diagnostics panel,
- current goal panel,
- local context panel,
- dependency pane,
- hole / `sorry` tracker,
- proof-state timeline,
- and suggested next actions.

The workbench should integrate with native Lean LSP and show backend actions like:

- “Try native repair”
- “Send to UlamAI”
- “Send to Aristotle”
- “Launch swarm proof attempt”

#### 5. Runs
The runs screen should list every `explore`, `formalize`, `prove`, `repair`, `evaluate`, and `import` run.

Each row should show:

- run id,
- type,
- backend,
- agent owner,
- start/end time,
- status,
- affected files,
- key metrics,
- and result summary.

Clicking a run opens the run inspector.

#### 6. Run Inspector
A run inspector should show:

- timeline,
- events stream,
- raw logs,
- artifacts,
- produced diffs,
- approvals requested,
- metrics before/after,
- and provenance links.

This screen is where OpenMath becomes inspectable instead of magical.

#### 7. Agents
This screen should imitate OpenClaw’s orchestration feeling, but for research.

It should show:

- agent roster,
- role,
- current task,
- claimed work items,
- current branch or patchset,
- last summary,
- token/runtime budgets,
- and conflict/merge warnings.

Use swimlanes or cards, not just a chat log.

#### 8. Metrics
This screen should be inspired by `autoresearch` and `bandmaster`.

It should show:

- benchmark history,
- declaration solved counts over time,
- build health trends,
- import/formalization acceptance rates,
- review burden estimates,
- regressions,
- and keep/discard decisions.

This is where OpenMath becomes a research machine rather than a one-shot assistant.

#### 9. Backends
This screen is critical.

It should show cards for:

- Native backend,
- UlamAI,
- Aristotle,
- and any future backends.

Each card should display:

- installed/not installed,
- detected version,
- executable path,
- capabilities,
- health check result,
- auth status if needed,
- supported commands,
- and “copy install command” buttons.

#### 10. Terminal
This is how the user can use external CLIs **directly from the Web UI**.

The terminal screen should provide tabbed terminals such as:

- `shell`
- `lake`
- `ulam`
- `aristotle`

Each terminal runs inside the project workspace.

The terminal must support:

- raw command execution,
- log capture into runs,
- file download/upload,
- command templates,
- and “promote output to artifact” actions.

This is where Aristotle CLI direct use lives.

---

## Aristotle CLI from the Web UI

This is a hard requirement.

OpenMath should support **two ways** of using Aristotle.

### A. Structured adapter mode
The user fills a form in the UI:

- prompt,
- target project,
- file scope,
- wait vs async,
- destination path.

OpenMath then launches the corresponding CLI command and tracks it as a structured run.

### B. Raw terminal mode
The user opens the `aristotle` terminal tab and runs commands directly, for example:

```bash
aristotle submit "Fill in all sorries" --project-dir ./LeanProject --wait
aristotle formalize paper.tex --wait --destination output.tar.gz
aristotle list --limit 10
aristotle result <project-id> --destination result.tar.gz
```

OpenMath should capture stdout/stderr, preserve command history, and allow importing the result artifact into the workspace.

### UI affordances for Aristotle

The Backends page should expose quick actions:

- **Fill all `sorry`s in current project**
- **Formalize selected source document**
- **Fetch result by project id**
- **Open Aristotle terminal**

### Import behavior

When Aristotle produces a tarball or files, OpenMath should:

1. unpack them into `.openmath/imports/aristotle/<run-id>/`,
2. compute diffs against the current project,
3. attach the result to a run record,
4. request approval before overwriting canonical files,
5. and link generated declarations into the claim graph.

---

## UlamAI integration model

OpenMath should treat UlamAI similarly, but with a stronger research/Lean backend role.

### Installation stance

OpenMath does **not** vendor UlamAI.
The user installs it separately if desired.

The Backends screen should present the upstream installation options, for example:

- Homebrew: `brew tap ulamai/ulamai && brew install ulamai`
- or clone/install from upstream.

### Structured actions

OpenMath should provide buttons/forms for common Ulam-backed actions:

- formalize a `.tex` document,
- prove a declaration,
- run TeX/informal proof drafting,
- benchmark a suite,
- inspect Ulam artifacts.

### Raw terminal mode

The `ulam` terminal tab should let the user run upstream commands directly, such as:

```bash
ulam formalize paper.tex --out paper.lean
python3 -m ulam prove path/to/File.lean --theorem MyTheorem --lean dojo
python3 -m ulam prove --theorem MyTheorem --output-format tex --statement "..."
```

### Normalization rule

Ulam artifacts must be imported into OpenMath’s run model.

OpenMath should never let backend-specific directories become the main source of truth.
It may preserve raw backend artifacts, but it must also translate them into:

- normalized run metadata,
- attached diffs,
- updated graph nodes,
- and workspace-visible summaries.

---

## Backend adapter contract

OpenMath should define a clean adapter interface.

Every backend adapter must implement the equivalent of:

```text
health() -> status
capabilities() -> capability list
run(spec) -> backend_run_id
poll(backend_run_id) -> status/events
cancel(backend_run_id)
collect(backend_run_id, target_dir) -> artifacts
normalize(artifacts) -> OpenMath run summary + graph updates + diffs
```

### Why this matters

This is what lets OpenMath stay self-contained without becoming closed.

The product surface stays stable even if the proving engine changes.

---

## HTTP API and WebSocket protocol

OpenMath should imitate the good control-plane pattern from OpenClaw:

- one local gateway,
- HTTP API,
- WebSocket event stream,
- browser UI on the same server,
- local-first auth.

### Minimal HTTP surface

```text
GET    /api/projects
POST   /api/projects
GET    /api/projects/:id/state
POST   /api/projects/:id/runs
GET    /api/projects/:id/runs
GET    /api/projects/:id/runs/:runId
POST   /api/projects/:id/approvals/:approvalId/accept
POST   /api/projects/:id/approvals/:approvalId/reject
GET    /api/projects/:id/backends
POST   /api/projects/:id/backends/detect
POST   /api/projects/:id/backends/:backend/run
POST   /api/projects/:id/agents/dispatch
GET    /api/projects/:id/graph
GET    /api/projects/:id/sources
```

### Minimal WebSocket events

```text
project.updated
run.started
run.progress
run.finished
run.failed
run.artifact
graph.node.updated
graph.edge.updated
lean.diagnostics
lean.goal.updated
agent.status
approval.requested
approval.resolved
backend.health.updated
backend.job.updated
metrics.updated
terminal.output
```

These should be typed schemas, not ad-hoc blobs.

---

## CLI surface

The CLI should feel like a serious research tool.

Examples:

```bash
openmath init
openmath web
openmath doctor
openmath backend detect
openmath backend doctor
openmath explore "Investigate whether ..."
openmath draft claim-123
openmath formalize notes/paper.tex
openmath prove LeanProject/MyFile.lean#my_theorem
openmath repair LeanProject/MyFile.lean
openmath evaluate
openmath agents start
openmath agents status
openmath runs list
openmath graph show
openmath terminal
```

### Backend-aware CLI examples

```bash
openmath formalize notes/paper.tex --backend ulam
openmath prove LeanProject/MyFile.lean#my_theorem --backend native
openmath prove LeanProject/MyFile.lean#my_theorem --backend aristotle
openmath backend open aristotle
openmath backend open ulam
```

`backend open aristotle` should open the corresponding terminal/profile or backend screen.

---

## Example `project.toml`

```toml
[project]
name = "additive-combinatorics"
objective = "Explore, formalize, and prove selected lemmas from notes.tex"
workspace = "."
entry_docs = ["README.md", "notes.tex"]
lean_project = "./LeanProject"

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
```

---

## Approval model

OpenMath should be permissive for exploration and strict for semantics.

### Auto-apply allowed

- note creation,
- run logging,
- graph annotations,
- local scratch files,
- benchmark reports,
- non-canonical imports.

### Approval required

- theorem statement changes,
- overwriting accepted Lean declarations,
- accepting external backend output into canonical files,
- branch merge of multi-agent patchsets,
- deletion of accepted artifacts,
- or any change that invalidates downstream proofs.

This is especially important when importing UlamAI or Aristotle results.

---

## What to copy from each inspiration, and what not to copy

### From OpenClaw, copy:

- gateway shape,
- typed control plane,
- control UI concept,
- session/orchestration awareness,
- agent isolation,
- workspace-centric operation,
- and tool abstraction.

### From OpenClaw, do not copy:

- messaging-channel sprawl,
- personal-assistant product identity,
- node/device complexity unless later needed,
- or transcript-first UX.

### From `autoresearch`, copy:

- `program.md` mentality,
- metric-driven experimentation,
- baseline vs candidate logic,
- and run/result logging.

### From `autoresearch`, do not copy:

- single-metric oversimplification,
- uncontrolled indefinite changes to canonical files,
- or domain assumptions specific to model training.

### From `bandmaster`, copy:

- conductor/worker split,
- config-driven orchestration,
- file-backed swarm coordination,
- and keep/discard loop semantics.

### From `bandmaster`, do not copy:

- provider-specific assumptions into the core model,
- or a code-only notion of progress.

### From UlamAI, copy:

- truth orientation,
- artifact clarity,
- formalization/proving seriousness,
- and Lean backend awareness.

### From UlamAI, do not copy:

- its advanced proving machinery into OpenMath core when using the real tool as an optional backend is better.

---

## Implementation order

### Phase 1 — OpenMath core
Build from scratch:

- project/workspace model,
- gateway,
- Web UI,
- CLI,
- claim graph,
- Lean workbench,
- session summaries,
- run model,
- metric dashboards,
- native minimal backend,
- approvals,
- terminal infrastructure.

### Phase 2 — backend adapters
Add:

- UlamAI adapter,
- Aristotle adapter,
- backend detection + doctor,
- backend pages,
- structured job launching,
- artifact normalization.

### Phase 3 — research loops
Add:

- `program.md`-driven research policies,
- metric bundle evaluation,
- keep/discard candidate branches,
- benchmark harnesses,
- multi-agent conductor logic,
- and swarm claim/publish/sync.

### Phase 4 — scientific polish
Add:

- richer source ingestion,
- better literature/retrieval flows,
- more specialized research agent roles,
- domain packs,
- and editor extensions.

---

## Success criteria

OpenMath is successful when all of the following are true:

1. A mathematician can open one local web app and do real work without touching five unrelated tools.
2. The project remains understandable from its workspace files.
3. A broken theorem statement visibly invalidates downstream proofs.
4. The user can inspect every important agent action as a run, diff, artifact, or approval.
5. The user can use Aristotle CLI directly from the Web UI terminal.
6. The user can install UlamAI and immediately route selected tasks to it.
7. OpenMath still has value even if neither UlamAI nor Aristotle is installed.
8. OpenMath never confuses chat history with scientific memory.
9. The UI feels like a research control room, not a toy chatbot.
10. Lean remains the final judge.

---

## Final design stance

The final stance should be stated clearly in the README:

> **OpenMath is a self-contained research platform with its own native UI, orchestration, memory, and Lean workbench. It does not depend on OpenClaw or OpenGauss, and it does not try to clone UlamAI internally. Instead, OpenMath provides optional adapter integrations for external proving engines like UlamAI and Aristotle, while keeping one unified project model and user experience.**

That is the right shape.

---

## Upstream references

- UlamAI: https://github.com/ulamai/ulamai
- OpenClaw: https://github.com/openclaw/openclaw
- OpenClaw docs: https://docs.openclaw.ai/
- OpenGauss: https://github.com/math-inc/OpenGauss
- Karpathy autoresearch: https://github.com/karpathy/autoresearch
- Bandmaster: https://github.com/przchojecki/bandmaster
- Aristotle: https://aristotle.harmonic.fun/
- Aristotle CLI package: https://pypi.org/project/aristotlelib/
