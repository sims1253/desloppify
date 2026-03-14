"""Review guidance hooks for R.

Patterns and dimensions informed by Posit/posit-dev skills:
- critical-code-reviewer: R red flags and adversarial review patterns
- cran-extrachecks: CRAN submission readiness
- testing-r-packages: testthat best practices
- lifecycle: API evolution and deprecation conventions
"""

from __future__ import annotations

import re

HOLISTIC_REVIEW_DIMENSIONS: list[str] = [
    "cross_module_architecture",
    "error_consistency",
    "abstraction_fitness",
    "convention_outlier",
    "cran_readiness",
    "test_strategy",
    "api_lifecycle_health",
    "design_coherence",
    "vectorization_discipline",
    "package_organization",
]

REVIEW_GUIDANCE = {
    "patterns": [
        # --- Functional style & vectorization ---
        "Prefer functional programming over mutable state; use vectorized "
        "operations instead of loops where possible.",
        "Flag explicit for/while loops where a vectorized equivalent exists "
        "(e.g. sapply/vapply/lapply instead of for with append).",
        "Check for vectorized conditions in if() statements — "
        "if (x > 0) where x is a vector produces a warning and only "
        "checks the first element. Use ifelse() or any()/all().",
        # --- Imports & dependencies ---
        "Use explicit imports (library()) at the top of scripts, not inside "
        "functions.",
        "Flag partial argument matching — foo(len = 10) works but is "
        "fragrant; always use full argument names.",
        # --- Style consistency ---
        "Avoid T/F as shorthand for TRUE/FALSE to prevent masking issues "
        "if a variable named T or F exists in scope.",
        "Use the pipe operator consistently — avoid mixing %>%, |>, and "
        "nested calls in the same codebase.",
        "Flag unnecessary return() at the end of functions — R functions "
        "return the last expression automatically.",
        "Prefer early returns over deep nesting — reduce indent levels by "
        "guarding preconditions at the top of functions.",
        "Use here::here() or similar for project-relative paths instead of "
        "setwd().",
        # --- CRAN readiness ---
        "Check that all exported functions have @return and @examples in "
        "roxygen2 documentation.",
        "Verify DESCRIPTION Title uses title case, has no redundant phrases "
        "(\"A Toolkit for\", \"for R\"), and is under 65 characters.",
        "Verify DESCRIPTION Description does not start with \"This package\" "
        "or \"Functions for\", is 3-4 sentences, and expands acronyms.",
        "Check that all URLs use https:// and do not redirect.",
        "Verify Authors@R includes a copyright holder with [cph] role.",
        # --- Lifecycle ---
        "Check that deprecated functions have lifecycle::badge(\"deprecated\") "
        "and call lifecycle::deprecate_warn() or deprecate_stop().",
        "Verify experimental functions signal their stage with "
        "lifecycle::signal_stage(\"experimental\", ...).",
        # --- Testing ---
        "Prefer testthat conventions: tests/testthat/test-*.R mapping to "
        "R/*.R source files.",
        "Tests should be self-sufficient — each test_that() should contain "
        "its own setup, not rely on ambient state from earlier tests.",
        "Flag use of deprecated testthat patterns: context(), "
        "expect_equivalent(), with_mock() — use describe(), "
        "expect_equal(), local_mocked_bindings() instead.",
        "Check that tests using side effects (file writes, options, env vars) "
        "use withr::local_*() for cleanup.",
        "Verify tests requiring suggested packages guard with "
        "@examplesIf or if (rlang::is_installed(...)).",
    ],
    "auth": [],
    "naming": (
        "Use snake_case for functions and variables, PascalCase for S3/S4/R6 "
        "class constructors."
    ),
}

MIGRATION_PATTERN_PAIRS: list[tuple[str, object, object]] = [
    (
        "base pipe→native pipe",
        re.compile(r"\|>\s*"),
        re.compile(r"\|\s*>"),
    ),
    ("T/F→TRUE/FALSE", re.compile(r"\b(?:^|[^.\w])([TF])(?:$|[^.\w])"), re.compile(r"\bTRUE\b|\bFALSE\b")),
]

MIGRATION_MIXED_EXTENSIONS: set[str] = set()
LOW_VALUE_PATTERN = re.compile(
    r"(?m)^\s*(?:library|require|import)\s*\(",
)

# --- Detection regexes ---

_LIBRARY_RE = re.compile(r"(?m)^\s*(?:library|require)\s*\(\s*([\w.]+)")
_FUNCTION_RE = re.compile(r"(?m)^\s*(\w+)\s*<-\s*function\s*\(")
_CLASS_RE = re.compile(
    r"(?m)^\s*\w+\s*<-\s*R6Class\s*\(\s*[\"'](\w+)",
)
_S3_CLASS_RE = re.compile(r"class\s*=\s*[\"'](\w+)[\"']")
_ROXYGEN_RETURN_RE = re.compile(r"#'\s*@return\b")
_ROXYGEN_EXAMPLES_RE = re.compile(r"#'\s*@examples\b")
_ROXYGEN_EXPORT_RE = re.compile(r"#'\s*@export\b")
_T_F_LITERAL_RE = re.compile(r"(?<!\w)([TF])(?!\w)")
_PARTIAL_ARG_RE = re.compile(r"\(\s*\w+\s*=\s*")
_VECTOR_IF_RE = re.compile(r"\bif\s*\(\s*\w+\s*[><=!]")
_EARLY_RETURN_RE = re.compile(r"\breturn\s*\(")
_EXPLICIT_RETURN_RE = re.compile(r"^\s*return\(\s*\w+\s*\)\s*$", re.MULTILINE)
_DEPRECATED_LIFECYCLE_RE = re.compile(r"lifecycle::deprecate_(?:soft|warn|stop)")
_EXPERIMENTAL_LIFECYCLE_RE = re.compile(r"lifecycle::signal_stage\(\s*[\"']experimental")
_LIFECYCLE_BADGE_RE = re.compile(r"lifecycle::badge\(\s*[\"']")
_LIBRARY_INSIDE_FN_RE = re.compile(
    r"(?:library|require)\s*\(",
)
_USE_NESTED_CALL_RE = re.compile(r"\)\s*\(")


