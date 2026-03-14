"""Review guidance hooks for R."""

from __future__ import annotations

import re

HOLISTIC_REVIEW_DIMENSIONS: list[str] = [
    "cross_module_architecture",
    "error_consistency",
    "abstraction_fitness",
    "test_strategy",
    "design_coherence",
]

REVIEW_GUIDANCE = {
    "patterns": [
        "Prefer functional programming over mutable state; use vectorized "
        "operations instead of loops where possible.",
        "Use explicit imports (library()) at the top of scripts, not inside "
        "functions.",
        "Prefer testthat conventions: tests/testthat/test-*.R mapping to "
        "R/*.R source files.",
        "Use the pipe operator (%>%) consistently across the codebase — "
        "avoid mixing with nested calls.",
        "Avoid T/F as shorthand for TRUE/FALSE to prevent masking issues.",
        "Use here::here() or similar for project-relative paths instead of "
        "setwd().",
    ],
    "auth": [],
    "naming": (
        "Use snake_case for functions and variables, PascalCase for S3/S4/R6 "
        "class constructors."
    ),
}

MIGRATION_PATTERN_PAIRS: list[tuple[str, object, object]] = []
MIGRATION_MIXED_EXTENSIONS: set[str] = set()
LOW_VALUE_PATTERN = re.compile(
    r"(?m)^\s*(?:library|require|import)\s*\(",
)

_LIBRARY_RE = re.compile(r"(?m)^\s*(?:library|require)\s*\(\s*(\w[\w.]+)")
_FUNCTION_RE = re.compile(r"(?m)^\s*(\w+)\s*<-\s*function\s*\(")
_CLASS_RE = re.compile(
    r"(?m)^\s*\w+\s*<-\s*R6Class\s*\(\s*[\"'](\w+)",
)
_S3_CLASS_RE = re.compile(r"class\s*=\s*[\"'](\w+)[\"']")


def module_patterns(content: str) -> list[str]:
    """Extract library/require names for review context."""
    return [match.group(1) for match in _LIBRARY_RE.finditer(content)]


def api_surface(file_contents: dict[str, str]) -> dict[str, list[str]]:
    """Build minimal API-surface summary from parsed R files."""
    functions: set[str] = set()
    r6_classes: set[str] = set()
    s3_constructors: set[str] = set()

    for content in file_contents.values():
        for match in _FUNCTION_RE.finditer(content):
            name = match.group(1)
            if not name.startswith("_"):
                functions.add(name)
        for match in _CLASS_RE.finditer(content):
            r6_classes.add(match.group(1))
        if _S3_CLASS_RE.search(content):
            for match in _FUNCTION_RE.finditer(content):
                name = match.group(1)
                if not name.startswith("_"):
                    s3_constructors.add(name)

    return {
        "public_functions": sorted(functions),
        "r6_classes": sorted(r6_classes),
        "s3_constructors": sorted(s3_constructors),
    }


__all__ = [
    "HOLISTIC_REVIEW_DIMENSIONS",
    "LOW_VALUE_PATTERN",
    "MIGRATION_MIXED_EXTENSIONS",
    "MIGRATION_PATTERN_PAIRS",
    "REVIEW_GUIDANCE",
    "api_surface",
    "module_patterns",
]
