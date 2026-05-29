# Coordination Operator Guide

This guide covers the current operator helpers for long-running and multi-conversation work. These tools create and inspect SOP coordination carriers; they do not grant command authority, scheduler locks, or semantic validation by themselves.

## Proof Runs

Use deterministic dry-runs for artifact checks:

```powershell
.\scripts\run-dry.ps1
```

Use mailbox suppression when the run is only a proof pass and should not publish live `rework_notice` messages:

```powershell
.\scripts\run-dry.ps1 -SuppressMailbox
```

The run still writes local Shaliach response artifacts and `run_manifest.sop`.

## Shaliach Response Traces

When a run writes `<layer>.shaliach_response.sop`, inspect `perspective_trace` fields before assigning repair work. They explain why the response was selected, usually from protocol, evidence, form, and response-coordination perspectives.

These traces are useful repair evidence, but they are deterministic scaffold records. Treat them as Shaliach support context, not as a substitute for Manager review or future live Shaliach internal negotiation.

## Shaliach Self-Negotiation Artifacts

Each layer dry-run writes `<layer>.shaliach_self_negotiation.sop` beside `<layer>.shaliach_finding.sop`. Read it before treating a finding as resolved or assigning rework.

Key fields:

- `status`: `resolved`, `advisory`, or `rework_required`.
- `perspective`: deterministic Shaliach perspectives such as `legal_counsel`, `protocol_officer`, `failure_advocate`, and `purpose_guardian`.
- `proposed_response`: the response each deterministic perspective supports.
- `resolved_intention`: the reconciled Shaliach intention for this finding.
- `unresolved_tension`: tension that should remain visible instead of being smoothed away.

Status meanings:

- `resolved`: no unresolved tension was detected by the deterministic scaffold.
- `advisory`: a non-blocking tension should be carried forward or repaired opportunistically.
- `rework_required`: a blocking tension should be repaired before treating the layer as clean.

The file is intentionally bounded. It is evidence for Shaliach review, and finding/response artifacts may cite it through `self_negotiation_ref`, but it is not live model self-deliberation, Manager approval, file-application permission, or a replacement for direct artifact inspection.

Inspect a self-negotiation artifact with:

```powershell
.\scripts\shaliach-self-negotiation.ps1 -Artifact .\runs\<timestamp>\<layer>.shaliach_self_negotiation.sop
```

The command prints an inspection summary only. It does not rewrite the artifact, advance the frontier, or approve the layer.

Inspect consistency across the self-negotiation, finding, and optional response artifacts with:

```powershell
.\scripts\shaliach-cross-inspect.ps1 `
  -SelfNegotiation .\runs\<timestamp>\<layer>.shaliach_self_negotiation.sop `
  -Finding .\runs\<timestamp>\<layer>.shaliach_finding.sop `
  -Response .\runs\<timestamp>\<layer>.shaliach_response.sop
