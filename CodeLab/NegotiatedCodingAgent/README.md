# Negotiated Coding Agent

A local-LLM coding-agent prototype that makes multiple model roles negotiate layered flowcharts and structured SOP packages before writing code.

The core idea is deliberately staged:

1. Application-level flowchart
2. Subsystem-level flowchart
3. Component-level flowchart
4. Code-level flowchart
5. Code generation from the settled code-level flowchart

Each layer runs a negotiation pass across multiple LLM roles. The system then asks an arbiter model to merge the proposals into one settled flowchart for the next layer.

The current architecture names are:

- `Shaliach`: protocol counsel/enforcement for SOP, SJS, DataDrivenDesign, lineage, uncertainty, and artifact form.
- `Manager`: objective integrity, layer approval, work slicing, implementation review, and final acceptance.
- `Directors`: medium-weight flow-control negotiators.
- `Programmers`: bounded implementation agents.

## Status

This is a first runnable scaffold. It supports Ollama-compatible local models, OpenAI-compatible endpoints for future vLLM/LM Studio routing, and deterministic dry-run mode for testing the pipeline without an LLM server.

## Quick Start

From this folder:

```powershell
.\scripts\run-dry.ps1
```

For an unattended-work checkpoint:

```powershell
.\scripts\long-run-harness.ps1
```

With Ollama running locally:

```powershell
.\scripts\run-ollama.ps1
```

By default the config uses:

- `qwen2.5-coder:7b` for planner/coder roles
- `llama3.1:8b` for critic/arbiter roles

Edit `agent.config.json` to use the models you actually have installed.
Increasing `negotiation.rounds_per_layer` above `1` carries prior Director disagreement into later proposal rounds.

## Output

Runs are written under `runs/<timestamp>/`:

- `protocol_activation.sop`
- `<layer>.flowchart.md`
- `<layer>.package.sop`
- `DirectorDisagreementLedger` inside each layer package
- `<layer>.shaliach_finding.sop`
- `<layer>.shaliach_response.sop` when Shaliach requires a response
- `<layer>.manager_review.sop`
- `programmer_assignment_plan.sop`
- `multi_programmer_execution_plan.sop`
- `multi_programmer_merge_review_input.sop`
- `merge_conflict_ledger.sop`
- `merge_review_decision.sop`
- `manual_merge_packet.sop` when merge review is ready and no conflicts block packet creation
- `apply_plan.sop` and `apply_result.sop` as dry-run evidence when a manual merge packet is generated
- explicit apply/rollback command artifacts such as `apply_mutation_preflight.sop`, `snapshot_materialization.sop`, `verification_result.sop`, `rollback_preview.sop`, `rollback_result.sop`, and `post_apply_acceptance.sop` when those operator commands are run
- `WS001_core_implementation.<Programmer>.work_slice.sop`
- `WS001_core_implementation.<Programmer>.raw.md`
- `WS001_core_implementation.<Programmer>.programmer_report.sop`
- `WS001_core_implementation.<Programmer>.manager_review.sop`
- `WS001_core_implementation.<Programmer>.execution_result.sop`
- `coder.raw.md`
- `implementation/`
- `file_change_surface.sop`
- `file_change_index.sop`
- `run_manifest.sop`
- `run_blocked.sop` and `run_repair_plan.sop` for blocked runs
- `negotiation_log.jsonl`

The layer-specific files are emitted for each configured negotiation layer, currently:

- `application.flowchart.md`
- `application.package.sop`
- `application.manager_review.sop`
- `subsystem.flowchart.md`
- `subsystem.package.sop`
- `subsystem.manager_review.sop`
- `component.flowchart.md`
- `component.package.sop`
- `component.manager_review.sop`
- `code.flowchart.md`
- `code.package.sop`
- `code.manager_review.sop`
- `WS001_core_implementation.<Programmer>.work_slice.sop`
- `WS001_core_implementation.<Programmer>.programmer_report.sop`
- `WS001_core_implementation.<Programmer>.manager_review.sop`

The generated implementation is intentionally conservative: the coder writes files only inside the run folder unless you later add an explicit workspace writer.

