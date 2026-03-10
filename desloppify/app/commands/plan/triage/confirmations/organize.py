"""Organize-stage triage confirmation handler."""

from __future__ import annotations

import argparse

from desloppify.base.output.terminal import colorize
from desloppify.base.output.user_message import print_user_message

from .basic import MIN_ATTESTATION_LEN, validate_attestation
from .shared import (
    StageConfirmationRequest,
    ensure_stage_is_confirmable,
    finalize_stage_confirmation,
)
from ..display.dashboard import show_plan_summary
from ..helpers import count_log_activity_since, open_review_ids_from_state, triage_coverage
from ..services import TriageServices, default_triage_services


def _require_enriched_clusters(plan: dict) -> bool:
    from ..stages.helpers import unenriched_clusters  # noqa: PLC0415

    gaps = unenriched_clusters(plan)
    if not gaps:
        return True
    print(colorize(f"\n  Cannot confirm: {len(gaps)} cluster(s) still need enrichment.", "red"))
    for name, missing in gaps:
        print(colorize(f"    {name}: missing {', '.join(missing)}", "yellow"))
    print(colorize("  Small clusters (<5 issues) need at least 1 action step per issue.", "dim"))
    print(colorize('  Fix: desloppify plan cluster update <name> --steps "step1" "step2"', "dim"))
    return False


def _require_clustered_review_issues(plan: dict, state: dict) -> bool:
    from ..stages.helpers import unclustered_review_issues  # noqa: PLC0415

    unclustered = unclustered_review_issues(plan, state)
    if not unclustered:
        return True
    print(colorize(f"\n  Cannot confirm: {len(unclustered)} review issue(s) have no action plan.", "red"))
    for fid in unclustered[:5]:
        short = fid.rsplit("::", 2)[-2] if "::" in fid else fid
        print(colorize(f"    {short}", "yellow"))
    if len(unclustered) > 5:
        print(colorize(f"    ... and {len(unclustered) - 5} more", "yellow"))
    print(colorize("  Add each to a cluster or wontfix it before confirming.", "dim"))
    return False


def _print_reflect_activity_summary(plan: dict, stages: dict) -> None:
    reflect_ts = stages.get("reflect", {}).get("timestamp", "")
    if not reflect_ts:
        return
    activity = count_log_activity_since(plan, reflect_ts)
    if activity:
        print("  Since reflect, you have:")
        for action, count in sorted(activity.items()):
            print(f"    {action}: {count}")
        return
    print("  No logged plan operations since reflect.")


def _organize_cluster_names(plan: dict) -> list[str]:
    return [
        name for name in plan.get("clusters", {}) if not plan["clusters"][name].get("auto")
    ]


def _warn_directory_scatter(plan: dict, *, scatter_fn) -> None:
    scattered = scatter_fn(plan)
    if not scattered:
        return
    print(colorize(f"\n  Warning: {len(scattered)} cluster(s) span many unrelated directories:", "yellow"))
    for name, dir_count, sample_dirs in scattered:
        print(colorize(f"    {name}: {dir_count} directories — likely grouped by theme, not area", "yellow"))
        for directory in sample_dirs[:3]:
            print(colorize(f"      {directory}", "dim"))
    print(colorize("  Consider splitting into area-focused clusters (same files in same PR).", "dim"))


def _warn_high_step_ratio(plan: dict, *, ratio_fn) -> None:
    high_ratio = ratio_fn(plan)
    if not high_ratio:
        return
    print(colorize(f"\n  Warning: {len(high_ratio)} cluster(s) have step count ≥ issue count:", "yellow"))
    for name, steps, issues, ratio in high_ratio:
        print(colorize(f"    {name}: {steps} steps for {issues} issues ({ratio:.1f}x)", "yellow"))
    print(colorize("  Steps should consolidate changes to the same file. 1:1 means each issue is its own step.", "dim"))


def _overlap_dependency_gaps(overlaps: list[tuple[str, str, list[str]]], clusters: dict) -> list[tuple[str, str, list[str]]]:
    needs_dep = []
    for left, right, files in overlaps:
        left_deps = set(clusters.get(left, {}).get("depends_on_clusters", []))
        right_deps = set(clusters.get(right, {}).get("depends_on_clusters", []))
        if right not in left_deps and left not in right_deps:
            needs_dep.append((left, right, files))
    return needs_dep