```

The command returns exit code `0` for structurally consistent artifacts and `1` for mismatches. It is a consistency check only, not semantic validation or Manager approval.

## Run Manifests

Each completed or blocked run writes `run_manifest.sop`. Validate that listed artifact refs exist:

```powershell
.\scripts\validate-run-manifest.ps1 -Manifest .\runs\<timestamp>\run_manifest.sop
```

This is a file-existence check, not semantic artifact validation.

## Dry-Run Apply Validation

When a run emits `manual_merge_packet.sop`, validate the packet without applying it to the target workspace:

```powershell
.\scripts\apply-merge-dry-run.ps1 -RunRoot .\runs\<timestamp> -TargetWorkspaceRoot C:\Project\TheBrain
```

This writes or refreshes `apply_plan.sop`, `apply_result.sop`, and `apply_command_log.sop` under the run root. It does not write to `TargetWorkspaceRoot`.

The dry-run CLI rejects mutation acknowledgement flags by design. Treat `apply_result.sop` with `apply_status` set to `dry_run` as validation evidence only, not as proof that code was applied.

When the mutation acknowledgement flag is supplied, the command runs the preflight gate, writes `apply_mutation_preflight.sop`, writes `snapshot_materialization.sop` under the run root, applies accepted packet files to the explicit target workspace, runs verification, writes `verification_result.sop`, writes `apply_result.sop`, and writes `post_apply_acceptance.sop`. Use this only with a deliberate target workspace and reviewed packet evidence.

Before running any future rollback mutation, generate a preview:

```powershell
.\scripts\rollback-preview.ps1 -RunRoot .\runs\<timestamp>
```

This writes `rollback_preview.sop` from `apply_result.sop` and `snapshot_materialization.sop`. It does not restore or remove target files.

To execute rollback, add the explicit mutation acknowledgement and target workspace:

```powershell
.\scripts\rollback-preview.ps1 -RunRoot .\runs\<timestamp> -TargetWorkspaceRoot C:\Project\TheBrain -IUnderstandThisMutatesWorkspace
```

Rollback restores files from snapshot refs and removes files recorded as created by the apply result. It writes `rollback_result.sop` and refreshes `post_apply_acceptance.sop` with the rollback outcome.

Expected dry-run artifacts:

- `apply_plan.sop`: target paths, snapshot plan, rollback reference, and verification command that would be used by a future apply command.
- `apply_result.sop`: `apply_status` remains `dry_run`; proposed target files are listed as skipped, not applied.
- `apply_command_log.sop`: records whether validation completed or was rejected.

Expected mutation-only artifacts:

- `verification_result.sop`: command, return code, and output tails from post-apply verification.
- `post_apply_acceptance.sop`: Manager/Shaliach acceptance synthesis over apply, verification, and rollback evidence. This is still a record boundary, not an extra filesystem operation.

If the merge decision is `blocked_by_conflict`, inspect `merge_conflict_ledger.sop` first. Do not run dry-run apply validation until a conflict-free `manual_merge_packet.sop` exists.

The dry-run command can be rerun after changing only validation arguments, such as a different verification command:

```powershell
.\scripts\apply-merge-dry-run.ps1 -RunRoot .\runs\<timestamp> -TargetWorkspaceRoot C:\Project\TheBrain -VerificationCommand "powershell -ExecutionPolicy Bypass -File scripts\test.ps1"
```

## Long-Run Checkpoint

Write a checkpoint for unattended continuation:

```powershell
.\scripts\long-run-harness.ps1
```

The checkpoint is written to `coordination/long_run_checkpoint.sop`.

Key fields:

- `start_current_frontier`: the conversation frontier before the harness ran proof commands.
- `end_current_frontier`: the conversation frontier after the harness ran proof commands.
- `test_status`, `dry_run_status`, and `model_inventory_status`: gating checks for continuation.
- `openai_health_status`: non-gating environment state for the local OpenAI-compatible server.
- `route_draft_status`: non-gating configuration guidance from `scripts\live-route-draft.ps1`.
- `shaliach_cross_artifact_status`: deterministic consistency proof over Shaliach self-negotiation, finding, and optional response artifacts.

An unavailable OpenAI-compatible server should not block continuation when the current work is governance, documentation, or dry-run proof. It only means live local serving is not ready yet.

`route_draft_status` passing means the harness wrote or refreshed `coordination/live_route_config_draft.sop`. It does not mean `agent.config.json` was changed, live serving is available, or model quality has been benchmarked. Use it as a bridge between machine readiness and a later operator-reviewed config edit.

Validate recorded Shaliach checkpoint probe evidence without rerunning the harness:

```powershell
.\scripts\validate-checkpoint-probe.ps1 -Checkpoint .\coordination\long_run_checkpoint.sop
```

The validator returns exit code `0` for passed evidence, `2` for incomplete evidence, and `1` for failed probe evidence. It keeps `openai_health_status` non-gating and does not approve Shaliach findings semantically.

To validate both a run manifest and checkpoint proof evidence in one read-only summary:

```powershell
.\scripts\validate-artifacts.ps1 -Manifest .\runs\<timestamp>\run_manifest.sop -Checkpoint .\coordination\long_run_checkpoint.sop
```

This combined validator uses the same exit-code vocabulary: `0` passed, `2` incomplete, and `1` failed. It checks artifact refs and recorded proof status only; it is not final code acceptance or apply permission.

## Mailbox Messages

List mailbox messages:

```powershell
.\scripts\mailbox.ps1 -Command list -Mailbox director_pool
```

List unread messages:

```powershell
.\scripts\mailbox.ps1 -Command list -Mailbox director_pool -Unread
```

Advance the read cursor after a worker has observed a message:

```powershell
.\scripts\mailbox.ps1 -Command advance -Mailbox director_pool -MessageId <message-id>
```

The read cursor means observed, not completed.

## Claims

Claim a message:

```powershell
.\scripts\mailbox.ps1 -Command claim -Mailbox director_pool -MessageId <message-id> -Claimant <worker-uuid>
```

List claim state:

```powershell
.\scripts\mailbox.ps1 -Command claims -Mailbox director_pool
```

Claims are append-only coordination evidence. Conflicts are visible in claim output and conflict-signal messages, but claims are not scheduler locks.

## Worker Runner Boundary

The future worker runner is designed in `coordination/worker_runner_design.sop`. Until its record types and CLI exist, use mailbox claims manually and keep Manager/frontier updates explicit.

A real worker cycle must leave more evidence than a claim:

- `WorkerLeaseRecord`: temporary ownership evidence for a claim, with expiration and frontier-at-claim.
- `WorkerCycleRecord`: outcome, proof refs, changed files, and requested next frontier.
- failure record: command failure, dirty worktree summary, and safe resume action.

The runner must pause on Shaliach pause conditions, claim conflicts, stale frontiers, and unknown dirty work. A claim alone never authorizes code edits, target workspace mutation, or frontier advancement.

Preview unread work without claiming it:

```powershell
.\scripts\worker-runner-preview.ps1 -Worker <worker-uuid> -Mailbox director_pool -MaxClaims 1
```

This prints a `WorkerRunnerPreview` with proposed `WorkerLeaseRecord` entries. It does not write `claims.sop`, advance read cursors, or create worker cycle files.

Claim bounded unread work and write lease evidence:

```powershell
.\scripts\worker-runner-preview.ps1 -Worker <worker-uuid> -Mailbox director_pool -MaxClaims 1 -ClaimRecord
```

Claim-record mode writes mailbox claim evidence and `coordination/workers/<worker-uuid>/leases/<claim-id>.sop`. It still does not execute the work, advance read cursors, or update the Manager frontier.

Record a worker cycle outcome from explicit evidence refs:

```powershell
.\scripts\worker-runner-preview.ps1 -Worker <worker-uuid> -Mailbox director_pool -RecordCycle -CycleId <cycle-id> -CycleStatus paused_by_shaliach -ClaimRef <claim-ref> -SliceRef <slice-ref> -ProofRef <proof-ref>
```

Cycle-record mode writes `coordination/workers/<worker-uuid>/cycles/<cycle-id>.sop`. It is Manager review input, not completion approval, and it does not mutate the active conversation frontier.

Run an explicit proof command and record the result:

```powershell
.\scripts\worker-runner-preview.ps1 -Worker <worker-uuid> -Mailbox director_pool -RunProofCommand "powershell -ExecutionPolicy Bypass -File scripts\test.ps1" -CycleId <cycle-id>
```

Proof-command mode writes a `WorkerCycleRecord`. On failed proof it also writes a `WorkerFailureRecord` under `coordination/workers/<worker-uuid>/failures/` and returns a nonzero exit code. It should be used only for explicit proof commands selected by the active slice.

## Execution Gate Boundary

Before a future worker runner executes claimed implementation work, it must have execution-gate evidence:

- `ManagerAuthorizationRecord`: Manager-side permission evidence, not final acceptance.
- `ShaliachExecutionClearance`: protocol counsel evidence, not Manager authorization.
- `ExecutionGateDecision`: combined gate result, not completion approval.

The deterministic evaluator can allow proof-only work or block on Manager denial, Shaliach pause/rework, stale frontier, or invalid lease. It does not run live Manager/Shaliach deliberation, execute implementation work, or mutate the target workspace.

Preview an execution gate decision from existing refs:

```powershell
.\scripts\execution-gate-preview.ps1 -ManagerAuthorizationRef <auth-ref> -ShaliachClearanceRef <clearance-ref> -LeaseRef <lease-ref> -CurrentFrontier <frontier>
```

The preview command prints `ExecutionGateDecision` to stdout. It does not write gate files, authorizations, clearances, leases, cycles, claims, or read cursors.

`coordination/execution_gate_decision_writer_design.sop` describes the next explicit write step. Its future command may persist the evaluated `ExecutionGateDecision` under `coordination/workers/<worker-uuid>/execution_gates/`, including blocked decisions for later review. Persisting that gate decision is not permission to execute implementation work, does not create Manager or Shaliach evidence, and does not move the Manager frontier.

Persist the evaluated gate decision as review evidence:

```powershell
.\scripts\execution-gate-preview.ps1 -ManagerAuthorizationRef <auth-ref> -ShaliachClearanceRef <clearance-ref> -LeaseRef <lease-ref> -CurrentFrontier <frontier> -GateId <gate-id> -Write
```

Write mode creates exactly one `ExecutionGateDecision` artifact under `coordination/workers/<worker-uuid>/execution_gates/` and refuses to overwrite an existing gate file.

The next planned bridge is `coordination/gate_to_worker_cycle_bridge_design.sop`. It maps persisted gate decisions to `WorkerCycleRecord` review evidence, for example Manager blocks become `blocked`, Shaliach blocks become `paused_by_shaliach`, stale frontiers become `needs_manager_review`, and proof-only allowed gates become `ready_for_proof`. That bridge remains non-executing.

Record a worker cycle from a persisted gate decision:

```powershell
.\scripts\worker-runner-preview.ps1 -Worker <worker-uuid> -Mailbox director_pool -RecordGateCycle -ExecutionGateRef <gate-ref> -CycleId <cycle-id>
```

Gate-cycle bridge mode writes one `WorkerCycleRecord` from the existing gate ref. It does not run proof commands, execute implementation work, or advance the read cursor.

The next planned proof handoff is `coordination/manager_reviewed_proof_handoff_design.sop`. A `ready_for_proof` cycle is review evidence only; a later Manager proof handoff must approve the exact proof command before the proof-command runner consumes it.

Write a Manager proof handoff without running the command:

```powershell
.\scripts\worker-runner-preview.ps1 -Worker <worker-uuid> -Mailbox director_pool -WriteProofHandoff -ReadyCycleRef <cycle-ref> -ExecutionGateRef <gate-ref> -HandoffId <handoff-id> -ProofCommand "<command>" -ProofRoute "<route>" -CurrentFrontier <frontier> -ExpiresAt <timestamp>
```

The handoff writer validates that the source cycle is `ready_for_proof` and that the exact command matches the handoff evidence. It writes only the handoff artifact.

`coordination/handoff_aware_proof_runner_design.sop` describes the next planned consumption step. An approved handoff may later feed the existing proof-command runner, but only after validation and only into a new proof result cycle; it must not advance cursors or frontiers.

Consume an approved proof handoff:

```powershell
.\scripts\worker-runner-preview.ps1 -Worker <worker-uuid> -Mailbox director_pool -ConsumeProofHandoff -HandoffRef <handoff-ref> -CurrentFrontier <frontier> -CycleId <cycle-id>
```

Consume mode loads the approved handoff and referenced ready cycle, validates the frontier and worker, then runs only the exact command recorded in the handoff. The result is a new proof cycle; failed proofs still write `WorkerFailureRecord` evidence.

The next planned implementation boundary is `coordination/gate_authorized_run_local_execution_design.sop`. It permits only run-local generated outputs from an `execution_allowed` gate; target workspace writes still belong to the explicit merge/apply/rollback protocols.

Write a dry-run run-local execution plan:

```powershell
.\scripts\run-local-execution-plan.ps1 -Worker <worker-uuid> -ExecutionGateRef <gate-ref> -ReadyCycleRef <cycle-ref> -RunId <run-id> -CycleId <cycle-id> -PlanId <plan-id>
```

The planner writes `run_local_execution_plan.sop` under `runs/<run-id>/worker_execution/<cycle-id>/`. It does not generate implementation files.

The current writer helper can execute a plan into the same run-local root and write `run_local_execution_result.sop`; an operator CLI for that writer is the next boundary.

Execute an existing run-local plan into generated evidence:

```powershell
.\scripts\run-local-execution-plan.ps1 -Worker <worker-uuid> -ExecutePlan -PlanRef <plan-ref> -ResultId <result-id> -WorkerCycleRef <cycle-ref> -GeneratedText "<text>"
```

Execute-plan mode writes generated evidence under the plan root and writes `run_local_execution_result.sop`. It still does not apply files to the target workspace.

The next planned review boundary is `coordination/run_local_output_review_design.sop`. Run-local generated files need Manager and Shaliach review before they can become eligible for a manual merge packet, and eligibility is still not apply acceptance.

Write run-local output review evidence:

```powershell
.\scripts\run-local-output-review.ps1 -RunLocalRoot <root> -ManagerReview -ReviewStatus accepted_for_merge_review -PlanRef <plan-ref> -ResultRef <result-ref> -GeneratedFile <generated-ref>
.\scripts\run-local-output-review.ps1 -RunLocalRoot <root> -ShaliachReview -ReviewStatus clear -PlanRef <plan-ref> -ResultRef <result-ref> -CheckedProtocol SOP
.\scripts\run-local-output-review.ps1 -RunLocalRoot <root> -Eligibility -ManagerReviewRef <manager-review-ref> -ShaliachReviewRef <shaliach-review-ref>
```

Eligibility writes `run_local_merge_eligibility.sop`. It does not create `manual_merge_packet.sop`.

`coordination/run_local_to_merge_packet_bridge_design.sop` describes the next planned bridge from eligible run-local output to draft manual merge inputs. Draft inputs are not manual merge packets and cannot be applied.

Write a non-mutating merge draft input from eligible run-local output:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-local-merge-draft.ps1 `
  -RunLocalRoot runs/run-1/worker_execution/cycle-run `
  -TargetWorkspaceRoot C:\Project\TheBrain
```

