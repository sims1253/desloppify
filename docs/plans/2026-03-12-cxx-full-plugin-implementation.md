# C++ Full Plugin Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade `desloppify.languages.cxx` from a generic plugin to a full C++ plugin with compile-database-aware dependency analysis, C++ review guidance, security/test-coverage hooks, and strict-score-compatible signals.

**Architecture:** Replace the single-file `generic_lang()` registration with a `LangConfig`-based full plugin modeled after `go` and `csharp`. Use `compile_commands.json` as the primary dependency source, tree-sitter for extractors and shared AST phases, and normalized external-tool output for corroboration and security.

**Tech Stack:** Python, `LangConfig` full-plugin contract, tree-sitter C++ spec, compile database parsing, `cppcheck`, `clang-tidy`, pytest.

---

### Task 1: Convert `cxx` Into A Full Plugin Package

**Files:**
- Modify: `desloppify/languages/cxx/__init__.py`
- Create: `desloppify/languages/cxx/commands.py`
- Create: `desloppify/languages/cxx/extractors.py`
- Create: `desloppify/languages/cxx/phases.py`
- Create: `desloppify/languages/cxx/review.py`
- Create: `desloppify/languages/cxx/test_coverage.py`
- Create: `desloppify/languages/cxx/move.py`
- Create: `desloppify/languages/cxx/_helpers.py`
- Create: `desloppify/languages/cxx/_zones.py`
- Create: `desloppify/languages/cxx/detectors/__init__.py`
- Create: `desloppify/languages/cxx/fixers/__init__.py`
- Create: `desloppify/languages/cxx/review_data/__init__.py`
- Create: `desloppify/languages/cxx/review_data/dimensions.override.json`
- Create: `desloppify/languages/cxx/tests/__init__.py`
- Test: `desloppify/languages/cxx/tests/test_init.py`
- Test: `desloppify/tests/lang/common/test_lang_structure_validation.py`

**Step 1: Write the failing contract test**

```python
from desloppify.languages.cxx import CxxConfig


def test_cxx_uses_full_plugin_config():
    cfg = CxxConfig()
    assert cfg.name == "cxx"
    assert callable(cfg.build_dep_graph)
    assert callable(cfg.extract_functions)
    assert cfg.review_guidance
```

**Step 2: Run test to verify it fails**

Run: `pytest -q desloppify/languages/cxx/tests/test_init.py -k full_plugin`
Expected: FAIL because `CxxConfig` does not exist yet.

**Step 3: Write minimal implementation**

```python
class CxxConfig(LangConfig):
    def __init__(self):
        super().__init__(
            name="cxx",
            extensions=[".c", ".cc", ".cpp", ".cxx", ".h", ".hpp"],
            phases=[...],
            build_dep_graph=build_cxx_dep_graph,
            extract_functions=extract_all_cxx_functions,
            review_guidance=CXX_REVIEW_GUIDANCE,
        )
```

**Step 4: Run tests to verify the contract passes**

Run: `pytest -q desloppify/languages/cxx/tests/test_init.py desloppify/tests/lang/common/test_lang_structure_validation.py`
Expected: PASS for the new config and plugin layout.

**Step 5: Commit**

```bash
git add desloppify/languages/cxx
git commit -m "feat: scaffold full C++ plugin package"
```

### Task 2: Add File Discovery, Extractors, And Structural Signals

**Files:**
- Modify: `desloppify/languages/cxx/extractors.py`
- Modify: `desloppify/languages/cxx/phases.py`
- Modify: `desloppify/languages/cxx/_helpers.py`
- Test: `desloppify/languages/cxx/tests/test_extractors.py`
- Test: `desloppify/languages/cxx/tests/test_structural.py`

**Step 1: Write failing extractor and complexity tests**

