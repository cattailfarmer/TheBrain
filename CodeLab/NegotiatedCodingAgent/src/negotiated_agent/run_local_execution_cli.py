from __future__ import annotations

import argparse
from pathlib import Path
from uuid import uuid4

from .execution_gate import load_execution_gate_decision
from .run_local_execution import build_run_local_execution_plan, execute_run_local_plan, load_run_local_execution_plan
from .worker_lifecycle import load_worker_cycle_record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a run-local execution plan without generating implementation files.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--worker", required=True)
    parser.add_argument("--execution-gate-ref", default=None)
    parser.add_argument("--ready-cycle-ref", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--cycle-id", default=None)
    parser.add_argument("--plan-id", default=None)
    parser.add_argument("--execute-plan", action="store_true")
    parser.add_argument("--plan-ref", default=None)
    parser.add_argument("--result-id", default=None)
    parser.add_argument("--generated-text", default="Generated run-local implementation evidence.\n")
    parser.add_argument("--worker-cycle-ref", default=None)
    args = parser.parse_args(argv)
    try:
        if args.execute_plan:
            if not args.plan_ref or not args.result_id or not args.worker_cycle_ref:
                raise ValueError("--plan-ref, --result-id, and --worker-cycle-ref are required with --execute-plan")
            plan = load_run_local_execution_plan(_resolve(args.project_root, args.plan_ref))
            result = execute_run_local_plan(
                project_root=args.project_root,
                plan=plan,
                plan_ref=args.plan_ref,
                result_id=args.result_id,
                worker_cycle_ref=args.worker_cycle_ref,
                generated_text=args.generated_text,
            )
            print(
                "& [RunLocalExecutionWriteResult] is run-local generated evidence persistence\n"
                f"  + [result_id] is {result.result_id}\n"
                f"  + [generated_file_set] is {', '.join(result.generated_files)}\n"
                "  + [authority_boundary] is run_local_execution_write_not_target_workspace_application\n",
                end="",
            )
            return 0
        if not args.execution_gate_ref or not args.ready_cycle_ref or not args.run_id or not args.cycle_id:
            raise ValueError("--execution-gate-ref, --ready-cycle-ref, --run-id, and --cycle-id are required when planning")
        gate = load_execution_gate_decision(_resolve(args.project_root, args.execution_gate_ref))
        cycle = load_worker_cycle_record(_resolve(args.project_root, args.ready_cycle_ref))
        run_local_root = args.project_root / "runs" / args.run_id / "worker_execution" / args.cycle_id
        plan = build_run_local_execution_plan(
            plan_id=args.plan_id or str(uuid4()),
            worker_uuid=args.worker,
            execution_gate=gate,
            execution_gate_ref=args.execution_gate_ref,
            ready_cycle=cycle,
            ready_cycle_ref=args.ready_cycle_ref,
            project_root=args.project_root,
            run_id=args.run_id,
            run_local_root=run_local_root,
        )
        out = run_local_root / "run_local_execution_plan.sop"
        if out.exists():
            raise FileExistsError(f"{out} already exists")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(plan.to_sop(), encoding="utf-8")
        print(
            "& [RunLocalExecutionPlanWriteResult] is run-local execution plan persistence evidence\n"
            f"  + [plan_id] is {plan.plan_id}\n"
            f"  + [artifact_ref] is {out.relative_to(args.project_root).as_posix()}\n"
            "  + [authority_boundary] is run_local_execution_plan_write_not_implementation_execution\n",
            end="",
        )
        return 0
    except (FileNotFoundError, FileExistsError, KeyError, ValueError) as exc:
        print(
            "& [RunLocalExecutionPlanError] is run-local execution planning failure evidence\n"
            f"  + [error] is {str(exc)}\n"
            "  + [authority_boundary] is run_local_execution_plan_error_not_implementation_execution\n",
            end="",
        )
        return 1


def _resolve(project_root: Path, ref: str) -> Path:
    path = Path(ref)
    return path if path.is_absolute() else project_root / path


if __name__ == "__main__":
    raise SystemExit(main())
