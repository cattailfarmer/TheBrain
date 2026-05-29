from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

from .apply_preflight import apply_packet_files_to_workspace, build_apply_mutation_preflight, materialize_snapshot_evidence
from .apply_plan import ApplyResult
from .apply_plan import build_dry_run_apply_artifacts
from .merge_packet import AcceptedFileMapEntry, ManualMergePacket, RollbackPlan, ensure_target_path_within_workspace
from .writer import write_text


def _field(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped.startswith("+ [") or "] is " not in stripped:
        return None
    key, value = stripped[3:].split("] is ", 1)
    return key, value


def load_manual_merge_packet(path: Path, target_workspace_root: Path) -> ManualMergePacket:
    if not path.exists():
        raise FileNotFoundError(f"Manual merge packet not found: {path}")
    fields: dict[str, str] = {}
    accepted: list[AcceptedFileMapEntry] = []
    current_entry: dict[str, str] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("& [AcceptedFileMapEntry ") or stripped.startswith("& [RollbackPlan]"):
            if current_entry:
                accepted.append(_accepted_entry(current_entry, target_workspace_root))
            current_entry = {} if stripped.startswith("& [AcceptedFileMapEntry ") else None
            continue
        parsed = _field(line)
        if not parsed:
            continue
        key, value = parsed
        if current_entry is not None and key in {"source_ref", "target_path", "source_assignment_ref"}:
            current_entry[key] = value
        else:
            fields[key] = value
    if current_entry:
        accepted.append(_accepted_entry(current_entry, target_workspace_root))
    return ManualMergePacket(
        packet_id=fields.get("packet_id", path.stem),
        source_run_root=fields.get("source_run_root", str(path.parent.name)),
        target_workspace_root=str(target_workspace_root),
        accepted_files=tuple(accepted),
        rejected_output_refs=(),
        conflict_resolution_refs=(),
        rollback_plan=RollbackPlan(entries=(), verification_command=fields.get("verification_command", "not_specified")),
        manager_acceptance_ref=fields.get("manager_acceptance_ref", "missing"),
        shaliach_review_ref=fields.get("shaliach_review_ref", "missing"),
        verification_command=fields.get("verification_command", "not_specified"),
    )


def _accepted_entry(fields: dict[str, str], target_workspace_root: Path) -> AcceptedFileMapEntry:
    target_path = fields["target_path"]
    ensure_target_path_within_workspace(target_workspace_root, target_path)
    return AcceptedFileMapEntry(
        source_ref=fields["source_ref"],
        target_path=target_path,
        source_assignment_ref=fields["source_assignment_ref"],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="apply-manual-merge-packet")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--target-workspace-root", required=True)
    parser.add_argument("--verification-command", default=None)
    parser.add_argument("--i-understand-this-mutates-workspace", action="store_true")
    args = parser.parse_args(argv)
    run_root = Path(args.run_root)
    target_workspace_root = Path(args.target_workspace_root)
    if args.i_understand_this_mutates_workspace:
        try:
            packet = load_manual_merge_packet(run_root / "manual_merge_packet.sop", target_workspace_root)
            preflight = build_apply_mutation_preflight(run_root, target_workspace_root, packet)
            write_text(run_root / "apply_mutation_preflight.sop", preflight.to_sop())
            snapshot_status = "not_run"
            apply_status = "not_run"
            if preflight.status == "ready_for_mutation_implementation":
                snapshots = materialize_snapshot_evidence(run_root, target_workspace_root, packet)
                write_text(run_root / "snapshot_materialization.sop", snapshots.to_sop())
                snapshot_status = "written"
                write_result = apply_packet_files_to_workspace(run_root, target_workspace_root, packet)
                verification = _run_verification(args.verification_command or packet.verification_command, target_workspace_root)
                write_text(run_root / "verification_result.sop", verification)
                apply_status = "applied" if write_result.ok and "returncode] is 0" in verification else "failed"
                apply_result = ApplyResult(
                    apply_status=apply_status,
                    applied_files=write_result.applied_files,
                    skipped_files=write_result.skipped_files,
                    snapshot_refs=tuple(entry.snapshot_ref for entry in snapshots.entries if entry.snapshot_ref != "none"),
                    rollback_command=(
                        "rollback-manual-merge-packet --apply-result apply_result.sop "
                        "--target-workspace-root "
                        f"{target_workspace_root} --i-understand-this-mutates-workspace"
                    ),
                    verification_result_ref="verification_result.sop",
                    error_summary=write_result.error_summary,
                )
                write_text(run_root / "apply_result.sop", apply_result.to_sop())
            write_text(
                run_root / "apply_command_log.sop",
                "& [ApplyCommandLog] is a mutation preflight command log\n"
                f"  + [status] is {preflight.status}\n"
                f"  + [reason] is {preflight.reason}\n"
                f"  + [snapshot_materialization] is {snapshot_status}\n"
                f"  + [apply_status] is {apply_status}\n"
                f"  + [mutation_performed] is {str(apply_status in {'applied', 'failed'}).lower()}\n"
                "  + [authority_boundary] is explicit_operator_acknowledgement_required_for_mutation\n",
            )
            return 0 if apply_status == "applied" else 2
        except (FileNotFoundError, KeyError, ValueError) as exc:
            write_text(
                run_root / "apply_command_log.sop",
                "& [ApplyCommandLog] is a mutation preflight command log\n"
                "  + [status] is rejected\n"
                f"  + [reason] is {str(exc)}\n"
                "  + [mutation_performed] is false\n"
                "  + [authority_boundary] is mutation_preflight_not_mutation_command\n",
            )
            return 2
    try:
        packet = load_manual_merge_packet(run_root / "manual_merge_packet.sop", target_workspace_root)
        if args.verification_command:
            packet = ManualMergePacket(
                packet_id=packet.packet_id,
                source_run_root=packet.source_run_root,
                target_workspace_root=packet.target_workspace_root,
                accepted_files=packet.accepted_files,
                rejected_output_refs=packet.rejected_output_refs,
                conflict_resolution_refs=packet.conflict_resolution_refs,
                rollback_plan=packet.rollback_plan,
                manager_acceptance_ref=packet.manager_acceptance_ref,
                shaliach_review_ref=packet.shaliach_review_ref,
                verification_command=args.verification_command,
            )
        apply_plan, apply_result = build_dry_run_apply_artifacts(packet)
        write_text(run_root / "apply_plan.sop", apply_plan.to_sop())
        write_text(run_root / "apply_result.sop", apply_result.to_sop())
        write_text(
            run_root / "apply_command_log.sop",
            "& [ApplyCommandLog] is a dry-run apply command log\n"
            "  + [status] is dry_run_completed\n"
            f"  + [run_root] is {run_root}\n"
            f"  + [target_workspace_root] is {target_workspace_root}\n"
            "  + [authority_boundary] is dry_run_cli_not_mutation_command\n",
        )
        return 0
    except (FileNotFoundError, KeyError, ValueError) as exc:
        write_text(
            run_root / "apply_command_log.sop",
            "& [ApplyCommandLog] is a dry-run apply command log\n"
            "  + [status] is rejected\n"
            f"  + [reason] is {str(exc)}\n"
            "  + [authority_boundary] is dry_run_cli_not_mutation_command\n",
        )
        return 1


def _run_verification(command: str, cwd: Path) -> str:
    if not command or command == "not_specified":
        return """& [VerificationResult] is the post-apply verification result
  + [command] is not_specified
  + [returncode] is 1
  + [stdout_tail] is none
  + [stderr_tail] is verification command missing
  + [authority_boundary] is verification_result_not_manager_acceptance
"""
    result = subprocess.run(command, cwd=cwd, shell=True, capture_output=True, text=True, timeout=180, check=False)
    return f"""& [VerificationResult] is the post-apply verification result
  + [command] is {command}
  + [returncode] is {result.returncode}
  + [stdout_tail] is {_tail(result.stdout)}
  + [stderr_tail] is {_tail(result.stderr)}
  + [authority_boundary] is verification_result_not_manager_acceptance
"""


def _tail(text: str, limit: int = 240) -> str:
    return " ".join(text.replace("\x00", "").split())[:limit].rstrip() if text else "none"


if __name__ == "__main__":
    raise SystemExit(main())