```python
def test_extract_cxx_functions_and_classes(tmp_path):
    source = tmp_path / "widget.cpp"
    source.write_text("class Widget { void run(); }; void helper() {}")
    functions = extract_all_cxx_functions([str(source)])
    assert any(f.name == "helper" for f in functions)


def test_phase_structural_flags_large_or_complex_cxx_file(tmp_path):
    issues, complexity = phase_structural(tmp_path, fake_cxx_lang())
    assert isinstance(issues, list)
    assert isinstance(complexity, dict)
```

**Step 2: Run the tests to verify they fail**

Run: `pytest -q desloppify/languages/cxx/tests/test_extractors.py desloppify/languages/cxx/tests/test_structural.py`
Expected: FAIL because extractors and phase wiring are missing.

**Step 3: Implement minimal extractor and structural phase**

```python
def extract_all_cxx_functions(files: list[str]) -> list[FunctionInfo]:
    return extract_functions_with_treesitter(files, "cpp")


def phase_structural(path: Path, lang: LangRuntimeContract):
    return run_structural_phase(path, lang, complexity_signals=CXX_COMPLEXITY_SIGNALS, log_fn=log)
```

**Step 4: Run the tests to verify they pass**

Run: `pytest -q desloppify/languages/cxx/tests/test_extractors.py desloppify/languages/cxx/tests/test_structural.py`
Expected: PASS, with language-specific thresholds and extractors wired.

**Step 5: Commit**

```bash
git add desloppify/languages/cxx
git commit -m "feat: add C++ extractors and structural phase"
```

### Task 3: Build Compile-Database-Aware Dependency Analysis

**Files:**
- Create: `desloppify/languages/cxx/detectors/deps.py`
- Modify: `desloppify/languages/cxx/_helpers.py`
- Modify: `desloppify/languages/cxx/phases.py`
- Test: `desloppify/languages/cxx/tests/test_deps.py`
- Test: `desloppify/languages/cxx/tests/test_compile_commands.py`

**Step 1: Write failing dependency tests for both paths**

```python
def test_build_dep_graph_from_compile_commands(tmp_path):
    graph = build_cxx_dep_graph(tmp_path)
    assert "src/main.cpp" in graph


def test_build_dep_graph_falls_back_to_makefile_include_scan(tmp_path):
    graph = build_cxx_dep_graph(tmp_path)
    assert graph
```

**Step 2: Run tests to verify they fail**

Run: `pytest -q desloppify/languages/cxx/tests/test_deps.py desloppify/languages/cxx/tests/test_compile_commands.py`
Expected: FAIL because no C++ dep-graph builder exists.

**Step 3: Implement the primary and fallback graph builders**

```python
def build_cxx_dep_graph(path: Path) -> dict[str, set[str]]:
    if (path / "compile_commands.json").exists():
        return build_from_compile_commands(path)
    return build_from_local_includes(path)
```

**Step 4: Run the tests to verify they pass**

Run: `pytest -q desloppify/languages/cxx/tests/test_deps.py desloppify/languages/cxx/tests/test_compile_commands.py`
Expected: PASS, including cycle/orphan-ready graph output.

**Step 5: Commit**

```bash
git add desloppify/languages/cxx
git commit -m "feat: add C++ dependency graph analysis"
```

### Task 4: Add Review Guidance And Scoring Hooks

**Files:**
- Modify: `desloppify/languages/cxx/review.py`
- Modify: `desloppify/languages/cxx/review_data/dimensions.override.json`
- Modify: `desloppify/languages/cxx/__init__.py`
- Test: `desloppify/languages/cxx/tests/test_review.py`

**Step 1: Write the failing review tests**

```python
def test_cxx_review_guidance_mentions_namespaces_and_ownership():
    assert "ownership" in CXX_REVIEW_GUIDANCE["patterns"][0].lower()


def test_cxx_api_surface_summarizes_public_types():
    summary = api_surface({"widget.hpp": "class Widget { public: void Run(); };"})
    assert "public_types" in summary
```

**Step 2: Run the tests to verify they fail**

Run: `pytest -q desloppify/languages/cxx/tests/test_review.py`
Expected: FAIL because C++ review guidance is not implemented.

**Step 3: Implement C++-specific review hooks**

