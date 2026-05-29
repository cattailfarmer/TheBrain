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
- `<layer>.shaliach_self_negotiation.sop` records deterministic Shaliach perspective intentions, proposed responses, resolved intention, and unresolved tensions for the layer finding.
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

`negotiated_agent.worker_runner` and `scripts/worker-runner-preview.ps1` add the first non-mutating runner preview. The preview reads unread mailbox messages, drafts proposed lease records against the active frontier, and writes only to stdout, leaving claims and cursors untouched.

The same worker-runner CLI can now run explicit claim-record mode. That path claims bounded unread messages and writes `WorkerLeaseRecord` files under `coordination/workers/<worker_uuid>/leases/`, but still does not execute work, advance read cursors, or update Manager frontier state.

Worker cycle-record mode writes `WorkerCycleRecord` artifacts under `coordination/workers/<worker_uuid>/cycles/` from explicit claim, slice, proof, file, Shaliach, commit, or failure refs. These records are Manager review input and preserve the `worker_cycle_record_not_manager_approval` boundary.

The worker proof-command scaffold can run an explicit proof command and write success or failed-proof cycle evidence. Failed proofs also write `WorkerFailureRecord` artifacts with return code, output tails, dirty-worktree summary when git status is available, and safe-resume guidance; the command does not approve work or move the frontier.

`coordination/worker_execution_gate_design.sop` defines the authority boundary before any future autonomous worker can execute claimed implementation work. It requires Manager authorization, Shaliach execution clearance, lease validity, frontier matching, proof route evidence, and explicit blocking states before a runner may move beyond preview, claim, cycle, or proof evidence.

`negotiated_agent.execution_gate` implements the first gate record forms: `ManagerAuthorizationRecord`, `ShaliachExecutionClearance`, and `ExecutionGateDecision`. These make the future execution gate auditable without granting final acceptance, Manager authority, or completion approval.

The same module provides a deterministic execution gate evaluator. It combines Manager authorization, Shaliach clearance, worker lease status, and current frontier into allowed or blocked gate decisions such as `proof_only_allowed`, `blocked_by_manager`, `blocked_by_shaliach`, `stale_frontier`, and `lease_invalid`. It is scaffold policy, not live Manager/Shaliach deliberation.

`coordination/execution_gate_preview_cli_design.sop` defines a future no-write preview command for that evaluator. The preview command should parse existing Manager authorization, Shaliach clearance, and lease records, print an `ExecutionGateDecision` to stdout, and leave all worker, mailbox, and conversation files unchanged.

`negotiated_agent.execution_gate_cli` and `scripts/execution-gate-preview.ps1` implement that no-write preview. The CLI loads existing gate evidence refs, rejects malformed inputs, and prints the resulting `ExecutionGateDecision` without writing gate or worker artifacts.

`coordination/execution_gate_decision_writer_design.sop` defines the next explicit mutation boundary. A future writer may persist an `ExecutionGateDecision` under `coordination/workers/<worker_uuid>/execution_gates/` from existing Manager authorization, Shaliach clearance, lease, and frontier evidence. That write is review evidence only: it must not create authorizations or clearances, claim mailbox work, advance read cursors, write worker cycles, mutate the active frontier, execute implementation work, or touch the target workspace.

The existing execution gate CLI now has explicit write mode for that boundary. It evaluates the same inputs as preview mode, writes a single gate artifact, allows blocked decisions to be persisted for review, and refuses output collisions.

`coordination/gate_to_worker_cycle_bridge_design.sop` defines the next bridge from persisted gate decisions into `WorkerCycleRecord` evidence. Blocked, paused, stale, conflict, and proof-ready gate outcomes can become worker cycle records for review, but the bridge must not run proof commands, execute implementation work, advance read cursors, or move the Manager frontier.

