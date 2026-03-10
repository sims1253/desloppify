"""Enrich and sense-check triage confirmation handlers."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from desloppify.base.output.terminal import colorize
from desloppify.base.output.user_message import print_user_message

from .basic import MIN_ATTESTATION_LEN, validate_attestation
from .shared import (
    StageConfirmationRequest,
    ensure_stage_is_confirmable,
    finalize_stage_confirmation,
)
from ..services import TriageServices, default_triage_services


@dataclass(frozen=True)
class _ConfirmationCheckIssue:
    code: str
    total: int
    rows: list[tuple]


@dataclass(frozen=True)
class _ConfirmationCheckReport:
    failures: list[_ConfirmationCheckIssue]
    warnings: list[_ConfirmationCheckIssue]

    def failure(self, code: str) -> _ConfirmationCheckIssue | None:
        for issue in self.failures:
            if issue.code == code:
                return issue
        return None

    def warning(self, code: str) -> _ConfirmationCheckIssue | None:
        for issue in self.warnings:
            if issue.code == code:
                return issue
        return None


def _print_confirmation_failure(
    *,
    issue: _ConfirmationCheckIssue | None,
    header: str,
    row_printer,
    hints: tuple[str, ...] = (),
) -> bool:
    if issue is None:
        return False
    print(colorize(header.format(total=issue.total), "red"))
    row_printer(issue)
    for hint in hints:
        print(colorize(hint, "dim"))
    return True


def _collect_enrich_level_confirmation_checks(
    plan: dict,
    *,
    include_stale_issue_ref_warning: bool,
) -> _ConfirmationCheckReport:
    from ..validation.core import (
        _steps_missing_issue_refs,
        _steps_referencing_skipped_issues,
        _steps_with_bad_paths,
        _steps_with_vague_detail,
        _steps_without_effort,
        _underspecified_steps,
    )
    from desloppify.base.discovery.paths import get_project_root

    repo_root = get_project_root()

    failures: list[_ConfirmationCheckIssue] = []
    warnings: list[_ConfirmationCheckIssue] = []

    underspec = _underspecified_steps(plan)
    if underspec:
        failures.append(
            _ConfirmationCheckIssue(
                code="underspecified",
                total=sum(n for _, n, _ in underspec),
                rows=underspec,
            )
        )

    bad_paths = _steps_with_bad_paths(plan, repo_root)
    if bad_paths:
        failures.append(
            _ConfirmationCheckIssue(
                code="bad_paths",
                total=sum(len(paths) for _, _, paths in bad_paths),
                rows=bad_paths,
            )
        )

    missing_effort = _steps_without_effort(plan)
    if missing_effort:
        failures.append(
            _ConfirmationCheckIssue(
                code="missing_effort",
                total=sum(n for _, n, _ in missing_effort),
                rows=missing_effort,
            )
        )

    missing_refs = _steps_missing_issue_refs(plan)
    if missing_refs:
        failures.append(
            _ConfirmationCheckIssue(
                code="missing_issue_refs",
                total=sum(n for _, n, _ in missing_refs),
                rows=missing_refs,
            )
        )

    vague_detail = _steps_with_vague_detail(plan, repo_root)
    if vague_detail:
        failures.append(
            _ConfirmationCheckIssue(
                code="vague_detail",
                total=len(vague_detail),
                rows=vague_detail,
            )
        )

    if include_stale_issue_ref_warning:
        stale_refs = _steps_referencing_skipped_issues(plan)
        if stale_refs:
            warnings.append(
                _ConfirmationCheckIssue(
                    code="stale_issue_refs",
                    total=sum(len(ids) for _, _, ids in stale_refs),
                    rows=stale_refs,
                )
            )

    return _ConfirmationCheckReport(failures=failures, warnings=warnings)


def _print_underspecified_rows(issue: _ConfirmationCheckIssue) -> None:
    for name, bare, total in issue.rows[:5]:
        print(colorize(f"    {name}: {bare}/{total} steps", "yellow"))
    print()


def _print_bad_path_rows(issue: _ConfirmationCheckIssue) -> None:
    for name, step_num, paths in issue.rows:
        for path_str in paths:
            print(colorize(f"    {name} step {step_num}: {path_str}", "yellow"))


def _print_missing_ratio_rows(issue: _ConfirmationCheckIssue, *, suffix: str) -> None:
    for name, missing, total in issue.rows[:5]:
        print(colorize(f"    {name}: {missing}/{total} steps {suffix}", "yellow"))


def _print_vague_detail_rows(issue: _ConfirmationCheckIssue) -> None:
    for name, step_num, title in issue.rows[:5]:
        print(colorize(f"    {name} step {step_num}: {title}", "yellow"))


def _handle_enrich_failures(checks: _ConfirmationCheckReport) -> bool:
    if _print_confirmation_failure(
        issue=checks.failure("underspecified"),
        header="\n  Cannot confirm: {total} step(s) still lack detail or issue_refs.",
        row_printer=_print_underspecified_rows,
        hints=(
            "  Every step needs --detail (sub-points) or --issue-refs (for auto-completion).",
            '  Fix: desloppify plan cluster update <name> --update-step N --detail "sub-details"',
        ),
    ):
        return True
    print(colorize("  All steps have detail or issue_refs.", "green"))
    if _print_confirmation_failure(
        issue=checks.failure("bad_paths"),
        header="\n  Cannot confirm: {total} file path(s) in step details don't exist on disk.",
        row_printer=_print_bad_path_rows,
        hints=("  Fix paths with: desloppify plan cluster update <name> --update-step N --detail '...'",),
    ):
        return True
    if _print_confirmation_failure(
        issue=checks.failure("missing_effort"),
        header="\n  Cannot confirm: {total} step(s) have no effort tag.",
        row_printer=lambda issue: _print_missing_ratio_rows(issue, suffix="missing effort"),
        hints=(
            "  Every step needs --effort (trivial/small/medium/large).",
            "  Fix: desloppify plan cluster update <name> --update-step N --effort small",
        ),
    ):
        return True
    if _print_confirmation_failure(
        issue=checks.failure("missing_issue_refs"),
        header="\n  Cannot confirm: {total} step(s) have no issue_refs.",
        row_printer=lambda issue: _print_missing_ratio_rows(issue, suffix="missing refs"),
        hints=(
            "  Every step needs --issue-refs linking it to the review issue(s) it addresses.",
            "  Fix: desloppify plan cluster update <name> --update-step N --issue-refs <hash1> <hash2>",
        ),
    ):
        return True
    return _print_confirmation_failure(
        issue=checks.failure("vague_detail"),
        header="\n  Cannot confirm: {total} step(s) have vague detail (< 80 chars, no file paths).",
        row_printer=_print_vague_detail_rows,
        hints=(
            "  Executor-ready means: someone with zero context knows which file to open and what to change.",
            "  Add file paths and specific instructions to each step's --detail.",
        ),
    )


def _print_stale_ref_warning(issue: _ConfirmationCheckIssue | None) -> None:
    if issue is None:
        return
    print(colorize(f"\n  Warning: {issue.total} step issue_ref(s) point to skipped/wontfixed issues.", "yellow"))
    for name, step_num, ids in issue.rows[:5]:
        print(colorize(f"    {name} step {step_num}: {', '.join(ids[:3])}", "yellow"))
    print(colorize("  Consider removing stale refs or removing the step if it's no longer needed.", "dim"))


def _handle_sense_check_failures(checks: _ConfirmationCheckReport) -> bool:
    failure_messages = {
        "underspecified": "still lack detail or issue_refs.",
        "bad_paths": "file path(s) in step details don't exist on disk.",
        "missing_effort": "step(s) have no effort tag.",
        "missing_issue_refs": "step(s) have no issue_refs.",
        "vague_detail": "step(s) have vague detail.",
    }
    for code, suffix in failure_messages.items():
        issue = checks.failure(code)
        if issue is None:
            continue
        print(colorize(f"\n  Cannot confirm: {issue.total} {suffix}", "red"))
        if code == "underspecified":
            _print_underspecified_rows(issue)
        elif code == "bad_paths":
            _print_bad_path_rows(issue)
        return True
    return False


def confirm_enrich(
    args: argparse.Namespace,
    plan: dict,
    stages: dict,
    attestation: str | None,
    *,
    services: TriageServices | None = None,
) -> None:
    """Show enrich summary and record confirmation if attestation is valid."""
    resolved_services = services or default_triage_services()
    if not ensure_stage_is_confirmable(stages, stage="enrich"):
        return

    checks = _collect_enrich_level_confirmation_checks(
        plan,
        include_stale_issue_ref_warning=True,
    )

    print(colorize("  Stage: ENRICH — Make steps executor-ready (detail, refs)", "bold"))
    print(colorize("  " + "─" * 54, "dim"))

    if _handle_enrich_failures(checks):
        return

    _print_stale_ref_warning(checks.warning("stale_issue_refs"))

    enrich_clusters = [n for n in plan.get("clusters", {}) if not plan["clusters"][n].get("auto")]

    if not finalize_stage_confirmation(
        plan=plan,
        stages=stages,
        request=StageConfirmationRequest(
            stage="enrich",
            attestation=attestation,
            min_attestation_len=MIN_ATTESTATION_LEN,
            command_hint='desloppify plan triage --confirm enrich --attestation "Steps are executor-ready..."',
            validation_stage="enrich",
            validate_attestation_fn=validate_attestation,
            validation_kwargs={"cluster_names": enrich_clusters},
            log_action="triage_confirm_enrich",
        ),
        services=resolved_services,
    ):
        return
    print_user_message(
        "Hey — enrich is confirmed. Run `desloppify plan triage"
        " --stage sense-check --report \"...\"` to verify step"
        " accuracy and cross-cluster dependencies."
    )


def confirm_sense_check(
    args: argparse.Namespace,
    plan: dict,
    stages: dict,
    attestation: str | None,
    *,
    services: TriageServices | None = None,
) -> None:
    """Show sense-check summary and record confirmation if attestation is valid."""
    resolved_services = services or default_triage_services()
    if not ensure_stage_is_confirmable(stages, stage="sense-check"):
        return

    checks = _collect_enrich_level_confirmation_checks(
        plan,
        include_stale_issue_ref_warning=False,
    )

    print(colorize("  Stage: SENSE-CHECK — Verify accuracy & cross-cluster deps", "bold"))
    print(colorize("  " + "─" * 57, "dim"))

    if _handle_sense_check_failures(checks):
        return

    print(colorize("  All enrich-level checks pass.", "green"))

    sense_check_clusters = [n for n in plan.get("clusters", {}) if not plan["clusters"][n].get("auto")]

    if not finalize_stage_confirmation(
        plan=plan,
        stages=stages,
        request=StageConfirmationRequest(
            stage="sense-check",
            attestation=attestation,
            min_attestation_len=MIN_ATTESTATION_LEN,
            command_hint='desloppify plan triage --confirm sense-check --attestation "Content and structure verified..."',
            validation_stage="sense-check",
            validate_attestation_fn=validate_attestation,
            validation_kwargs={"cluster_names": sense_check_clusters},
            log_action="triage_confirm_sense_check",
        ),
        services=resolved_services,
    ):
        return
    print_user_message(
        "Hey — sense-check is confirmed. Run `desloppify plan triage"
        " --complete --strategy \"...\"` to finish triage."
    )


__all__ = ["confirm_enrich", "confirm_sense_check"]