This writes `run_local_merge_draft_input.sop`. It does not create `manual_merge_packet.sop` and does not apply files to the target workspace.

`coordination/merge_draft_to_packet_proposal_design.sop` describes the next boundary after draft input. A future writer may create `manual_merge_packet.sop` only from explicit Manager packet acceptance and Shaliach packet review evidence; draft input alone is insufficient.

Write packet proposal evidence:

```powershell
.\scripts\packet-proposal.ps1 -RunLocalRoot <root> -ManagerAcceptance -AcceptanceStatus accepted_for_packet_proposal -AcceptedEntryCount 1 -FrontierAtAcceptance <frontier>
.\scripts\packet-proposal.ps1 -RunLocalRoot <root> -ShaliachReview -ReviewStatus clear_for_packet_proposal -CheckedProtocol SOP
.\scripts\packet-proposal.ps1 -RunLocalRoot <root> -PacketProposal -PacketId <packet-id> -VerificationCommand "powershell -ExecutionPolicy Bypass -File scripts\test.ps1"
```

The packet proposal command writes `manual_merge_packet.sop` only after the acceptance and review artifacts exist. It does not write `apply_plan.sop` or mutate the target workspace.

`coordination/frontier_advancement_record_design.sop` describes the next Manager-control boundary. Do not treat a packet proposal or a passing proof as a frontier update; a future frontier advancement record must be written and then explicitly applied to the conversation surface.

