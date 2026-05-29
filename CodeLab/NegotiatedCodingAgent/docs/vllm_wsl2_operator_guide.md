# vLLM WSL2 Operator Guide

This is the manual path for the preferred RTX 5090 serving route. The project does not install WSL2, CUDA, Python packages, or vLLM automatically.

Primary references:

- Microsoft CUDA on WSL: <https://learn.microsoft.com/windows/ai/directml/gpu-cuda-in-wsl>
- NVIDIA CUDA on WSL user guide: <https://docs.nvidia.com/cuda/wsl-user-guide/>
- vLLM quickstart and OpenAI-compatible server: <https://docs.vllm.ai/en/latest/getting_started/quickstart.html>

## Current Preflight

Run:

```powershell
.\scripts\vllm-wsl2-preflight.ps1
```

The current report is written to `coordination/vllm_wsl2_preflight.sop`. On this machine it reports:

- RTX 5090 detected through Windows `nvidia-smi`
- about 32 GB VRAM
- WSL unavailable
- recommended route: `install_wsl2_then_vllm`

## Manual Setup Sequence

1. Install WSL2 with Ubuntu from an elevated Windows terminal.

```powershell
wsl --install -d Ubuntu
```

2. Reboot if Windows requests it, then open Ubuntu and update packages.

```bash
sudo apt update
sudo apt upgrade
```

3. Verify GPU visibility inside WSL.

```bash
nvidia-smi
```

Do not install a Linux NVIDIA kernel driver inside WSL. NVIDIA’s WSL guidance uses the Windows host driver exposed into WSL.

4. Create a Python environment for vLLM inside WSL.

Use the current vLLM installation guide when choosing `pip`, `uv`, CUDA/PyTorch options, and model-specific requirements.

5. Start a vLLM OpenAI-compatible server inside WSL.

The project expects an OpenAI-compatible endpoint, conventionally:

```text
http://localhost:8000/v1
```

6. From Windows PowerShell, verify the route.

```powershell
.\scripts\model-inventory.ps1
.\scripts\role-model-profile.ps1
```

The expected transition is from `install_wsl2_then_vllm` or `dry_run_until_serving_installed` toward `vllm_wsl2_openai_compatible` once `/v1/models` responds.

## Project Integration

After the server is reachable, set role providers in `agent.config.json` to `openai_compatible` with the vLLM base URL. Keep model names explicit per role so Manager, Directors, Shaliach, and Programmers can represent different model tiers.

Keep dry-run mode for governance tests:

```powershell
.\scripts\run-dry.ps1 -SuppressMailbox
```

Use live serving only after `scripts\test.ps1`, `scripts\model-inventory.ps1`, and `scripts\role-model-profile.ps1` are coherent.
