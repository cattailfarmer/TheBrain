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

An unavailable OpenAI-compatible server should not block continuation when the current work is governance, documentation, or dry-run proof. It only means live local serving is not ready yet.

`route_draft_status` passing means the harness wrote or refreshed `coordination/live_route_config_draft.sop`. It does not mean `agent.config.json` was changed, live serving is available, or model quality has been benchmarked. Use it as a bridge between machine readiness and a later operator-reviewed config edit.

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

## Rendezvous Packets

Write a handoff packet between conversations:

```powershell
.\scripts\mailbox.ps1 -Command rendezvous -Source <source-uuid> -Target <target-uuid> -Subject "handoff subject" -Boundary "what is done, what remains, and where authority stops"
```

Rendezvous packets are durable handoff carriers. They should state the boundary clearly enough that another conversation can reenter without inheriting hidden assumptions.
