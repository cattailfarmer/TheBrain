from __future__ import annotations

from dataclasses import dataclass
import json
import re
import shutil
import subprocess
import urllib.error
import urllib.request


@dataclass(frozen=True)
class ToolProbe:
    name: str
    available: bool
    detail: str


@dataclass(frozen=True)
class GpuProbe:
    available: bool
    name: str
    vram_mib: int | None
    driver: str
    cuda: str


@dataclass(frozen=True)
class ModelInventory:
    gpu: GpuProbe
    ollama: ToolProbe
    wsl: ToolProbe
    docker: ToolProbe
    openai_compatible: ToolProbe
    ollama_models: tuple[str, ...]

    @property
    def recommended_route(self) -> str:
        if self.wsl.available and self.gpu.available and (self.gpu.vram_mib or 0) >= 24000:
            return "vllm_wsl2_openai_compatible"
        if self.ollama.available and self.ollama_models:
            return "ollama_local"
        if self.openai_compatible.available:
            return "openai_compatible_existing_server"
        if self.gpu.available:
            return "install_wsl2_then_vllm"
        return "dry_run_until_local_serving_installed"

    def to_sop(self) -> str:
        models = ", ".join(self.ollama_models) if self.ollama_models else "none_detected"
        role_routes = role_route_profile(self)
        return f"""& [ModelServingInventory] is the local model-serving readiness probe
  + [gpu_available] is {_bool(self.gpu.available)}
  + [gpu_name] is {self.gpu.name or "none_detected"}
  + [gpu_vram_mib] is {self.gpu.vram_mib if self.gpu.vram_mib is not None else "unknown"}
  + [nvidia_driver] is {self.gpu.driver or "unknown"}
  + [cuda_version] is {self.gpu.cuda or "unknown"}
  + [ollama_available] is {_bool(self.ollama.available)}
  + [ollama_detail] is {_field_value(self.ollama.detail)}
  + [ollama_model_set] is {models}
  + [wsl_available] is {_bool(self.wsl.available)}
  + [wsl_detail] is {_field_value(self.wsl.detail)}
  + [docker_available] is {_bool(self.docker.available)}
  + [docker_detail] is {_field_value(self.docker.detail)}
  + [openai_compatible_available] is {_bool(self.openai_compatible.available)}
  + [openai_compatible_detail] is {_field_value(self.openai_compatible.detail)}
  + [recommended_route] is {self.recommended_route}
  + [authority_boundary] is machine_probe_snapshot_not_installation_proof

& [RoleRouteProfile] is the model-serving route assignment for NegotiatedCodingAgent roles
  + [manager_route] is {role_routes["manager"]}
  + [director_route] is {role_routes["director"]}
  + [programmer_route] is {role_routes["programmer"]}
  + [shaliach_route] is {role_routes["shaliach"]}
"""


def probe_inventory(openai_compatible_base_url: str = "http://localhost:8000") -> ModelInventory:
    return ModelInventory(
        gpu=_probe_gpu(),
        ollama=_probe_tool("ollama", ["ollama", "--version"]),
        wsl=_probe_tool("wsl", ["wsl", "--status"]),
        docker=_probe_tool("docker", ["docker", "--version"]),
        openai_compatible=_probe_openai_compatible(openai_compatible_base_url),
        ollama_models=_probe_ollama_models(),
    )


def role_route_profile(inventory: ModelInventory) -> dict[str, str]:
    route = inventory.recommended_route
    if route == "vllm_wsl2_openai_compatible":
        return {
            "manager": "vllm_openai_compatible:large_reasoning_model",
            "director": "vllm_openai_compatible:medium_planning_models",
            "programmer": "vllm_openai_compatible:small_coder_swarm",
            "shaliach": "vllm_openai_compatible:manager_or_specialist_model",
        }
    if route == "ollama_local":
        return {
            "manager": "ollama:largest_available_model",
            "director": "ollama:medium_available_models",
            "programmer": "ollama:coder_available_models",
            "shaliach": "ollama:largest_available_model",
        }
    if route == "openai_compatible_existing_server":
        return {
            "manager": "openai_compatible:configured_server",
            "director": "openai_compatible:configured_server",
            "programmer": "openai_compatible:configured_server",
            "shaliach": "openai_compatible:configured_server",
        }
    return {
        "manager": "dry_run_until_serving_installed",
        "director": "dry_run_until_serving_installed",
        "programmer": "dry_run_until_serving_installed",
        "shaliach": "dry_run_until_serving_installed",
    }


def _probe_tool(name: str, command: list[str]) -> ToolProbe:
    if shutil.which(command[0]) is None:
        return ToolProbe(name=name, available=False, detail=f"{command[0]} not found on PATH")
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ToolProbe(name=name, available=False, detail=str(exc))
    detail = (result.stdout or result.stderr).strip()
    return ToolProbe(name=name, available=result.returncode == 0, detail=detail or f"exit_code={result.returncode}")


def _probe_gpu() -> GpuProbe:
    if shutil.which("nvidia-smi") is None:
        return GpuProbe(False, "", None, "", "")
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return GpuProbe(False, "", None, "", "")
    if result.returncode != 0 or not result.stdout.strip():
        return GpuProbe(False, "", None, "", "")
    first = result.stdout.splitlines()[0]
    parts = [part.strip() for part in first.split(",")]
    name = parts[0] if len(parts) > 0 else ""
    vram = _parse_int(parts[1]) if len(parts) > 1 else None
    driver = parts[2] if len(parts) > 2 else ""
    cuda = _probe_cuda_version()
    return GpuProbe(True, name, vram, driver, cuda)


def _probe_cuda_version() -> str:
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    match = re.search(r"CUDA Version:\s*([0-9.]+)", result.stdout)
    return match.group(1) if match else ""


def _probe_ollama_models() -> tuple[str, ...]:
    if shutil.which("ollama") is None:
        return ()
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ()
    if result.returncode != 0:
        return ()
    models = []
    for line in result.stdout.splitlines()[1:]:
        fields = line.split()
        if fields:
            models.append(fields[0])
    return tuple(models)


def _probe_openai_compatible(base_url: str) -> ToolProbe:
    url = base_url.rstrip("/") + "/v1/models"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return ToolProbe(name="openai_compatible", available=False, detail=f"{url} unavailable: {exc}")
    count = len(data.get("data", [])) if isinstance(data, dict) else 0
    return ToolProbe(name="openai_compatible", available=True, detail=f"{url} returned {count} models")


def _parse_int(value: str) -> int | None:
    match = re.search(r"\d+", value)
    return int(match.group(0)) if match else None


def _bool(value: bool) -> str:
    return "true" if value else "false"


def _field_value(value: str) -> str:
    cleaned = value.replace("\x00", "")
    return " ".join(cleaned.split())[:240] if cleaned else "none"
