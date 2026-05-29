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

An unavailable OpenAI-compatible server should not block continuation when the current work is governance, documentation, or dry-run proof. It only means live local serving is not ready yet.

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

## Rendezvous Packets

Write a handoff packet between conversations:

```powershell
.\scripts\mailbox.ps1 -Command rendezvous -Source <source-uuid> -Target <target-uuid> -Subject "handoff subject" -Boundary "what is done, what remains, and where authority stops"
```

Rendezvous packets are durable handoff carriers. They should state the boundary clearly enough that another conversation can reenter without inheriting hidden assumptions.