```python
HOLISTIC_REVIEW_DIMENSIONS = [
    "cross_module_architecture",
    "abstraction_fitness",
    "api_surface_coherence",
    "design_coherence",
]
```

Add guidance for namespace hygiene, header/source separation, ownership coherence, and module boundaries.

**Step 4: Run the tests to verify they pass**

Run: `pytest -q desloppify/languages/cxx/tests/test_review.py`
Expected: PASS, with C++ guidance exposed through the full plugin config.

**Step 5: Commit**

```bash
git add desloppify/languages/cxx
git commit -m "feat: add C++ review guidance and scoring hooks"
```

### Task 5: Add Test Coverage Mapping And Security Integration

**Files:**
- Modify: `desloppify/languages/cxx/test_coverage.py`
- Create: `desloppify/languages/cxx/detectors/security.py`
- Modify: `desloppify/languages/cxx/__init__.py`
- Test: `desloppify/languages/cxx/tests/test_coverage.py`
- Test: `desloppify/languages/cxx/tests/test_security.py`

**Step 1: Write failing coverage and security tests**

```python
def test_map_cpp_test_to_source_by_convention():
    assert map_test_to_source("tests/widget_test.cpp", {"src/widget.cpp"}) == "src/widget.cpp"


def test_detect_cxx_security_normalizes_tool_findings(tmp_path):
    result = detect_cxx_security([], {})
    assert hasattr(result, "entries")
```

**Step 2: Run the tests to verify they fail**

Run: `pytest -q desloppify/languages/cxx/tests/test_coverage.py desloppify/languages/cxx/tests/test_security.py`
Expected: FAIL because coverage hooks and security adapter do not exist.

**Step 3: Implement the minimal working hooks**

```python
def map_test_to_source(test_path: str, production_set: set[str]) -> str | None:
    return by_basename_or_stem(test_path, production_set, suffixes=("_test", "_spec", "Test"))


def detect_cxx_security(files, zone_map):
    return run_cxx_security_tools(files, zone_map, tools=("clang-tidy", "cppcheck"))
```

**Step 4: Run the tests to verify they pass**

Run: `pytest -q desloppify/languages/cxx/tests/test_coverage.py desloppify/languages/cxx/tests/test_security.py`
Expected: PASS with normalized coverage and security outputs.

**Step 5: Commit**

```bash
git add desloppify/languages/cxx
git commit -m "feat: add C++ test coverage and security hooks"
```

### Task 6: Add Detect Commands, Move Support, And Minimal Fixer Surface

**Files:**
- Modify: `desloppify/languages/cxx/commands.py`
- Modify: `desloppify/languages/cxx/move.py`
- Modify: `desloppify/languages/cxx/fixers/__init__.py`
- Test: `desloppify/languages/cxx/tests/test_commands.py`
- Test: `desloppify/languages/cxx/tests/test_move.py`

**Step 1: Write failing CLI-surface tests**

```python
def test_cxx_detect_commands_are_registered():
    cmds = get_detect_commands()
    assert any(cmd["id"] == "clang_tidy" for cmd in cmds)


def test_cxx_move_module_exposes_contract():
    assert hasattr(cxx_move, "can_move")
```

**Step 2: Run the tests to verify they fail**

Run: `pytest -q desloppify/languages/cxx/tests/test_commands.py desloppify/languages/cxx/tests/test_move.py`
Expected: FAIL because the command and move surfaces are incomplete.

**Step 3: Implement the minimal contract-complete modules**

```python
def get_detect_commands() -> list[dict]:
    return [{"id": "clang_tidy", "label": "clang-tidy"}, {"id": "cppcheck", "label": "cppcheck"}]
```

```python
def can_move(_path: str) -> bool:
    return False
```

**Step 4: Run the tests to verify they pass**

Run: `pytest -q desloppify/languages/cxx/tests/test_commands.py desloppify/languages/cxx/tests/test_move.py`
Expected: PASS with full-plugin contract coverage in place.

**Step 5: Commit**

