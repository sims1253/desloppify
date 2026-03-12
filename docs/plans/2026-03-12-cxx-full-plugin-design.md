# C++ Full Plugin Design

**Date:** 2026-03-12

## Goal

Upgrade `desloppify.languages.cxx` from a generic `generic_lang()` wrapper to a first-class full plugin that participates in the same scan, review, planning, and strict-score workflows as the mature `go`, `csharp`, and `python` plugins.

The plugin must deliver C++-specific signals for dead code, duplication, complexity, dependency cycles, naming, abstraction fitness, module boundaries, security, and test coverage. It must treat `compile_commands.json` as the main source of build truth and provide a documented best-effort fallback for `Makefile` projects.

## Context

Today C/C++ is listed as a generic plugin in [desloppify/languages/README.md](C:\Users\Dragoy\.codex\worktrees\edaf\desloppify\desloppify\languages\README.md), and [desloppify/languages/cxx/__init__.py](C:\Users\Dragoy\.codex\worktrees\edaf\desloppify\desloppify\languages\cxx\__init__.py) is a single-file `cppcheck` wrapper with tree-sitter support. The repository already has the full-plugin contract, shared phase builders, tree-sitter specs for C++, and mature examples in `go/`, `csharp/`, and `python/`.

This design keeps the existing hybrid philosophy:

- `compile_commands.json` owns project structure when present.
- Tree-sitter provides structural extraction and shared AST-backed signals.
- External tools such as `cppcheck` and `clang-tidy` can corroborate C++-specific findings, especially in security and diagnostics-heavy areas.

## Chosen Approach

Implement a hybrid full plugin for C++.

This is a deliberate middle path:

- It is stronger than incrementally growing the current generic wrapper, which would keep generic constraints in the long-term shape.
- It is lower-risk than a clang-first architecture that would make the plugin depend on a heavier runtime and more fragile toolchain assumptions.

The hybrid plugin uses `compile_commands.json` for dependency truth, tree-sitter for extractors and shared AST analysis, and external tools where they add value without becoming the only analysis engine.

## Architecture

Create a full plugin package under `desloppify/languages/cxx/` with the same contract used by the existing first-class languages:

- `__init__.py`
  Register `CxxConfig(LangConfig)` through `register_full_plugin(...)`.
- `commands.py`
  Expose C++ detect commands and runtime options.
- `extractors.py`
  Discover C++ files and extract functions, classes, methods, namespaces, and include edges.
- `phases.py`
  Assemble the C++ detector pipeline.
- `review.py`
  Provide language-specific review guidance, API-surface summaries, module patterns, and holistic dimensions.
- `test_coverage.py`
  Map production files to tests using naming conventions, includes, and project layout.
- `move.py`
  Support move/refactor workflows expected from full plugins.
- `detectors/`
  Hold dependency and security-specific logic.
- `fixers/`
  Start with the contract surface even if fixers remain minimal in the first pass.
- `review_data/`
  Hold C++ review-dimension overrides and guidance payloads.
- `tests/`
  Colocated language-specific tests.

## Signal Model

### Dependency Graph And Cycles

Use `compile_commands.json` as the main dependency source for CMake-based repositories. The plugin should read translation units, include directories, and relevant compile flags, then construct a project-local include graph suitable for cycle, orphaned, and boundary analysis.

For `Makefile` projects, provide a weaker but still useful fallback:

- detect files from `Makefile`-style layouts and configured markers,
- parse local `#include` directives,
- resolve project-local headers heuristically,
- document that generated headers, macro-heavy branches, and variant-specific build flags may reduce accuracy.

### Dead Code, Orphans, And Single-Use Abstractions

Derive actionability from the C++ dependency graph rather than generic heuristics alone. This allows the plugin to identify:

- unreachable translation units,
- orphaned headers or sources,
- single-use wrappers and thin abstractions,
- suspicious module islands with weak inbound usage.

### Duplication, Complexity, Large Units, And God Classes

Run an explicit C++ `phase_structural` with language-tuned thresholds and signals. Tree-sitter remains the structural backbone, but thresholds, presentation, and corroboration must be tailored for C++ idioms such as nested control flow, macro-adjacent complexity, large headers, and multi-method classes.

### Security

Security should be a full-plugin phase, not just generic tool output. The recommended model is a wrapper that normalizes `clang-tidy` and `cppcheck` findings into the shared security pipeline, with confidence gating to avoid noisy strict-score regressions.

### Subjective Review

The review layer must understand C++ conventions, including:

- naming consistency across namespaces, classes, methods, and constants,
- header/source separation hygiene,
- ownership-model coherence (`raw` vs smart pointers),
- module and namespace boundaries,
- abstraction fitness and API-surface design,
- migration smells such as mixed ownership conventions or legacy macro-driven patterns.

All findings must remain compatible with existing scoring concepts such as confidence, actionability, corroboration, and strict-score visibility.

## Delivery Shape

Ship this as a single epic with explicit deliverables instead of a vague “support C++” effort.

### Required Deliverables

- Convert `desloppify.languages.cxx` from generic-only registration to `register_full_plugin(...)`.
- Add C++-specific modules for commands, extractors, phases, review, test coverage, move support, detectors, fixers, and tests.
- Build a dependency engine with a `compile_commands.json` primary path and documented `Makefile` fallback.
- Wire full phase ordering: structural, coupling/cycles/orphaned, tree-sitter phases, signature, test coverage, security, and subjective duplicate tail.
- Add review guidance, module patterns, API-surface summaries, and holistic review dimensions for C++.
- Update docs to move C++ from the generic tier to the full-plugin tier.

### Main Risks

- `compile_commands.json` may not reflect every generated-header or multi-config build permutation.
- `Makefile` fallback must remain explicitly weaker than the compile-database path.
- C++ conventions vary heavily between codebases, so review guidance must be helpful without being over-opinionated.
- Security-tool normalization can generate strict-score noise if confidence gating is too loose.

## Definition Of Done

The work is complete when all of the following are true:

- C++ is no longer a generic-only plugin.
- `scan`, `next`, `plan`, `status`, `review`, and strict-score flows treat C++ as a full plugin.
- For CMake repositories, the plugin can surface dead code, duplication, complexity, dependency cycles, security findings, naming/abstraction/module-boundary review, and test-coverage hooks.
- For `Makefile` repositories, the plugin provides documented best-effort dependency support without claiming parity with compile-database analysis.
- The plugin has colocated language tests and passes the shared plugin contract/layout checks.
- Documentation clearly states supported build paths, limits, and expected behavior.

## Non-Goals For The First Pass

The first pass does not attempt to provide equal support for Bazel, Meson, or other build systems. It also does not require a libclang-native AST or a full set of mature auto-fixers on day one, as long as the full-plugin contract is present and the scoring behavior is correct.
