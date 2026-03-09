"""High-level orchestration for flat-directory detection."""

from __future__ import annotations

from pathlib import Path

from .config import (
    DEFAULT_THIN_WRAPPER_NAMES,
    THIN_WRAPPER_NAMES,
    FlatDirDetectionConfig,
    resolve_detection_settings,
)
from .entries import (
    fragmentation_entry,
    is_overloaded,
    sort_entries,
    thin_wrapper_entry,
)
from .stats import all_tracked_dirs, build_dir_stats


def detect_flat_dirs(
    path: Path,
    file_finder,
    threshold: int = 20,
    *,
    config: FlatDirDetectionConfig | None = None,
    child_dir_threshold: int = 10,
    child_dir_weight: int = 3,
    combined_threshold: int = 30,
    sparse_parent_child_threshold: int = 8,
    sparse_child_file_threshold: int = 1,
    sparse_child_count_threshold: int = 6,
    sparse_child_ratio_threshold: float = 0.7,
    thin_wrapper_parent_sibling_threshold: int = 10,
    thin_wrapper_max_file_count: int = 1,
    thin_wrapper_max_child_dir_count: int = 1,
    thin_wrapper_names: tuple[str, ...] = DEFAULT_THIN_WRAPPER_NAMES,
) -> tuple[list[dict], int]:
    """Find overloaded/fragmented directories using count and fan-out heuristics."""
    settings = resolve_detection_settings(
        threshold=threshold,
        config=config,
        child_dir_threshold=child_dir_threshold,
        child_dir_weight=child_dir_weight,
        combined_threshold=combined_threshold,
        sparse_parent_child_threshold=sparse_parent_child_threshold,
        sparse_child_file_threshold=sparse_child_file_threshold,
        sparse_child_count_threshold=sparse_child_count_threshold,
        sparse_child_ratio_threshold=sparse_child_ratio_threshold,
        thin_wrapper_parent_sibling_threshold=thin_wrapper_parent_sibling_threshold,
        thin_wrapper_max_file_count=thin_wrapper_max_file_count,
        thin_wrapper_max_child_dir_count=thin_wrapper_max_child_dir_count,
        thin_wrapper_names=thin_wrapper_names,
    )
    files = file_finder(path)
    scan_root = path.resolve()
    dir_counts, child_dirs = build_dir_stats(scan_root, files)
    tracked_dirs = all_tracked_dirs(dir_counts, child_dirs)

    thin_names = {name.lower() for name in settings.thin_wrapper_names}
    if not thin_names:
        thin_names = set(THIN_WRAPPER_NAMES)

    entries: list[dict] = []
    for dir_path in sorted(tracked_dirs):
        file_count = int(dir_counts.get(dir_path, 0))
        direct_children = child_dirs.get(dir_path, set())
        direct_child_count = len(direct_children)
        combined_score = file_count + (settings.child_dir_weight * direct_child_count)
        has_local_files = dir_path in dir_counts

        if has_local_files:
            if is_overloaded(
                file_count=file_count,
                direct_child_count=direct_child_count,
                combined_score=combined_score,
                settings=settings,
            ):
                overload_entry: dict[str, str | int] = {}
                overload_entry["directory"] = dir_path
                overload_entry["file_count"] = file_count
                overload_entry["child_dir_count"] = direct_child_count
                overload_entry["combined_score"] = combined_score
                overload_entry["kind"] = "overload"
                entries.append(overload_entry)
                continue
            fragmented = fragmentation_entry(
                dir_path=dir_path,
                file_count=file_count,
                direct_children=direct_children,
                direct_child_count=direct_child_count,
                combined_score=combined_score,
                settings=settings,
                dir_counts=dir_counts,
                child_dirs=child_dirs,
            )
            if fragmented is not None:
                entries.append(fragmented)
                continue

        thin_wrapper = thin_wrapper_entry(
            dir_path=dir_path,
            thin_names=thin_names,
            file_count=file_count,
            direct_child_count=direct_child_count,
            combined_score=combined_score,
            settings=settings,
            child_dirs=child_dirs,
        )
        if thin_wrapper is not None:
            entries.append(thin_wrapper)
    return sort_entries(entries), len(tracked_dirs)


__all__ = ["detect_flat_dirs"]
