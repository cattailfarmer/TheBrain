from __future__ import annotations

import argparse
from pathlib import Path

from .conversation import ActiveConversationPointer, ConversationSurface
from .frontier_application import (
    apply_frontier_application_plan,
    build_frontier_application_plan,
    load_frontier_advancement_record,
    load_frontier_application_plan,
    write_frontier_application_plan,
    write_frontier_application_result,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write dry-run frontier application plans without mutating conversation surfaces.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--advancement-ref", default=None)
    parser.add_argument("--apply-plan", action="store_true")
    parser.add_argument("--plan-ref", default="frontier_application_plan.sop")
    parser.add_argument("--result-id", default="frontier-application-result-1")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--plan-id", default="frontier-application-plan-1")
    parser.add_argument("--current-frontier", default=None)
    parser.add_argument("--conversation-surface-ref", default=None)
    parser.add_argument("--completed-slice-ref", action="append", default=[])
    parser.add_argument("--narrative-update-required", action="store_true")
    parser.add_argument("--narrative-update-deferred", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.apply_plan:
            plan_path = _resolve(args.project_root, args.plan_ref)
            plan = load_frontier_application_plan(plan_path)
            result = apply_frontier_application_plan(
                project_root=args.project_root,
                plan=plan,
                plan_ref=args.plan_ref,
                result_id=args.result_id,
                narrative_update_ref="coordination/project_narrative_surface.sop" if plan.narrative_update_required else "none",
            )
            output_dir = _resolve(args.project_root, args.output_dir or plan_path.parent.as_posix())
            path = write_frontier_application_result(output_dir, result)
            print(
                "& [FrontierApplicationApplyResult] is frontier application explicit apply evidence\n"
                f"  + [artifact_ref] is {path.relative_to(args.project_root).as_posix()}\n"
                f"  + [applied_status] is {result.applied_status}\n"
                "  + [authority_boundary] is frontier_application_apply_not_code_apply\n",
                end="",
            )
            return 0 if result.applied_status == "applied" else 1
        if not args.advancement_ref:
            raise ValueError("--advancement-ref is required unless --apply-plan is set")
        advancement_path = _resolve(args.project_root, args.advancement_ref)
        advancement = load_frontier_advancement_record(advancement_path)
        if args.conversation_surface_ref:
            conversation_surface_ref = args.conversation_surface_ref
        else:
            pointer = ActiveConversationPointer.load(args.project_root)
            conversation_surface_ref = pointer.surface_path.relative_to(args.project_root).as_posix()
        current_frontier = args.current_frontier
        if current_frontier is None:
            current_frontier = ConversationSurface.load(_resolve(args.project_root, conversation_surface_ref)).first("current_frontier", "unknown") or "unknown"
        plan = build_frontier_application_plan(
            plan_id=args.plan_id,
            advancement_ref=args.advancement_ref,
            advancement=advancement,
            conversation_surface_ref=conversation_surface_ref,
            current_frontier=current_frontier,
            completed_slice_refs_to_append=tuple(args.completed_slice_ref),
            narrative_update_required=not args.narrative_update_deferred if not args.narrative_update_required else True,
        )
        output_dir = _resolve(args.project_root, args.output_dir or advancement_path.parent.as_posix())
        path = write_frontier_application_plan(output_dir, plan)
        print(
            "& [FrontierApplicationPlanWriteResult] is frontier application plan evidence persistence\n"
            f"  + [artifact_ref] is {path.relative_to(args.project_root).as_posix()}\n"
            "  + [authority_boundary] is frontier_application_plan_write_not_surface_mutation\n",
            end="",
        )
        return 0
    except (FileNotFoundError, FileExistsError, KeyError, ValueError) as exc:
        print(
            "& [FrontierApplicationPlanError] is frontier application plan failure evidence\n"
            f"  + [error] is {str(exc)}\n"
            "  + [authority_boundary] is frontier_application_plan_error_not_surface_mutation\n",
            end="",
        )
        return 1


def _resolve(project_root: Path, ref: str) -> Path:
    path = Path(ref)
    return path if path.is_absolute() else project_root / path


if __name__ == "__main__":
    raise SystemExit(main())