`negotiated_agent.worker_runner_cli` and `scripts/worker-runner-preview.ps1` now support explicit gate-cycle bridge mode. It loads a persisted `ExecutionGateDecision`, maps the gate status to a non-executing `WorkerCycleRecord`, writes one cycle artifact, and rejects worker mismatches or existing cycle collisions.

`coordination/manager_reviewed_proof_handoff_design.sop` defines the next proof boundary. A `ready_for_proof` cycle is not enough by itself to run a command; a future `ManagerProofHandoffRecord` must approve the exact proof command and preserve the boundary that proof result cycles do not advance frontiers or authorize implementation execution.

`ManagerProofHandoffRecord` and the worker-runner CLI handoff writer implement the evidence side of that boundary. The writer validates a `ready_for_proof` cycle, exact proof command, execution gate ref, and current frontier, then writes a handoff artifact without running the command.

`coordination/handoff_aware_proof_runner_design.sop` defines how a later runner may consume an approved handoff. Consumption must validate the ready cycle, handoff, exact command, worker, and frontier before invoking the existing proof-command runner, and the result is a new proof cycle rather than Manager completion approval.

The worker-runner CLI now supports handoff consumption. It loads a `ManagerProofHandoffRecord`, loads the referenced `ready_for_proof` cycle, validates the current frontier, and calls the existing proof-command runner with handoff, ready-cycle, and gate refs carried into the new proof result cycle.

`coordination/gate_authorized_run_local_execution_design.sop` defines the first implementation-execution boundary after the gate and proof scaffolding. It allows only run-local generation under a worker execution root when an `execution_allowed` gate and matching `ready_for_run_local_execution` cycle exist. Generated files remain evidence for later Manager/Shaliach review, merge packet, apply, rollback, and post-apply acceptance protocols.

`RunLocalExecutionPlan`, `RunLocalExecutionResult`, and `scripts/run-local-execution-plan.ps1` provide the first dry-run planning step for that boundary. The planner writes only plan evidence under the selected run-local worker execution root and rejects proof-only gates.

`negotiated_agent.run_local_execution.execute_run_local_plan` adds the deterministic writer helper for that same boundary. It writes generated evidence only beneath the plan's run-local worker execution root and writes `run_local_execution_result.sop`; target workspace application remains reserved for later merge/apply protocols.

`scripts/run-local-execution-plan.ps1 -ExecutePlan` exposes that deterministic writer through the operator wrapper. The command consumes existing plan evidence and writes generated run-local artifacts only under the plan root.

`coordination/run_local_output_review_design.sop` defines the review boundary after run-local generation. Manager and Shaliach review artifacts must inspect the generated file refs and proof evidence before a non-mutating merge eligibility summary can say the output is eligible for later manual merge packet construction.

`negotiated_agent.run_local_review` and `scripts/run-local-output-review.ps1` implement the review and eligibility evidence path. The CLI can write Manager review, Shaliach review, and merge eligibility artifacts, but it never creates a manual merge packet or applies files.

`coordination/run_local_to_merge_packet_bridge_design.sop` defines the next bridge. Eligible run-local outputs may become draft accepted-file-map inputs for a later manual merge packet, but the bridge output is still not a `ManualMergePacket` and still cannot apply files. `negotiated_agent.run_local_merge_draft` owns the draft input record plus source-run-root and target-workspace containment checks, and `negotiated_agent.run_local_merge_draft_cli` writes `run_local_merge_draft_input.sop` without creating `manual_merge_packet.sop`.

`coordination/merge_draft_to_packet_proposal_design.sop` defines the next packet-construction boundary for run-local worker output. A draft input is not enough by itself: packet proposal construction requires Manager packet acceptance, Shaliach packet review, source and target containment rechecks, rollback evidence, and a verification command before creating a `ManualMergePacket` proposal. `negotiated_agent.packet_proposal` implements the pure records and builder; it writes nothing and cannot apply files or move the Manager frontier.