def module_patterns(content: str) -> list[str]:
    """Extract R-specific module convention markers for review context."""
    out: list[str] = []
    for match in _LIBRARY_RE.finditer(content):
        out.append(f"import:{match.group(1)}")
    if _ROXYGEN_EXPORT_RE.search(content):
        out.append("has_exports")
    if _ROXYGEN_RETURN_RE.search(content) and _ROXYGEN_EXPORT_RE.search(content):
        out.append("has_documented_returns")
    if _DEPRECATED_LIFECYCLE_RE.search(content):
        out.append("has_deprecations")
    if _LIFECYCLE_BADGE_RE.search(content):
        out.append("has_lifecycle_badges")
    return out


def api_surface(file_contents: dict[str, str]) -> dict[str, list[str]]:
    """Build API-surface summary from parsed R files.

    Includes functions, classes, documentation coverage, and lifecycle signals.
    """
    functions: set[str] = set()
    r6_classes: set[str] = set()
    s3_constructors: set[str] = set()
    exported_missing_return: list[str] = []
    exported_missing_examples: list[str] = []
    deprecated_functions: list[str] = []
    experimental_functions: list[str] = []
    uses_t_f: list[str] = []
    library_inside_function: list[str] = []
    unnecessary_return: list[str] = []

    for path, content in file_contents.items():
        lines = content.splitlines()
        current_fn: str | None = None
        inside_fn = False
        fn_start_line = 0
        in_roxygen = False
        has_return_doc = False
        has_examples_doc = False
        is_exported = False
        is_deprecated = False

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Track roxygen block state
            if stripped.startswith("#'"):
                in_roxygen = True
                if _ROXYGEN_RETURN_RE.search(stripped):
                    has_return_doc = True
                if _ROXYGEN_EXAMPLES_RE.search(stripped):
                    has_examples_doc = True
                if _ROXYGEN_EXPORT_RE.search(stripped):
                    is_exported = True
                if _DEPRECATED_LIFECYCLE_RE.search(stripped):
                    is_deprecated = True
                if _EXPERIMENTAL_LIFECYCLE_RE.search(stripped):
                    is_deprecated = False
                continue
            else:
                if in_roxygen:
                    in_roxygen = False

            # Detect function definition
            fn_match = _FUNCTION_RE.match(stripped)
            if fn_match:
                name = fn_match.group(1)
                current_fn = name
                fn_start_line = i
                inside_fn = True

                if not name.startswith("_"):
                    functions.add(name)

                # Check documentation for previous exported function
                if is_exported and current_fn is not None:
                    if not has_return_doc:
                        exported_missing_return.append(f"{path}:{fn_start_line}")
                    if not has_examples_doc:
                        exported_missing_examples.append(f"{path}:{fn_start_line}")
                    if is_deprecated:
                        deprecated_functions.append(name)

                # Reset doc tracking for this function
                has_return_doc = False
                has_examples_doc = False
                is_exported = False
                is_deprecated = False

                # Check for library() calls inside functions (only after first def)
                if current_fn is not None and _LIBRARY_INSIDE_FN_RE.search(stripped):
                    library_inside_function.append(f"{path}:{i}:{name}")

                continue

            # Inside a function body — detect patterns
            if inside_fn and current_fn:
                # Library/require inside function
                if _LIBRARY_INSIDE_FN_RE.search(stripped) and not stripped.startswith("#"):
                    if f"{path}:{i}:{current_fn}" not in library_inside_function:
                        library_inside_function.append(f"{path}:{i}:{current_fn}")

                # Unnecessary trailing return()
                if _EXPLICIT_RETURN_RE.match(stripped) and i == len(lines) - 1:
                    unnecessary_return.append(f"{path}:{i}:{current_fn}")

        # R6 class detection
        for match in _CLASS_RE.finditer(content):
            r6_classes.add(match.group(1))

        # S3 class detection
        if _S3_CLASS_RE.search(content):
            for match in _FUNCTION_RE.finditer(content):
                name = match.group(1)
                if not name.startswith("_"):
                    s3_constructors.add(name)

        # Detect T/F usage (excluding strings and comments)
        for i, line in enumerate(lines):
            if line.strip().startswith("#"):
                continue
            for m in _T_F_LITERAL_RE.finditer(line):
                char = m.group(1)
                pos = m.start()
                # Avoid matching inside strings (rough heuristic)
                quote_count = line[:pos].count('"') + line[:pos].count("'")
                if quote_count % 2 == 0:
                    uses_t_f.append(f"{path}:{i}")

    return {
        "public_functions": sorted(functions),
        "r6_classes": sorted(r6_classes),
        "s3_constructors": sorted(s3_constructors),
        "exported_missing_return": sorted(exported_missing_return),
        "exported_missing_examples": sorted(exported_missing_examples),
        "deprecated_functions": sorted(deprecated_functions),
        "uses_t_f_literal": sorted(set(uses_t_f)),
        "library_inside_function": sorted(set(library_inside_function)),
        "unnecessary_trailing_return": sorted(unnecessary_return),
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
