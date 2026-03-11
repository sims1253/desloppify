"""State compatibility facade.

Prefer narrower surfaces for new code:
- ``desloppify.state_io`` for persistence/schema contracts
- ``desloppify.state_scoring`` for scoring-only reads

Compatibility owner: core-platform
Removal target: 2026-06-30
"""

from typing import NamedTuple

from desloppify.engine._state.filtering import (
    add_ignore,
    is_ignored,
    issue_in_scan_scope,
    make_issue,
    open_scope_breakdown,
    path_scoped_issues,
    remove_ignored_issues,
)
from desloppify.engine._state.merge import (
    MergeScanOptions,
    find_suspect_detectors,
    merge_scan,
    upsert_issues,
)
from desloppify.engine._state.noise import (
    DEFAULT_ISSUE_NOISE_BUDGET,
    DEFAULT_ISSUE_NOISE_GLOBAL_BUDGET,
    apply_issue_noise_budget,
    resolve_issue_noise_budget,
    resolve_issue_noise_global_budget,
    resolve_issue_noise_settings,
)
from desloppify.engine._state.persistence import load_state, save_state, state_lock
from desloppify.engine._state.resolution import (
    coerce_assessment_score,
    match_issues,
    resolve_issues,
)
from desloppify.engine._state.schema import (
    CURRENT_VERSION,
    ConcernDismissal,
    DimensionScore,
    Issue,
    ScanMetadataModel,
    StateModel,
    StateStats,
    SubjectiveAssessment,
    SubjectiveIntegrity,
    empty_state,
    ensure_state_defaults,
    get_state_dir,
    get_state_file,
    json_default,
    migrate_state_keys,
    scan_inventory_available,
    scan_metadata,
    scan_metrics_available,
    utc_now,
    validate_state_invariants,
)
from desloppify.engine._state.schema_scores import (
    get_objective_score,
    get_overall_score,
    get_strict_score,
    get_verified_strict_score,
)
from desloppify.engine._state.scoring import (
    suppression_metrics,
)


class ScoreSnapshot(NamedTuple):
    """All four canonical scores from a single state dict."""

    overall: float | None
    objective: float | None
    strict: float | None
    verified: float | None


def score_snapshot(state: StateModel) -> ScoreSnapshot:
    """Load all four canonical scores from *state* in one call."""
    return ScoreSnapshot(
        overall=get_overall_score(state),
        objective=get_objective_score(state),
        strict=get_strict_score(state),
        verified=get_verified_strict_score(state),
    )


__all__ = [
    # Types
    "ConcernDismissal",
    "DimensionScore",
    "Issue",
    "ScanMetadataModel",
    "MergeScanOptions",
    "ScoreSnapshot",
    "StateModel",
    "StateStats",
    "SubjectiveAssessment",
    "SubjectiveIntegrity",
    # Constants
    "CURRENT_VERSION",
    "DEFAULT_ISSUE_NOISE_BUDGET",
    "DEFAULT_ISSUE_NOISE_GLOBAL_BUDGET",
    "get_state_dir",
    "get_state_file",
    # Functions
    "add_ignore",
    "apply_issue_noise_budget",
    "coerce_assessment_score",
    "empty_state",
    "ensure_state_defaults",
    "find_suspect_detectors",
    "issue_in_scan_scope",
    "open_scope_breakdown",
    "is_ignored",
    "json_default",
    "load_state",
    "make_issue",
    "match_issues",
    "merge_scan",
    "path_scoped_issues",
    "remove_ignored_issues",
    "resolve_issue_noise_budget",
    "resolve_issue_noise_global_budget",
    "resolve_issue_noise_settings",
    "resolve_issues",
    "save_state",
    "scan_inventory_available",
    "scan_metadata",
    "scan_metrics_available",
    "state_lock",
    "score_snapshot",
    "suppression_metrics",
    "upsert_issues",
    "utc_now",
    "validate_state_invariants",
    "migrate_state_keys",
]
