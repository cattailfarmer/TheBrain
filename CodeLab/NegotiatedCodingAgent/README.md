# Negotiated Coding Agent

A local-LLM coding-agent prototype that makes two or more models negotiate a layered flowchart before writing code.

The core idea is deliberately staged:

1. Application-level flowchart
2. Subsystem-level flowchart
3. Component-level flowchart
4. Code-level flowchart
5. Code generation from the settled code-level flowchart

Each layer runs a negotiation pass across multiple LLM roles. The system then asks an arbiter model to merge the proposals into one settled flowchart for the next layer.

## Status

This is a first runnable scaffold. It supports Ollama-compatible local models over HTTP and has a deterministic dry-run mode for testing the pipeline without an LLM server.

## Quick Start

From this folder:

```powershell
.\scripts\run-dry.ps1
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

- `application.flowchart.md`
- `subsystem.flowchart.md`
- `component.flowchart.md`
- `code.flowchart.md`
- `implementation/`
- `negotiation_log.jsonl`

The generated implementation is intentionally conservative: the coder writes files only inside the run folder unless you later add an explicit workspace writer.

## Design

See `docs/architecture.md`.

## Specification

The hierarchical manager/council/worker architecture is captured in `specifications/Hierarchical_Agent_Swarm.sop`.
The original dictated intent is preserved separately in `specifications/source/2026-05-29_hierarchical_agent_swarm_source.sop`.