Write frontier advancement evidence:

```powershell
.\scripts\frontier-advancement.ps1 `
  -AdvancementId <id> `
  -PreviousFrontier <current-frontier> `
  -NextFrontier <next-frontier> `
  -ManagerDecisionRef <manager-ref> `
  -ManagerDecisionStatus approved_for_frontier_advancement `
  -ShaliachReviewRef <shaliach-ref> `
  -ShaliachReviewStatus clear_for_frontier_advancement `
  -ProofRef coordination/long_run_checkpoint.sop
```

This writes `frontier_advancement_record.sop` under `coordination/frontier_advancements/<id>/`. It does not mutate the active conversation surface.

`coordination/frontier_application_plan_design.sop` describes the next boundary. A future planner must verify the active conversation surface still has the record's previous frontier before any explicit surface mutation command can update `current_frontier`.

Write a dry-run frontier application plan:

```powershell
.\scripts\frontier-application-plan.ps1 `
  -AdvancementRef coordination/frontier_advancements/<id>/frontier_advancement_record.sop `
  -PlanId <plan-id> `
  -CompletedSliceRef <slice-id>
```

This writes `frontier_application_plan.sop` beside the advancement record. It does not mutate the active conversation surface.

`coordination/frontier_application_apply_design.sop` describes the future explicit apply boundary. The apply command may mutate the active conversation surface only when the current frontier still equals the plan's previous frontier, and it must write a result artifact for both applied and blocked outcomes.

Apply a frontier application plan:

```powershell
.\scripts\frontier-application-plan.ps1 `
  -ApplyPlan `
  -PlanRef coordination/frontier_advancements/<id>/frontier_application_plan.sop `
  -ResultId <result-id>
```