To validate a generated manual merge packet without applying it to the workspace:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\apply-merge-dry-run.ps1 -RunRoot runs\<timestamp> -TargetWorkspaceRoot C:\Project\TheBrain
```

This command writes dry-run validation artifacts under the run root. It does not apply generated code to `TargetWorkspaceRoot`.

Worker-runner coordination support is also staged. The current commands can preview unread mailbox work, explicitly claim bounded work and write lease evidence, record cycle outcomes from explicit refs, and run explicit proof commands with cycle/failure evidence:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\worker-runner-preview.ps1 -Worker <worker-uuid> -Mailbox director_pool -MaxClaims 1
powershell -ExecutionPolicy Bypass -File scripts\worker-runner-preview.ps1 -Worker <worker-uuid> -Mailbox director_pool -MaxClaims 1 -ClaimRecord
powershell -ExecutionPolicy Bypass -File scripts\worker-runner-preview.ps1 -Worker <worker-uuid> -Mailbox director_pool -RecordCycle -CycleId <cycle-id> -CycleStatus completed -SliceRef <slice-ref>
powershell -ExecutionPolicy Bypass -File scripts\worker-runner-preview.ps1 -Worker <worker-uuid> -Mailbox director_pool -RunProofCommand "powershell -ExecutionPolicy Bypass -File scripts\test.ps1" -CycleId <cycle-id>
```

These commands write worker evidence under `coordination/workers/<worker-uuid>/` when run in claim, cycle, or proof mode. They do not make the system a full autonomous scheduler, do not approve Manager frontier changes, and do not mutate target workspace code.

Before any future autonomous worker executes implementation work, the execution gate must be represented. Current gate records are `ManagerAuthorizationRecord`, `ShaliachExecutionClearance`, and `ExecutionGateDecision`; the deterministic evaluator can classify gate state as proof-only allowed or blocked by Manager, Shaliach, stale frontier, or invalid lease. This is prerequisite evidence, not live Manager/Shaliach deliberation and not permission to apply target workspace changes.

The current preview command prints gate decisions without writing files. The next designed boundary is an explicit gate-decision writer that persists `ExecutionGateDecision` review evidence under a worker execution-gates directory while still refusing to create authorizations, claim work, advance frontiers, execute implementation work, or mutate the target workspace.

That explicit write mode is available through `scripts/execution-gate-preview.ps1 -Write`; default command behavior remains a no-write preview.

The next planned bridge maps persisted gate decisions into worker-cycle review evidence. It is designed to make blocked and proof-ready outcomes visible to the Manager without running proofs, executing implementation work, or moving the frontier.

The worker runner wrapper can now record that bridge explicitly with `scripts/worker-runner-preview.ps1 -RecordGateCycle -ExecutionGateRef <gate-ref>`.

The next proof boundary is designed in `coordination/manager_reviewed_proof_handoff_design.sop`: proof-ready cycle evidence still needs an explicit Manager proof handoff before a command runner consumes it.

The worker runner wrapper can now write that handoff evidence with `scripts/worker-runner-preview.ps1 -WriteProofHandoff`; command execution remains a separate step.

The planned handoff-aware proof runner is specified in `coordination/handoff_aware_proof_runner_design.sop`; it consumes approved proof handoffs into new proof result cycles without treating them as implementation execution or completion approval.

That consumption path is available through `scripts/worker-runner-preview.ps1 -ConsumeProofHandoff`.

The next designed boundary is run-local implementation execution from an `execution_allowed` gate. It is intentionally still not target workspace mutation; generated outputs must flow through later review, merge, apply, rollback, and acceptance records.

The dry-run planner for that boundary is `scripts/run-local-execution-plan.ps1`; it writes plan evidence only.

The run-local execution writer helper now writes deterministic generated evidence under the plan root, still not into the target workspace.

The same wrapper supports `-ExecutePlan` to produce run-local generated evidence from a plan.

Run-local generated outputs still need Manager and Shaliach review before merge eligibility; that boundary is specified in `coordination/run_local_output_review_design.sop`.

The review wrapper is `scripts/run-local-output-review.ps1`; it can write review and eligibility evidence, not merge packets.