def _warn_overlap_dependencies(plan: dict, *, overlap_fn) -> None:
    overlaps = overlap_fn(plan)
    if not overlaps:
        return
    clusters_dict = plan.get("clusters", {})
    print(colorize(f"\n  Note: {len(overlaps)} cluster pair(s) reference the same files:", "yellow"))
    for left, right, files in overlaps[:5]:
        print(colorize(f"    {left} ↔ {right}: {len(files)} shared file(s)", "yellow"))
    needs_dep = _overlap_dependency_gaps(overlaps, clusters_dict)
    if not needs_dep:
        return
    print(colorize("  These pairs have no dependency relationship — add one to prevent merge conflicts:", "dim"))
    for left, right, _files in needs_dep[:5]:
        print(colorize(f"    desloppify plan cluster update {right} --depends-on {left}", "dim"))
        print(colorize(f"    # or: desloppify plan cluster update {left} --depends-on {right}", "dim"))


def _warn_self_dependencies(clusters: dict) -> None:
    for name, cluster in clusters.items():
        deps = cluster.get("depends_on_clusters", [])
        if name in deps:
            print(colorize(f"  Warning: {name} depends on itself.", "yellow"))


def _warn_orphaned_clusters(clusters: dict) -> None:
    orphaned = [
        (name, len(cluster.get("action_steps", [])))
        for name, cluster in clusters.items()
        if not cluster.get("auto") and not cluster.get("issue_ids") and cluster.get("action_steps")
    ]
    if not orphaned:
        return
    print(colorize(f"\n  Note: {len(orphaned)} cluster(s) have steps but no issues:", "yellow"))
    for name, step_count in orphaned:
        print(colorize(f"    {name}: {step_count} steps, 0 issues", "yellow"))
    print(colorize("  These may need issues added, or may be leftover from resolved work.", "dim"))


def confirm_organize(
    args: argparse.Namespace,
    plan: dict,
    stages: dict,
    attestation: str | None,
    *,
    services: TriageServices | None = None,
) -> None:
    """Show full plan summary and record confirmation if attestation is valid."""
    resolved_services = services or default_triage_services()
    if not ensure_stage_is_confirmable(stages, stage="organize"):
        return

    runtime = resolved_services.command_runtime(args)
    state = runtime.state

    print(colorize("  Stage: ORGANIZE — Defer contradictions, cluster, & prioritize", "bold"))
    print(colorize("  " + "─" * 63, "dim"))
    _print_reflect_activity_summary(plan, stages)

    print(colorize("\n  Plan:", "bold"))
    show_plan_summary(plan, state)

    organize_clusters = _organize_cluster_names(plan)
    if not _require_enriched_clusters(plan):
        return
    if not _require_clustered_review_issues(plan, state):
        return

    # Organize warnings
    from ..validation.core import (  # noqa: PLC0415
        _cluster_file_overlaps,
        _clusters_with_directory_scatter,
        _clusters_with_high_step_ratio,
    )

    _warn_directory_scatter(plan, scatter_fn=_clusters_with_directory_scatter)
    _warn_high_step_ratio(plan, ratio_fn=_clusters_with_high_step_ratio)
    _warn_overlap_dependencies(plan, overlap_fn=_cluster_file_overlaps)
    all_clusters = plan.get("clusters", {})
    _warn_self_dependencies(all_clusters)
    _warn_orphaned_clusters(all_clusters)

    organized, total, _ = triage_coverage(plan, open_review_ids=open_review_ids_from_state(state))
    if not finalize_stage_confirmation(
        plan=plan,
        stages=stages,
        request=StageConfirmationRequest(
            stage="organize",
            attestation=attestation,
            min_attestation_len=MIN_ATTESTATION_LEN,
            command_hint='desloppify plan triage --confirm organize --attestation "This plan is correct..."',
            validation_stage="organize",
            validate_attestation_fn=validate_attestation,
            validation_kwargs={"cluster_names": organize_clusters},
            log_action="triage_confirm_organize",
            log_detail={"coverage": f"{organized}/{total}"},
            not_satisfied_hint="If not, adjust clusters, priorities, or queue order before completing.",
        ),
        services=resolved_services,
    ):
        return
    print_user_message(
        "Hey — organize is confirmed. Next: enrich your steps"
        " with detail and issue_refs so they're executor-ready."
        " Run `desloppify plan triage --stage enrich --report \"...\"`."
        " You can still reorganize (add/remove clusters, reorder)"
        " during the enrich stage."
    )


__all__ = ["confirm_organize"]