The apply mode writes `frontier_application_result.sop`. It updates `current_frontier` only when the active surface still matches the plan's previous frontier; stale plans produce a blocked result.

Write recomputed narrative stale-check evidence:

```powershell
.\scripts\narrative-coverage.ps1 -StaleCheck -CheckId <check-id>
```

This writes `coordination/narrative_stale_check.sop` and does not mutate `project_narrative_surface.sop`.

The next designed boundary is `coordination/narrative_coverage_update_record_design.sop`. It will produce update-record evidence from a stale-check record, but it is still not a narrative append command.

Write narrative coverage update-record evidence from a stale-check artifact:

```powershell
.\scripts\narrative-coverage.ps1 `
  -UpdateRecord `
  -UpdateId <update-id> `
  -StaleCheckRef coordination/narrative_stale_check.sop
```

This writes `coordination/narrative_coverage_update_record.sop` and does not mutate `project_narrative_surface.sop`.

Do not append update-record text to the narrative surface manually during automated runs. The reviewed append boundary is specified in `coordination/reviewed_narrative_append_design.sop`; implementation is intentionally split into later record, result, and CLI slices.

The Manager and Shaliach review record types now exist in `negotiated_agent.narrative_append`, but no operator wrapper writes them yet.

`NarrativeAppendResult` can now be produced in code as a non-mutating plan/result object. The operator-facing append command remains pending and should preserve the same stale surface guard.

The guarded append helper exists in code, but no shell wrapper loads review artifacts yet. Use it only through tests or a later CLI that validates Manager and Shaliach refs.

The reviewed append CLI is designed in `coordination/reviewed_narrative_append_cli_design.sop`. Until the parser and wrapper slices land, do not use shell commands to apply narrative update records.

The parser slice has landed, but the shell wrapper has not. Narrative append still requires code-level orchestration or the later CLI slice.

Write reviewed narrative append plan evidence:

```powershell
.\scripts\narrative-append.ps1 -GuardDiscovery

