# Local Model Serving

S15 and S87 record machine readiness separately from installation.

Current observed state on this machine:

- NVIDIA RTX 5090 is visible through `nvidia-smi` with about 32 GB VRAM.
- Windows NVIDIA driver is visible from the probe as `596.49`.
- Windows CUDA version is visible from the probe as `13.2`.
- Ollama is not installed on the Windows `PATH`.
- WSL is not installed.
- Docker is not installed.
- `http://localhost:8000/v1/models` is not serving an OpenAI-compatible model endpoint.
- vLLM is therefore not currently runnable here, because the preferred vLLM path needs Linux through WSL2 or a Linux host.

Recommended route:

1. Install WSL2 with a compact Ubuntu distribution when you are ready to spend disk space on serving.
2. Use vLLM inside WSL2 for the high-throughput OpenAI-compatible server path.
3. Keep Ollama as the simpler fallback route if you want a fast Windows-native first live run.
4. Keep dry-run mode as the governance proof route when no model server is available.

Disk-conscious boundary:

- WSL2 with one Ubuntu distribution is the preferred local path over a full dual-boot Linux install on a 1 TB drive.
- Do not install model weights casually. Pick one Manager-capable model first, then add Director and Programmer models only after the endpoint and role routing are proven.
- Keep generated run artifacts under `runs/` disposable. The durable state is the repository, SOP surfaces, and selected model-serving configuration.

Serving readiness ladder:

1. `dry_run_until_serving_installed`: current state; all orchestration and governance tests can continue.
2. `wsl_ready`: WSL2 is installed and `wsl --status` works.
3. `gpu_visible_in_wsl`: `nvidia-smi` works inside Ubuntu without installing a Linux NVIDIA kernel driver.
4. `vllm_endpoint_ready`: vLLM responds at `http://localhost:8000/v1/models`.
5. `role_routes_ready`: `agent.config.json` assigns explicit Manager, Director, Shaliach, and Programmer models against the OpenAI-compatible endpoint.

Run the repeatable probe:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\model-inventory.ps1 --out .\coordination\model_serving_inventory.sop
```

The probe writes an SOP snapshot with GPU, WSL, Docker, Ollama, OpenAI-compatible server, model inventory, and a recommended route.

For the manual RTX 5090 WSL2/vLLM path, see `docs/vllm_wsl2_operator_guide.md`.

After starting any vLLM or OpenAI-compatible server, run the focused endpoint healthcheck:

```powershell
.\scripts\openai-health.ps1 -BaseUrl http://localhost:8000 -Out .\coordination\openai_health.sop
```

An unavailable healthcheck is expected when no server is running. An available healthcheck proves `/v1/models` responds; it does not prove model quality, role fit, or throughput.

Draft role routes without mutating `agent.config.json`:

```powershell
.\scripts\live-route-draft.ps1 -BaseUrl http://localhost:8000
```

When no endpoint is available, the draft records a blocked readiness state and preserves the current configured models. When an OpenAI-compatible endpoint is available, the draft uses `/v1/models` or explicit `--model` arguments to suggest Manager, Director, Shaliach, and Programmer model assignments for operator review.

To test a candidate list before the endpoint reports models:

```powershell
.\scripts\live-route-draft.ps1 -Model model-a,model-b,model-c
```

Primary setup references:

- Microsoft WSL install guide: <https://learn.microsoft.com/windows/wsl/install>
- Microsoft CUDA on WSL guide: <https://learn.microsoft.com/windows/ai/directml/gpu-cuda-in-wsl>
- NVIDIA CUDA on WSL guide: <https://docs.nvidia.com/cuda/wsl-user-guide/>
- vLLM quickstart: <https://docs.vllm.ai/en/latest/getting_started/quickstart.html>