`negotiated_agent.packet_proposal_cli` and `scripts/packet-proposal.ps1` expose that boundary to operators. They can write Manager packet acceptance, Shaliach packet review, and `manual_merge_packet.sop` proposal evidence under the run-local root, but they do not create `apply_plan.sop` or mutate the target workspace.

`coordination/frontier_advancement_record_design.sop` defines the next Manager-control boundary. Packet proposals and proof artifacts may support moving the active work frontier, but `FrontierAdvancementRecord` must capture previous frontier, next frontier, Manager evidence, Shaliach evidence, proof refs, packet refs, and residual risk before any conversation surface is mutated. `negotiated_agent.frontier_advancement` implements the pure record and validation helper; it does not write active conversation surfaces.

`negotiated_agent.frontier_advancement_cli` and `scripts/frontier-advancement.ps1` write that advancement record under `coordination/frontier_advancements/<id>/`. This writer validates the current frontier and review statuses, then persists evidence only; an explicit later surface-application plan is still required before changing `current_frontier`.

`coordination/frontier_application_plan_design.sop` defines that next surface-application boundary. `negotiated_agent.frontier_application` loads a frontier advancement record, verifies the exact previous frontier, and builds a dry-run `FrontierApplicationPlan` before any later command changes `current_frontier`. This boundary remains separate from target workspace code application.

`negotiated_agent.frontier_application_cli` and `scripts/frontier-application-plan.ps1` write `frontier_application_plan.sop` beside the advancement record. The command may read the active conversation surface to verify the current frontier, but it does not write that surface.

`coordination/frontier_application_apply_design.sop` defines the future explicit surface mutation command. Applying a plan may replace the active conversation surface's `current_frontier` and append proof/completed-slice refs only after the exact previous frontier still matches. Stale plans should produce blocked result artifacts instead of overwriting newer work.

`FrontierApplicationResult` records applied and stale-blocked outcomes before the mutation helper is added. The same module can load `frontier_application_plan.sop` and synthesize result evidence, keeping the actual surface write as a separate boundary.

The frontier application helper now performs that surface write under exact previous-frontier match: it updates `current_frontier`, appends proof refs, appends completed-slice refs, and returns a `FrontierApplicationResult`. If the active surface has moved, it returns a stale-blocked result and preserves the surface.

`scripts/frontier-application-plan.ps1 -ApplyPlan` exposes that explicit surface application path. It writes `frontier_application_result.sop` for applied and stale-blocked outcomes and does not touch target workspace code.

`coordination/narrative_coverage_stale_check_design.sop` defines the next narrative-memory boundary. It extends the existing artifact-presence coverage check into explicit stale-check records over narrative surface, manager notice, refined plan, active conversation surface, long-run checkpoint, and latest run manifest refs. The design keeps updates append-only.

`NarrativeStaleCheckRecord` now recomputes expected narrative arcs, latest-run references, and active-frontier references from current files. It reports stale claims and recommended updates without rewriting the narrative surface.

`scripts/narrative-coverage.ps1 -StaleCheck` exposes the stale-check writer. It writes `coordination/narrative_stale_check.sop`, rejects output collisions, and does not mutate `project_narrative_surface.sop`.

`coordination/narrative_coverage_update_record_design.sop` defines the next narrative-memory artifact. `NarrativeCoverageUpdateRecord` will transform stale-check recommendations into append candidates and deferred update reasons while preserving stale claims and keeping narrative mutation behind a later explicit boundary.

`build_narrative_coverage_update_record` implements that artifact boundary as a pure function. It carries recommended updates forward, defers duplicate or current-state recommendations, preserves stale claim refs, and writes only SOP evidence.

`scripts/narrative-coverage.ps1 -UpdateRecord` exposes the update-record writer. It consumes an explicit stale-check ref and persists update evidence while keeping project narrative append behavior reserved for a later reviewed command.

`coordination/reviewed_narrative_append_design.sop` specifies that later command. It requires Manager approval, Shaliach clearance, and a narrative surface guard, then records applied or blocked outcomes without changing old narrative lines or advancing the Manager frontier.

