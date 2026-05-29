from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import subprocess

from .conversation import ConversationSurface


@dataclass(frozen=True)
class CommandResult:
    name: str
    returncode: int
    stdout_tail: str
    stderr_tail: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


@dataclass(frozen=True)
class LongRunCheckpoint:
    created_at: str
    conversation_uuid: str
    current_frontier: str
    git_clean_before: bool
    test_result: CommandResult
    dry_run_result: CommandResult
    model_inventory_result: CommandResult
    openai_health_result: CommandResult | None = None

    @property
    def status(self) -> str:
        if self.test_result.ok and self.dry_run_result.ok and self.model_inventory_result.ok:
            return "ready_for_continuation"
        return "needs_attention"

    def to_sop(self) -> str:
        return f"""& [LongRunCheckpoint] is a bounded unattended-work harness checkpoint
  + [created_at] is {self.created_at}
  + [conversation_uuid] is {self.conversation_uuid}
  + [current_frontier] is {self.current_frontier}
  + [git_clean_before] is {_bool(self.git_clean_before)}
  + [status] is {self.status}
  + [test_status] is {_status(self.test_result)}
  + [dry_run_status] is {_status(self.dry_run_result)}
  + [model_inventory_status] is {_status(self.model_inventory_result)}
  + [openai_health_status] is {_status(self.openai_health_result) if self.openai_health_result else "not_run"}
  + [authority_boundary] is harness_checkpoint_not_human_approval

  & [HarnessCommand test] is a command proof summary
    + [returncode] is {self.test_result.returncode}
    + [stdout_tail] is {_field_value(self.test_result.stdout_tail)}
    + [stderr_tail] is {_field_value(self.test_result.stderr_tail)}

  & [HarnessCommand dry_run] is a command proof summary
    + [returncode] is {self.dry_run_result.returncode}
    + [stdout_tail] is {_field_value(self.dry_run_result.stdout_tail)}
    + [stderr_tail] is {_field_value(self.dry_run_result.stderr_tail)}

  & [HarnessCommand model_inventory] is a command proof summary
    + [returncode] is {self.model_inventory_result.returncode}
    + [stdout_tail] is {_field_value(self.model_inventory_result.stdout_tail)}
    + [stderr_tail] is {_field_value(self.model_inventory_result.stderr_tail)}

  & [HarnessCommand openai_health] is an environment-state summary
    + [returncode] is {self.openai_health_result.returncode if self.openai_health_result else "not_run"}
    + [stdout_tail] is {_field_value(self.openai_health_result.stdout_tail if self.openai_health_result else "")}
    + [stderr_tail] is {_field_value(self.openai_health_result.stderr_tail if self.openai_health_result else "")}
    + [gating_behavior] is non_gating_environment_state
"""


def run_harness(project_root: Path) -> LongRunCheckpoint:
    surface = ConversationSurface.load_active(project_root)
    git_clean = _git_clean(project_root.parents[1])
    test = _run("test", ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(project_root / "scripts" / "test.ps1")], project_root)
    dry = _run(
        "dry_run",
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(project_root / "scripts" / "run-dry.ps1"),
            "-SuppressMailbox",
        ],
        project_root,
    )
    inventory = _run(
        "model_inventory",
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(project_root / "scripts" / "model-inventory.ps1"),
            "--out",
            str(project_root / "coordination" / "model_serving_inventory.sop"),
        ],
        project_root,
    )
    openai_health = _run(
        "openai_health",
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(project_root / "scripts" / "openai-health.ps1"),
            "-Out",
            str(project_root / "coordination" / "openai_health.sop"),
        ],
        project_root,
    )
    return LongRunCheckpoint(
        created_at=datetime.now(timezone.utc).isoformat(),
        conversation_uuid=surface.first("conversation_uuid", "unknown") or "unknown",
        current_frontier=surface.first("current_frontier", "unknown") or "unknown",
        git_clean_before=git_clean,
        test_result=test,
        dry_run_result=dry,
        model_inventory_result=inventory,
        openai_health_result=openai_health,
    )


def _run(name: str, command: list[str], cwd: Path) -> CommandResult:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=180, check=False)
    return CommandResult(
        name=name,
        returncode=result.returncode,
        stdout_tail=_tail(result.stdout),
        stderr_tail=_tail(result.stderr),
    )


def _git_clean(repo_root: Path) -> bool:
    result = subprocess.run(
        ["C:\\Program Files\\Git\\cmd\\git.exe", "status", "--short"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return result.returncode == 0 and not result.stdout.strip()


def _tail(text: str, limit: int = 500) -> str:
    return text.strip()[-limit:] if text else ""


def _status(result: CommandResult) -> str:
    return "passed" if result.ok else "failed"


def _bool(value: bool) -> str:
    return "true" if value else "false"


def _field_value(value: str) -> str:
    return " ".join(value.replace("\x00", "").split())[:240] if value else "none"
