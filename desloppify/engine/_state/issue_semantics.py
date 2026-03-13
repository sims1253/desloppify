"""Canonical work-item taxonomy and semantic helpers.

This module owns the semantic meaning of persisted tracked work. Callers should
use these helpers instead of branching on detector strings or ID prefixes.

Legacy ``issue`` names remain as aliases so the wider codebase can move
incrementally without losing semantic clarity.
"""

from __future__ import annotations

from typing import Any, Mapping, TypeAlias

WorkItemKind: TypeAlias = str
WorkItemOrigin: TypeAlias = str

MECHANICAL_DEFECT = "mechanical_defect"
REVIEW_DEFECT = "review_defect"
REVIEW_CONCERN = "review_concern"
ASSESSMENT_REQUEST = "assessment_request"

SCAN_ORIGIN = "scan"
REVIEW_IMPORT_ORIGIN = "review_import"
SYNTHETIC_TASK_ORIGIN = "synthetic_task"

WORK_ITEM_KINDS: frozenset[str] = frozenset(
    {
        MECHANICAL_DEFECT,
        REVIEW_DEFECT,
        REVIEW_CONCERN,
        ASSESSMENT_REQUEST,
    }
)
WORK_ITEM_ORIGINS: frozenset[str] = frozenset(
    {
        SCAN_ORIGIN,
        REVIEW_IMPORT_ORIGIN,
        SYNTHETIC_TASK_ORIGIN,
    }
)

# Legacy semantic aliases kept for compatibility while the repo moves to the
# work-item terminology.
MECHANICAL_FINDING = MECHANICAL_DEFECT
REVIEW_FINDING = REVIEW_DEFECT
CONCERN_FINDING = REVIEW_CONCERN
REVIEW_REQUEST = ASSESSMENT_REQUEST
SYNTHETIC_REQUEST_ORIGIN = SYNTHETIC_TASK_ORIGIN
ISSUE_KINDS = WORK_ITEM_KINDS
ISSUE_ORIGINS = WORK_ITEM_ORIGINS

_LEGACY_KIND_ALIASES: dict[str, str] = {
    "mechanical_finding": MECHANICAL_DEFECT,
    "review_finding": REVIEW_DEFECT,
    "concern_finding": REVIEW_CONCERN,
    "review_request": ASSESSMENT_REQUEST,
}
_LEGACY_ORIGIN_ALIASES: dict[str, str] = {
    "synthetic_request": SYNTHETIC_TASK_ORIGIN,
}

# Mechanical detectors that remain actionable work but stay excluded from
# detector-side scoring rules.
SCORING_EXCLUDED_DETECTORS: frozenset[str] = frozenset(
    {
        "concerns",
        "review",
        "subjective_review",
        "uncalled_functions",
        "unused_enums",
        "signature",
        "stale_wontfix",
    }
)


def infer_work_item_kind(
    detector: object,
    *,
    detail: Mapping[str, Any] | None = None,
) -> WorkItemKind:
    """Infer a persisted work-item kind from detector/detail fields."""
    detector_name = str(detector or "").strip()
    detail_dict = detail if isinstance(detail, Mapping) else {}

    if detector_name == "review":
        return REVIEW_DEFECT
    if detector_name == "concerns":
        return REVIEW_CONCERN
    if detector_name in {"subjective_review", "subjective_assessment", "holistic_review"}:
        return ASSESSMENT_REQUEST
    # Legacy imported confirmed concerns sometimes carried review-like detail;
    # keep explicit concern markers mapped to concern findings.
    if str(detail_dict.get("concern_verdict", "")).strip().lower() == "confirmed":
        return REVIEW_CONCERN
    return MECHANICAL_DEFECT


def infer_work_item_origin(
    detector: object,
    *,
    detail: Mapping[str, Any] | None = None,
) -> WorkItemOrigin:
    """Infer provenance for a persisted work item."""
    detector_name = str(detector or "").strip()
    detail_dict = detail if isinstance(detail, Mapping) else {}

    if detector_name == "review":
        return REVIEW_IMPORT_ORIGIN
    if detector_name == "concerns":
        verdict = str(detail_dict.get("concern_verdict", "")).strip().lower()
        return REVIEW_IMPORT_ORIGIN if verdict == "confirmed" else SCAN_ORIGIN
    if detector_name in {"subjective_review", "subjective_assessment", "holistic_review"}:
        return SYNTHETIC_TASK_ORIGIN
    return SCAN_ORIGIN


def infer_issue_kind(
    detector: object,
    *,
    detail: Mapping[str, Any] | None = None,
) -> WorkItemKind:
    """Backward-compatible alias for canonical work-item kind inference."""
    return infer_work_item_kind(detector, detail=detail)


def infer_issue_origin(
    detector: object,
    *,
    detail: Mapping[str, Any] | None = None,
) -> WorkItemOrigin:
    """Backward-compatible alias for canonical work-item origin inference."""
    return infer_work_item_origin(detector, detail=detail)


def normalized_work_item_kind(issue: Mapping[str, Any]) -> WorkItemKind:
    """Return the canonical work-item kind, inferring from legacy data when needed."""
    raw_kind = str(
        issue.get("work_item_kind", issue.get("issue_kind", ""))
    ).strip()
    if raw_kind in WORK_ITEM_KINDS:
        return raw_kind
    if raw_kind in _LEGACY_KIND_ALIASES:
        return _LEGACY_KIND_ALIASES[raw_kind]
    return infer_work_item_kind(issue.get("detector", ""), detail=_detail_dict(issue))