`ManagerNarrativeAppendApproval` and `ShaliachNarrativeAppendClearance` implement the review evidence side of that boundary. Their `allows_append` properties are deliberately local predicates; a later append result/helper must still validate refs, guards, and update entries.

`NarrativeAppendResult` and `build_narrative_append_result` add that validation as a pure planning step. The result records ready and blocked outcomes, including stale surface guards, without appending to `project_narrative_surface.sop`.

`apply_reviewed_narrative_append` is the first append-capable helper. It requires a ready result and an exact surface guard, appends only to the end of the narrative surface, and returns an applied or blocked `NarrativeAppendResult`.

`coordination/reviewed_narrative_append_cli_design.sop` defines the operator wrapper boundary. The future CLI must parse review artifacts rather than accept freeform statuses, write result artifacts for blocked and applied outcomes, and require an explicit apply flag before mutation.

The parser layer for that wrapper is implemented now. It extracts fields from `NarrativeCoverageUpdateRecord`, `ManagerNarrativeAppendApproval`, and `ShaliachNarrativeAppendClearance` SOP artifacts, and deliberately limits itself to field extraction plus header rejection.

`negotiated_agent.narrative_append_cli` and `scripts/narrative-append.ps1` implement plan mode. They persist a `NarrativeAppendResult` from loaded artifacts and the supplied surface guard, while leaving apply mode as a later explicit boundary.

Apply mode is now explicit through `--apply` / `-Apply`. It reuses the loaded artifacts, checks the same guard through `apply_reviewed_narrative_append`, writes blocked results for stale cases, and appends reviewed entries only at the end of the narrative surface.

Guard discovery is also exposed through `--guard-discovery` / `-GuardDiscovery`. It prints the current narrative surface guard and carries the boundary `guard_discovery_not_append_approval`.

`coordination/narrative_append_review_writer_design.sop` specifies future writer modes for Manager approval and Shaliach clearance artifacts. Those modes are evidence writers only and must remain separate from plan and apply mode.

The Manager approval writer mode is implemented as `--manager-approval` / `-ManagerApproval`. It writes `ManagerNarrativeAppendApproval` evidence with approval status, approved update count, frontier, and residual risks.

The Shaliach clearance writer mode is implemented as `--shaliach-clearance` / `-ShaliachClearance`. It writes `ShaliachNarrativeAppendClearance` evidence with checked protocols, findings, and required rework while remaining separate from append apply mode.

`coordination/reviewed_narrative_append_e2e_fixture_design.sop` describes the next proof layer: a temporary-project fixture that runs update-record, guard, review, plan, and apply steps end to end without mutating the live project narrative.

That e2e fixture is now implemented in the test suite. It proves the deterministic reviewed append workflow across CLI main functions while preserving the live workspace narrative surface.

`coordination/review_artifact_synthesis_design.sop` defines deterministic review drafts from `NarrativeCoverageUpdateRecord` evidence. The draft policy can derive approval counts and required rework, but carries an explicit boundary that it is not live Manager or Shaliach deliberation.

The pure synthesis builders are implemented in `negotiated_agent.narrative_append`. They derive Manager approval counts from appended updates and Shaliach required rework from deferred updates, while preserving caution fields in the generated review evidence.

`--synthesize-review-drafts` / `-SynthesizeReviewDrafts` exposes the synthesis path through the narrative append CLI and wrapper. It writes both review artifacts with collision checks and does not plan or apply narrative updates.

`coordination/shaliach_self_negotiation_record_design.sop` defines deterministic Shaliach self-negotiation records for pre-live scaffolding. `ShaliachSelfNegotiationRecord` is implemented, Shaliach findings can cite it through `self_negotiation_ref`, and dry-runs write one artifact per layer. The record preserves multiple advisory perspectives, resolved intention, and unresolved tensions without claiming live internal deliberation.

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
