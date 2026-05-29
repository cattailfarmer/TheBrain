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
- `WS001_initial_implementation.work_slice.sop`
- `WS001_initial_implementation.programmer_report.sop`
- `WS001_initial_implementation.manager_review.sop`
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
- `WS001_initial_implementation.work_slice.sop`
- `WS001_initial_implementation.programmer_report.sop`
- `WS001_initial_implementation.manager_review.sop`

The generated implementation is intentionally conservative: the coder writes files only inside the run folder unless you later add an explicit workspace writer.

Programmer swarm support is currently staged. The runtime can represent multiple planned slices and write an assignment plan, but the orchestrator still executes one initial slice until merge review and parallel execution are implemented.

## Design

See `docs/architecture.md`.
For long-running and multi-conversation operator helpers, see `docs/coordination_operator_guide.md`.
For the RTX 5090 WSL2/vLLM serving path, see `docs/vllm_wsl2_operator_guide.md`.
For a focused OpenAI-compatible endpoint check, run `.\scripts\openai-health.ps1`.

## Specification

The hierarchical manager/council/worker architecture is captured in `specifications/Hierarchical_Agent_Swarm.sop`.
The original dictated intent is preserved separately in `specifications/source/2026-05-29_hierarchical_agent_swarm_source.sop`.
