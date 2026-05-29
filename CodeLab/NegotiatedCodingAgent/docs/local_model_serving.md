# Local Model Serving

S15 records machine readiness separately from installation.

Current observed state on this machine:

- NVIDIA RTX 5090 is visible through `nvidia-smi` with about 32 GB VRAM.
- Ollama is not installed on the Windows `PATH`.
- WSL is not installed.
- Docker is not installed.
- vLLM is therefore not currently runnable here, because the preferred vLLM path needs Linux through WSL2 or a Linux host.

Recommended route:

1. Install WSL2 with a compact Ubuntu distribution when you are ready to spend disk space on serving.
2. Use vLLM inside WSL2 for the high-throughput OpenAI-compatible server path.
3. Keep Ollama as the simpler fallback route if you want a fast Windows-native first live run.
4. Keep dry-run mode as the governance proof route when no model server is available.

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
