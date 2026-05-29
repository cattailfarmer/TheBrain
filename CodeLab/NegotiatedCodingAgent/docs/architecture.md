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

## Programmer Assignment Plan

After the code-layer package is approved, the runtime writes `programmer_assignment_plan.sop`. This is a pre-execution planning artifact that maps approved work slices to configured Programmers.

Current boundary:

- assignment planning is implemented;
- one initial work slice is executed;
- parallel Programmer execution is not yet implemented;
- merge review for multiple Programmer outputs is not yet implemented.

This keeps the future swarm path explicit without pretending it already exists.

## Multi-Slice Planning Scaffold

The runtime can also represent a small deterministic set of planned implementation slices:

- core implementation;
- verification and test support;
- documentation and operator notes.

This scaffold is used to prove assignment planning across multiple configured Programmers. It is not yet semantic extraction from an arbitrary code package, and the orchestrator still executes one initial implementation slice.

Before any future parallel execution, `coordination/programmer_merge_review_protocol.sop` defines the planned merge-review gates: separate Programmer reports, conflict visibility, Manager review, Shaliach review when scope or lineage changes, file-change lineage, and verification after merge.

`coordination/multi_programmer_runner_design.sop` now connects that protocol to an executable runner contract. It defines runner inputs, assignment lifecycle states, per-Programmer artifact names, merge-review readiness, and the non-destructive boundary that keeps multi-Programmer output run-local until merge and rollback policy exist.

The current orchestrator uses the same assignment artifact contract for the executed Programmer path. It executes planned assignments sequentially, writes each output under a per-assignment run-local root, records assignment execution results, and keeps file-change lineage pointed at those isolated output paths. Merge remains a visible pending review step rather than a target-workspace mutation.

Before merge, `merge_conflict_ledger.sop` records same-file overlaps across isolated assignment roots. `merge_review_decision.sop` turns that evidence into a Manager-facing status such as blocked by conflict or ready for manual merge review. This is conflict visibility only: it does not choose a winner, combine code, or write to the target workspace.

`coordination/manual_merge_packet_policy.sop` defines the next boundary before target-workspace mutation: a future merge packet must carry source assignment refs, accepted file maps, rejected output refs, rollback instructions, Manager acceptance, Shaliach review, and verification evidence.

`negotiated_agent.merge_packet` provides the pure record forms for that packet and rollback plan, plus target-path containment checks. These records still do not apply changes; they make a future apply command prove its evidence first.

When merge review is ready and conflict-free, the orchestrator can emit `manual_merge_packet.sop` as a dry-run packet. Conflict-blocked runs suppress this packet and keep the conflict ledger as the next review surface.

`coordination/operator_approved_apply_policy.sop` defines the next safety boundary. Normal negotiation runs still never mutate the target workspace; any future apply command must default to dry-run and require an explicit mutation acknowledgement, path checks, rollback snapshots, and verification.

`negotiated_agent.apply_plan` now provides pure `ApplyPlan` and `ApplyResult` records for that future command. These records preserve dry-run defaults, snapshot plans, rollback commands, and verification refs without performing any file writes.

For conflict-free packet runs, the orchestrator emits `apply_plan.sop` and `apply_result.sop` as dry-run evidence. Conflict-blocked runs do not emit apply evidence, keeping the unresolved merge decision as the active boundary.

`coordination/apply_command_dry_run_cli_design.sop` defines the first future CLI step: validate a manual merge packet and write dry-run apply artifacts from explicit `--run-root` and `--target-workspace-root` arguments, while rejecting mutation behavior.

`negotiated_agent.apply_cli` and `scripts/apply-merge-dry-run.ps1` implement that dry-run validation path. The CLI writes `apply_plan.sop`, `apply_result.sop`, and `apply_command_log.sop` under the run root; it rejects the mutation acknowledgement flag because mutation mode is not implemented.

`coordination/operator_approved_apply_mutation_design.sop` now defines the later mutation contract without enabling it. It requires explicit operator acknowledgement, same-run merge evidence, conflict-free status, Manager acceptance, Shaliach review, target-path containment checks, pre-write snapshots, verification, rollback evidence, and post-apply review gates before target workspace mutation can be implemented.

`negotiated_agent.apply_preflight` implements the first pieces of that contract: mutation preflight validation, rollback snapshot materialization helpers, and target file copying behind explicit operator acknowledgement. Snapshot materialization writes rollback evidence under the run root for existing target files and records create-new operations before generated source files are applied to the explicit target workspace.

