# Architecture

## Purpose

The system is a local coding-agent kernel where multiple LLM roles negotiate a program shape before implementation begins.

The user gives an objective. The agent system turns that objective into progressively narrower flowcharts:

```text
objective
  -> application flowchart
  -> subsystem flowchart
  -> component flowchart
  -> code flowchart
  -> files
```

## Negotiation Roles

`Shaliach`
: Protocol counsel and enforcement for SOP, SJS, DataDrivenDesign, lineage, uncertainty, and artifact form. It currently emits finding and response-coordination artifacts from deterministic runtime checks and scaffolded faculty perspectives.

`Manager`
: Owns objective integrity, layer approval, work slicing, implementation review, and final acceptance. Manager approval is required before descent to the next flowchart layer.

`Directors`
: Medium-weight flow-control negotiators. They produce proposals for each layer and supply evidence for SJS and DataDesign ledgers.

`Programmers`
: Bounded implementation agents. They write implementation output only after the code-layer package is approved.

Roles and model assignments are configured in `agent.config.json`. The current runtime supports deterministic dry-run mode, Ollama-style local routing, and OpenAI-compatible routing for future vLLM serving.

## Four Flowchart Layers

### Application

Defines the whole product boundary:

- users and entry points
- main capabilities
- external dependencies
- persistence or integration surfaces
- application-level failure states

### Subsystem

Splits the application into cooperating subsystems:

- UI/API/CLI surfaces
- domain logic
- storage
- validation
- test harness

### Component

Splits one subsystem into components:

- modules/classes/functions
- state ownership
- inputs and outputs
- contracts between components

### Code

Defines code-level program flow:

- files to create
- public functions/classes
- control flow
- data structures
- test strategy

The coder only starts after this level exists.

## Flowchart Format

The expected flowchart format is Markdown:

```markdown
# <Layer> Flowchart

## Scope

## Nodes
- N1: ...

## Edges
- N1 -> N2: ...

## Data

## Risks

## Open Questions
```

This format is easy for humans to inspect and simple for local LLMs to maintain.

## Governance Artifacts

Each run records protocol and review surfaces alongside the flowcharts:

- `protocol_activation.sop` records active SOP protocol references and the authority boundary.
- `<layer>.package.sop` carries the flowchart, Director proposals, SJS ledger, DataDesign ledger, Shaliach finding, and Manager decision.
- `<layer>.shaliach_finding.sop` records no-finding, warning, pause, or rework findings.
- `<layer>.shaliach_response.sop` records repair steps when Shaliach warning or rework coordination is required.
- `file_change_surface.sop` and `file_change_index.sop` map generated files to solution records and justification refs.
- `run_manifest.sop` indexes run artifacts for reentry.
- `run_blocked.sop` and `run_repair_plan.sop` appear when Shaliach or Manager blocks progress.

These artifacts are evidence surfaces. They do not replace direct file inspection, tests, user instruction, or signed specifications.

## Coordination Surfaces

The runtime includes mailbox, claim, read cursor, conflict, and rendezvous packet helpers for multiple conversations working in the same project:

- mailbox messages are append-only coordination carriers;
- claims are append-only evidence, not scheduler locks;
- read cursors mean observed, not completed;
- rendezvous packets are handoff carriers with explicit boundaries.

Operator commands for these helpers are documented in `docs/coordination_operator_guide.md`.

## Local Model Serving

The preferred high-throughput route for this machine is WSL2 plus vLLM serving an OpenAI-compatible endpoint. The current preflight detects the RTX 5090 and records WSL as the blocker. Local serving remains uninstalled until a human performs the WSL2/vLLM setup.

Current serving support:

- dry-run for deterministic governance proof;
- Ollama route when installed and configured;
- OpenAI-compatible route for vLLM or similar servers;
- role-model profile and endpoint healthcheck reports under `coordination/`.

The manual setup path is documented in `docs/vllm_wsl2_operator_guide.md`.

## Implementation Boundary

The first version writes generated code into a timestamped run directory. That keeps generated files auditable and avoids letting the agent overwrite an existing project before the writer policy is mature.