.\scripts\narrative-append.ps1 `
  -ExpectedSurfaceGuard <guard> `
  -ResultId <result-id>
```

Guard discovery prints the current surface guard. Plan mode writes `coordination/narrative_append_result.sop` from existing update, Manager approval, and Shaliach clearance artifacts. It does not append to the narrative surface.

Apply reviewed narrative append evidence:

```powershell
.\scripts\narrative-append.ps1 `
  -Apply `
  -ExpectedSurfaceGuard <guard> `
  -ResultId <result-id>
```

Apply mode writes the same result artifact path. It appends only when the loaded evidence allows append and the surface guard matches; blocked outcomes preserve the narrative surface.

Review artifact writer modes are designed in `coordination/narrative_append_review_writer_design.sop`; until implemented, Manager approval and Shaliach clearance artifacts must come from code-level helpers or hand-authored SOP with care.

Write Manager narrative append approval evidence:

```powershell
.\scripts\narrative-append.ps1 `
  -ManagerApproval `
  -ApprovalId <approval-id> `
  -ApprovalStatus approved_for_narrative_append `
  -ApprovedUpdateCount <count> `
  -FrontierAtApproval <frontier>
```

This writes `coordination/manager_narrative_append_approval.sop` and does not plan or apply append.

Write Shaliach narrative append clearance evidence:

```powershell
.\scripts\narrative-append.ps1 `
  -ShaliachClearance `
  -ClearanceId <clearance-id> `
  -ClearanceStatus clear_for_narrative_append `
  -CheckedProtocol SOP `
  -CheckedProtocol SJS
```

