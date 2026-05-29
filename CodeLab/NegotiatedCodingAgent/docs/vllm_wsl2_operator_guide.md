# vLLM WSL2 Operator Guide

This is the manual path for the preferred RTX 5090 serving route. The project does not install WSL2, CUDA, Python packages, or vLLM automatically.

Primary references:

- Microsoft WSL install guide: <https://learn.microsoft.com/windows/wsl/install>
- Microsoft CUDA on WSL: <https://learn.microsoft.com/windows/ai/directml/gpu-cuda-in-wsl>
- NVIDIA CUDA on WSL user guide: <https://docs.nvidia.com/cuda/wsl-user-guide/>
- vLLM quickstart and OpenAI-compatible server: <https://docs.vllm.ai/en/latest/getting_started/quickstart.html>

This guide is intentionally conservative. It records the setup sequence and verification commands, but the repository should not claim live serving until the probes in this guide pass on the target machine.

## Current Preflight

Run:

```powershell
.\scripts\vllm-wsl2-preflight.ps1
```

The current report is written to `coordination/vllm_wsl2_preflight.sop`. On this machine it reports:

- RTX 5090 detected through Windows `nvidia-smi`
- about 32 GB VRAM
- Windows NVIDIA driver `596.49`
- CUDA version `13.2` as reported by Windows `nvidia-smi`
- WSL unavailable
- Docker unavailable
- OpenAI-compatible endpoint unavailable at `http://localhost:8000/v1/models`
- recommended route: `install_wsl2_then_vllm`

## Manual Setup Sequence

1. Install WSL2 with Ubuntu from an elevated Windows terminal.

```powershell
wsl --install -d Ubuntu
```

This is the disk-conscious route for the current 1 TB machine: it avoids a full Linux dual-boot while still giving vLLM the Linux environment it expects.

2. Reboot if Windows requests it, then open Ubuntu and update packages.

```bash
sudo apt update
sudo apt upgrade
```

3. Verify GPU visibility inside WSL.

```bash
nvidia-smi
```

Do not install a Linux NVIDIA kernel driver inside WSL. NVIDIA's WSL guidance uses the Windows host driver exposed into WSL.

4. Create a Python environment for vLLM inside WSL.

Use the current vLLM installation guide when choosing `pip`, `uv`, CUDA/PyTorch options, and model-specific requirements.

5. Start a vLLM OpenAI-compatible server inside WSL.

The project expects an OpenAI-compatible endpoint, conventionally:

```text
http://localhost:8000/v1
```

6. From Windows PowerShell, verify the route.

```powershell
.\scripts\openai-health.ps1 -BaseUrl http://localhost:8000 -Out .\coordination\openai_health.sop
.\scripts\model-inventory.ps1
.\scripts\role-model-profile.ps1
```

The expected transition is from `install_wsl2_then_vllm` or `dry_run_until_serving_installed` toward `vllm_wsl2_openai_compatible` once `/v1/models` responds.

## Verification Gates

Treat each gate as a stop point:

1. Windows host sees the GPU with `nvidia-smi`.
2. WSL2 is installed and `wsl --status` succeeds.
3. Ubuntu sees the GPU with `nvidia-smi`.
4. vLLM starts without CUDA or model-load errors.
5. Windows PowerShell can reach `http://localhost:8000/v1/models`.
6. `scripts\model-inventory.ps1` changes `openai_compatible_available` to `true`.
7. `scripts\role-model-profile.ps1` no longer routes Manager, Directors, Programmers, and Shaliach to `dry_run_until_serving_installed`.

If a gate fails, keep the project in dry-run mode and update the relevant SOP surface rather than editing runtime role routes.

## Project Integration

After the server is reachable, set role providers in `agent.config.json` to `openai_compatible` with the vLLM base URL. Keep model names explicit per role so Manager, Directors, Shaliach, and Programmers can represent different model tiers.

Suggested first live route shape:

- Manager: one strong coding/reasoning model that fits comfortably in VRAM.
- Directors: two or three medium models, or medium variants with different prompting if only one medium model is available at first.
- Shaliach: strong enough to critique SOP/SJS/DataDesign compliance, preferably not the same exact route as every Director.
- Programmers: lighter coding models that can produce bounded work-slice outputs quickly.

Do not begin by loading every intended model. Prove one OpenAI-compatible server, one model, one dry objective, then increase model diversity.

Keep dry-run mode for governance tests:

```powershell
.\scripts\run-dry.ps1 -SuppressMailbox
```

Use live serving only after `scripts\test.ps1`, `scripts\openai-health.ps1`, `scripts\model-inventory.ps1`, and `scripts\role-model-profile.ps1` are coherent.
