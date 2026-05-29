from __future__ import annotations

from dataclasses import dataclass

from .model_inventory import ModelInventory, probe_inventory


@dataclass(frozen=True)
class VllmWslPreflight:
    inventory: ModelInventory
    status: str
    blockers: tuple[str, ...]
    next_actions: tuple[str, ...]

    def to_sop(self) -> str:
        lines = [
            "& [VllmWsl2SetupPreflight] is the non-destructive readiness report for vLLM on WSL2",
            f"  + [status] is {self.status}",
            f"  + [gpu_name] is {self.inventory.gpu.name or 'none_detected'}",
            f"  + [gpu_vram_mib] is {self.inventory.gpu.vram_mib if self.inventory.gpu.vram_mib is not None else 'unknown'}",
            f"  + [nvidia_driver] is {self.inventory.gpu.driver or 'unknown'}",
            f"  + [cuda_version] is {self.inventory.gpu.cuda or 'unknown'}",
            f"  + [wsl_available] is {_bool(self.inventory.wsl.available)}",
            f"  + [wsl_detail] is {_field_value(self.inventory.wsl.detail)}",
            f"  + [docker_available] is {_bool(self.inventory.docker.available)}",
            f"  + [openai_compatible_available] is {_bool(self.inventory.openai_compatible.available)}",
            f"  + [recommended_route] is {self.inventory.recommended_route}",
            "  + [reference] is https://docs.vllm.ai/en/latest/getting_started/quickstart.html",
            "  + [reference] is https://learn.microsoft.com/windows/ai/directml/gpu-cuda-in-wsl",
            "  + [reference] is https://docs.nvidia.com/cuda/wsl-user-guide/",
            "  + [authority_boundary] is setup_preflight_not_system_installation",
        ]
        for blocker in self.blockers:
            lines.append(f"  + [blocker] is {_field_value(blocker)}")
        for action in self.next_actions:
            lines.append(f"  + [next_action] is {_field_value(action)}")
        return "\n".join(lines) + "\n"


def build_vllm_wsl_preflight(inventory: ModelInventory | None = None) -> VllmWslPreflight:
    inventory = inventory or probe_inventory()
    blockers: list[str] = []
    actions: list[str] = []

    if not inventory.gpu.available:
        blockers.append("NVIDIA GPU was not detected from Windows nvidia-smi.")
        actions.append("Install or repair NVIDIA Windows driver before attempting WSL2 CUDA serving.")
    elif (inventory.gpu.vram_mib or 0) < 24000:
        blockers.append("Detected GPU VRAM is below the 24 GiB threshold chosen for vLLM swarm serving.")
        actions.append("Use smaller models, quantization, Ollama, or remote OpenAI-compatible serving.")

    if not inventory.wsl.available:
        blockers.append("WSL is not installed or not available from this shell.")
        actions.append("Install WSL2 with an Ubuntu distribution, then verify `wsl --status` and `nvidia-smi` inside WSL.")
    else:
        actions.append("Inside WSL, verify CUDA visibility with `nvidia-smi` before installing vLLM.")

    if not inventory.openai_compatible.available:
        actions.append("After vLLM install, start an OpenAI-compatible server and verify `/v1/models` on localhost:8000.")

    actions.append("Do not install a Linux NVIDIA kernel driver inside WSL; use the Windows host driver exposed to WSL.")
    actions.append("Prefer vLLM OpenAI-compatible serving for concurrent Manager, Director, Shaliach, and Programmer routes.")

    status = "ready_for_wsl_vllm_install" if not blockers else "blocked_before_install"
    return VllmWslPreflight(
        inventory=inventory,
        status=status,
        blockers=tuple(blockers),
        next_actions=tuple(actions),
    )


def _bool(value: bool) -> str:
    return "true" if value else "false"


def _field_value(value: str) -> str:
    cleaned = value.replace("\x00", "")
    return " ".join(cleaned.split())[:240] if cleaned else "none"