def normalized_issue_kind(issue: Mapping[str, Any]) -> WorkItemKind:
    """Backward-compatible alias for canonical work-item kind normalization."""
    return normalized_work_item_kind(issue)


def normalized_work_item_origin(issue: Mapping[str, Any]) -> WorkItemOrigin:
    """Return the canonical work-item origin, inferring from legacy data when needed."""
    raw_origin = str(issue.get("origin", "")).strip()
    if raw_origin in WORK_ITEM_ORIGINS:
        return raw_origin
    if raw_origin in _LEGACY_ORIGIN_ALIASES:
        return _LEGACY_ORIGIN_ALIASES[raw_origin]
    return infer_work_item_origin(issue.get("detector", ""), detail=_detail_dict(issue))


def normalized_issue_origin(issue: Mapping[str, Any]) -> WorkItemOrigin:
    """Backward-compatible alias for canonical work-item origin normalization."""
    return normalized_work_item_origin(issue)


def ensure_issue_semantics(issue: dict[str, Any]) -> None:
    """Populate canonical semantic fields in-place.

    Both ``work_item_kind`` and legacy ``issue_kind`` are written so current
    in-repo callers can migrate incrementally while persisted state moves
    toward the work-item terminology.
    """
    kind = normalized_work_item_kind(issue)
    origin = normalized_work_item_origin(issue)
    issue["work_item_kind"] = kind
    issue["issue_kind"] = kind
    issue["origin"] = origin


def ensure_work_item_semantics(issue: dict[str, Any]) -> None:
    """Preferred name for semantic normalization."""
    ensure_issue_semantics(issue)


def is_defect_work_item(issue: Mapping[str, Any]) -> bool:
    return normalized_work_item_kind(issue) in {
        MECHANICAL_DEFECT,
        REVIEW_DEFECT,
        REVIEW_CONCERN,
    }


def is_objective_finding(issue: Mapping[str, Any]) -> bool:
    return normalized_work_item_kind(issue) == MECHANICAL_DEFECT


def is_review_finding(issue: Mapping[str, Any]) -> bool:
    return normalized_work_item_kind(issue) == REVIEW_DEFECT


def is_concern_finding(issue: Mapping[str, Any]) -> bool:
    return normalized_work_item_kind(issue) == REVIEW_CONCERN


def is_review_work_item(issue: Mapping[str, Any]) -> bool:
    return normalized_work_item_kind(issue) in {REVIEW_DEFECT, REVIEW_CONCERN}


def is_triage_finding(issue: Mapping[str, Any]) -> bool:
    return is_review_work_item(issue)


def is_assessment_request(issue: Mapping[str, Any]) -> bool:
    return normalized_work_item_kind(issue) == ASSESSMENT_REQUEST


def is_review_request(issue: Mapping[str, Any]) -> bool:
    return is_assessment_request(issue)


def is_non_objective_issue(issue: Mapping[str, Any]) -> bool:
    return not is_objective_finding(issue)


def counts_toward_objective_backlog(issue: Mapping[str, Any]) -> bool:
    return is_objective_finding(issue)


def is_import_only_issue(issue: Mapping[str, Any]) -> bool:
    return normalized_work_item_origin(issue) == REVIEW_IMPORT_ORIGIN


def is_scoring_excluded_detector(detector: object) -> bool:
    detector_name = str(detector or "").strip()
    return detector_name in SCORING_EXCLUDED_DETECTORS


def _detail_dict(issue: Mapping[str, Any]) -> Mapping[str, Any]:
    detail = issue.get("detail", {})
    return detail if isinstance(detail, Mapping) else {}


__all__ = [
    "ASSESSMENT_REQUEST",
    "CONCERN_FINDING",
    "ISSUE_KINDS",
    "ISSUE_ORIGINS",
    "MECHANICAL_DEFECT",
    "MECHANICAL_FINDING",
    "REVIEW_CONCERN",
    "REVIEW_DEFECT",
    "REVIEW_FINDING",
    "REVIEW_IMPORT_ORIGIN",
    "REVIEW_REQUEST",
    "SCAN_ORIGIN",
    "SCORING_EXCLUDED_DETECTORS",
    "SYNTHETIC_TASK_ORIGIN",
    "SYNTHETIC_REQUEST_ORIGIN",
    "counts_toward_objective_backlog",
    "ensure_work_item_semantics",
    "ensure_issue_semantics",
    "infer_work_item_kind",
    "infer_work_item_origin",
    "infer_issue_kind",
    "infer_issue_origin",
    "is_assessment_request",
    "is_concern_finding",
    "is_defect_work_item",
    "is_import_only_issue",
    "is_non_objective_issue",
    "is_objective_finding",
    "is_review_finding",
    "is_review_request",
    "is_review_work_item",
    "is_scoring_excluded_detector",
    "is_triage_finding",
    "normalized_work_item_kind",
    "normalized_work_item_origin",
    "normalized_issue_kind",
    "normalized_issue_origin",
    "WORK_ITEM_KINDS",
    "WORK_ITEM_ORIGINS",
]