```bash
git add desloppify/languages/cxx
git commit -m "feat: add C++ command and move surfaces"
```

### Task 7: Update Docs And Validate End-To-End Behavior

**Files:**
- Modify: `desloppify/languages/README.md`
- Modify: `README.md`
- Test: `desloppify/languages/cxx/tests/test_smoke.py`
- Test: `desloppify/tests/lang/common/test_lang_test_layout.py`
- Test: `desloppify/tests/lang/common/test_lang_structure_validation.py`

**Step 1: Write a failing smoke test and doc expectation test**

```python
def test_cxx_plugin_smoke_registration():
    cfg = CxxConfig()
    assert cfg.default_scan_profile in {"objective", "full"}
```

Add a doc assertion that C++ is no longer described as generic-only.

**Step 2: Run the tests to verify they fail**

Run: `pytest -q desloppify/languages/cxx/tests/test_smoke.py desloppify/tests/lang/common/test_lang_test_layout.py`
Expected: FAIL until the docs and plugin metadata are updated.

**Step 3: Update docs and metadata**

Move C++ into the full-plugin table in `desloppify/languages/README.md` and document:

- `compile_commands.json` primary path,
- `Makefile` best-effort fallback,
- current limits and expected behavior.

**Step 4: Run the full relevant verification**

Run: `pytest -q desloppify/languages/cxx/tests/ desloppify/tests/lang/common/`
Expected: PASS for C++ language tests and shared plugin-contract checks.

Then run:

Run: `pytest -q`
Expected: PASS or only pre-existing unrelated failures.

**Step 5: Commit**

```bash
git add desloppify/languages/cxx desloppify/languages/README.md README.md
git commit -m "feat: promote C++ to full plugin support"
```

### Task 8: Manual Validation On Representative Fixtures

**Files:**
- Create: `desloppify/languages/cxx/tests/fixtures/cmake_sample/...`
- Create: `desloppify/languages/cxx/tests/fixtures/makefile_sample/...`
- Test: `desloppify/languages/cxx/tests/test_end_to_end.py`

**Step 1: Write failing end-to-end fixture tests**

```python
def test_cmake_fixture_produces_dep_graph_and_cycles():
    result = run_scan_fixture("cmake_sample")
    assert result.dep_graph


def test_makefile_fixture_uses_best_effort_fallback():
    result = run_scan_fixture("makefile_sample")
    assert result.dep_graph
```

**Step 2: Run the tests to verify they fail**

Run: `pytest -q desloppify/languages/cxx/tests/test_end_to_end.py`
Expected: FAIL until representative fixtures exist.

**Step 3: Add fixtures and make assertions realistic**

Create two tiny fixtures:

- one CMake fixture with `compile_commands.json` and a simple include cycle,
- one `Makefile` fixture with local headers and no compile database.

**Step 4: Run the tests to verify they pass**

Run: `pytest -q desloppify/languages/cxx/tests/test_end_to_end.py`
Expected: PASS, proving both supported paths work as designed.

**Step 5: Commit**

```bash
git add desloppify/languages/cxx/tests
git commit -m "test: add end-to-end C++ plugin fixtures"
```

## Final Verification Checklist

Run each command and confirm the expected outcome before declaring success:

- `pytest -q desloppify/languages/cxx/tests/`
  Expected: PASS
- `pytest -q desloppify/tests/lang/common/`
  Expected: PASS
- `pytest -q`
  Expected: PASS or only unrelated pre-existing failures
- `python -m desloppify.cli scan --path <cmake_fixture>`
  Expected: C++ plugin loads and produces first-class findings
- `python -m desloppify.cli scan --path <makefile_fixture>`
  Expected: Best-effort C++ analysis without compile-database-only assumptions

## Notes For The Implementer

- Keep `compile_commands.json` as the truth source whenever it exists. Do not let the fallback path silently override it.
- Make the `Makefile` path explicitly weaker in both code and docs.
- Reuse shared framework helpers before adding new cross-language abstractions.
- Prefer TDD and keep commits small and topical.