`coordination/rollback_command_design.sop` defines the matching rollback contract. It requires explicit acknowledgement, same-run apply evidence, snapshot restoration for replaced files, removal only for files created by the apply result, verification evidence, and a durable `rollback_result.sop`.

`negotiated_agent.rollback` provides rollback preview records and explicit-acknowledgement rollback execution. The preview can distinguish snapshot restoration, created-file removal, and skipped files. The rollback writer restores snapshot-backed files and removes create-new files only when the operator supplies the target workspace and acknowledgement flag.

`coordination/post_apply_acceptance_design.sop` defines the next governance boundary: apply and rollback filesystem evidence are not final acceptance. A future `PostApplyAcceptanceRecord` must reference apply, verification, rollback when present, Manager decision, Shaliach decision, accepted files, and remaining risks.

`negotiated_agent.post_apply` provides that pure acceptance record model. It can synthesize accepted, verification-blocked, rollback-acknowledged, rollback-blocked, and Shaliach-blocked outcomes while preserving the boundary that acceptance records do not perform filesystem operations.

The explicit apply and rollback mutation CLIs now write `post_apply_acceptance.sop` from their actual run evidence. This makes final acceptance visible as a separate record after verification or rollback rather than burying it inside filesystem success.

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
- `DirectorDisagreementLedger` inside the layer package preserves Director perspective diversity before Manager settlement.
- `<layer>.shaliach_finding.sop` records no-finding, warning, pause, or rework findings.
- `<layer>.shaliach_response.sop` records repair steps when Shaliach warning or rework coordination is required.
- `file_change_surface.sop` and `file_change_index.sop` map generated files to solution records and justification refs.
- `run_manifest.sop` indexes run artifacts for reentry.
- `run_blocked.sop` and `run_repair_plan.sop` appear when Shaliach or Manager blocks progress.

These artifacts are evidence surfaces. They do not replace direct file inspection, tests, user instruction, or signed specifications.

## Shaliach Perspective Trace

Shaliach findings and response coordination artifacts include selected internal perspective records:

- `ProtocolCounsel`: checks SOP, SJS, DataDrivenDesign, and local specification obligations.
- `BoundaryMarshal`: checks scope, role, identity, authority, and lineage boundaries.
- `EvidenceClerk`: checks support strength, provenance, and missing evidence.
- `FailureExaminer`: checks blockers and recovery paths when relevant.
- `FormKeeper`: checks artifact shape and required fields.
- `ResponseCoordinator`: records the least intrusive sufficient response chosen from the finding.

These records are deterministic scaffold traces. They make Shaliach’s reasoning legible, but they are not yet full live model-negotiated Shaliach self-debate.

## Coordination Surfaces

The runtime includes mailbox, claim, read cursor, conflict, and rendezvous packet helpers for multiple conversations working in the same project:

- mailbox messages are append-only coordination carriers;
- claims are append-only evidence, not scheduler locks;
- read cursors mean observed, not completed;
- rendezvous packets are handoff carriers with explicit boundaries.

Operator commands for these helpers are documented in `docs/coordination_operator_guide.md`.

`coordination/worker_runner_design.sop` defines the next coordination runtime boundary. A future worker runner must write lease, cycle, pause, and failure records around mailbox claims, preserve Manager frontier authority, honor Shaliach pause conditions, and treat claims as evidence rather than trusted distributed locks.

`negotiated_agent.worker_lifecycle` implements the first record types for that boundary: `WorkerLeaseRecord`, `WorkerCycleRecord`, and `WorkerFailureRecord`. They serialize the worker evidence needed for future automation without claiming to lock work, approve frontiers, or repair failures automatically.

## Director Disagreement Ledger

The layer package includes `DirectorDisagreementLedger` before the Manager review sections. Its purpose is to keep distinct Director positions visible instead of allowing the settled flowchart to erase every disagreement.

In dry-run mode, Directors emit deterministic stance differences:

- `SystemsDirector` emphasizes structure, interfaces, decomposition, and flow control.
- `FailureDirector` emphasizes failure modes, boundary mistakes, recovery paths, and unresolved risks.

This proves the artifact path and review shape. It is not proof that live local models have achieved useful diversity; that still depends on model serving, model selection, and real proposal quality.

When `rounds_per_layer` is greater than one, later Director proposal prompts include prior Director concerns. This carry-forward keeps disagreement visible across rounds before Manager settlement. It is prompt context, not full deliberative memory or a replacement for the package-level `DirectorDisagreementLedger`.

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