This writes `coordination/shaliach_narrative_append_clearance.sop` and does not plan or apply append.

Draft both reviewed append artifacts from an update record:

```powershell
.\scripts\narrative-append.ps1 `
  -SynthesizeReviewDrafts `
  -FrontierAtApproval <frontier> `
  -CheckedProtocol SOP `
  -CheckedProtocol SJS
```

This writes Manager and Shaliach draft review artifacts. The drafts include deterministic-review caution fields and are not a replacement for live deliberation.

Complete deterministic reviewed narrative append workflow:

```powershell
.\scripts\narrative-coverage.ps1 -StaleCheck -CheckId <check-id>

.\scripts\narrative-coverage.ps1 `
  -UpdateRecord `
  -UpdateId <update-id> `
  -StaleCheckRef coordination/narrative_stale_check.sop

.\scripts\narrative-append.ps1 -GuardDiscovery

.\scripts\narrative-append.ps1 `
  -SynthesizeReviewDrafts `
  -FrontierAtApproval <frontier> `
  -CheckedProtocol SOP `
  -CheckedProtocol SJS

.\scripts\narrative-append.ps1 `
  -ExpectedSurfaceGuard <guard-from-discovery> `
  -ResultId <plan-id> `
  -Out coordination/narrative_append_plan.sop

.\scripts\narrative-append.ps1 `
  -Apply `
  -ExpectedSurfaceGuard <same-guard-if-still-current> `
  -ResultId <apply-id> `
  -Out coordination/narrative_append_result.sop
```

This workflow is deterministic artifact governance. It is useful for keeping narrative memory coherent, but the synthesized review drafts are not live Manager/Shaliach deliberation.

## Rendezvous Packets

Write a handoff packet between conversations:

```powershell
.\scripts\mailbox.ps1 -Command rendezvous -Source <source-uuid> -Target <target-uuid> -Subject "handoff subject" -Boundary "what is done, what remains, and where authority stops"
```

Rendezvous packets are durable handoff carriers. They should state the boundary clearly enough that another conversation can reenter without inheriting hidden assumptions.