The next bridge is specified in `coordination/run_local_to_merge_packet_bridge_design.sop`: eligible run-local outputs can become draft merge inputs, still not manual merge packets or apply actions. `negotiated_agent.run_local_merge_draft` implements the draft input record and source/target containment checks. The wrapper `scripts/run-local-merge-draft.ps1` writes `run_local_merge_draft_input.sop`; it still does not create `manual_merge_packet.sop` or apply files.

`coordination/merge_draft_to_packet_proposal_design.sop` defines the next boundary: a draft input can become a `ManualMergePacket` proposal only after fresh Manager packet acceptance and Shaliach packet review evidence. `negotiated_agent.packet_proposal` implements those record types and the pure proposal builder; the proposal still cannot apply files or advance the frontier.

The wrapper `scripts/packet-proposal.ps1` writes Manager packet acceptance, Shaliach packet review, and `manual_merge_packet.sop` proposal evidence. It does not create apply artifacts or touch the target workspace.

`coordination/frontier_advancement_record_design.sop` defines the next Manager-control boundary: frontier advancement should be a reviewed evidence record before any active conversation surface changes. `negotiated_agent.frontier_advancement` implements the pure record and validation helper. Packet proposals, proof refs, and Shaliach reviews can support that record, but they do not mutate `current_frontier` by themselves.

The wrapper `scripts/frontier-advancement.ps1` writes `frontier_advancement_record.sop` under `coordination/frontier_advancements/<id>/`. It is still evidence only; it does not apply the frontier change to the active conversation surface.

`coordination/frontier_application_plan_design.sop` defines the next boundary after that evidence: a dry-run plan must verify the active conversation frontier before any future command mutates `current_frontier`. `negotiated_agent.frontier_application` implements the plan record and loader/helper for that dry-run step.

The wrapper `scripts/frontier-application-plan.ps1` writes `frontier_application_plan.sop` beside a frontier advancement record. It does not mutate the active conversation surface.

`coordination/frontier_application_apply_design.sop` defines the next explicit mutation boundary: a future apply command may update the active conversation frontier only from a valid plan, and must write a result artifact for applied or stale-blocked outcomes.

`negotiated_agent.frontier_application` now also includes `FrontierApplicationResult` plus plan loading and result-building helpers for applied and stale-blocked outcomes.

The same module now has an explicit helper that can apply a valid frontier application plan to a conversation surface, append proof/completed-slice refs, and return a result; stale surfaces return a blocked result and remain unchanged. A CLI wrapper remains the next boundary.

The wrapper `scripts/frontier-application-plan.ps1 -ApplyPlan` applies a frontier application plan and writes `frontier_application_result.sop`. It mutates only the active conversation surface named by the plan and never target workspace files.

`coordination/narrative_coverage_stale_check_design.sop` defines the next narrative-memory boundary: recompute coverage and stale claims from current surfaces, then write evidence without rewriting narrative history.

`negotiated_agent.narrative_coverage` now includes `NarrativeStaleCheckRecord`, which recomputes expected narrative arcs, latest-run references, and active-frontier references without mutating the narrative surface.

The wrapper `scripts/narrative-coverage.ps1 -StaleCheck` writes `coordination/narrative_stale_check.sop` as evidence only; it refuses to overwrite an existing stale-check file.

Programmer swarm support is currently staged. The runtime can represent multiple planned slices, write an assignment plan, and execute planned assignments sequentially into separate run-local output roots. `coordination/multi_programmer_runner_design.sop` defines the runner contract for per-Programmer outputs and merge-review readiness; merge remains pending rather than applied to the target workspace.

## Design

See `docs/architecture.md`.
For long-running and multi-conversation operator helpers, see `docs/coordination_operator_guide.md`.
For current local serving readiness and the disk-conscious setup ladder, see `docs/local_model_serving.md`.
For the RTX 5090 WSL2/vLLM serving path, see `docs/vllm_wsl2_operator_guide.md`.
For a focused OpenAI-compatible endpoint check, run `.\scripts\openai-health.ps1`.
For a non-mutating live route draft after or before endpoint setup, run `.\scripts\live-route-draft.ps1`.

## Specification

The hierarchical manager/council/worker architecture is captured in `specifications/Hierarchical_Agent_Swarm.sop`.
The original dictated intent is preserved separately in `specifications/source/2026-05-29_hierarchical_agent_swarm_source.sop`.
