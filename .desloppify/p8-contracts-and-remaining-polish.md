# P8: Typed Contracts, Data-Driven Concerns, Command Options, and Naming

**Effort**: Medium (4-5 hours)
**Risk**: Low-medium — mostly type annotations, data restructuring, and renaming
**Files touched**: `app/commands/review/batch/core.py`, `engine/_plan/stale_dimensions.py`, `engine/concerns.py`, `app/commands/review/cmd.py`, `app/commands/scan/cmd.py`, `app/commands/show/cmd.py`, `base/text_utils.py`

This workstream handles the remaining polish items that didn't fit in the other workstreams.

---

## P8a: Replace dict-heavy seams with typed contracts (A3)

**The problem**: Critical workflows pass large `dict[str, Any]` payloads across module boundaries. This hides contract drift.

**Focus on the highest-value seams** (don't boil the ocean):

### Review batch normalization/merge payloads

**File**: `app/commands/review/batch/core.py`

1. Read the file. Find functions that receive or return large dicts (especially batch results, normalization outputs, merge inputs).
2. For the most-used dict shapes, define TypedDicts:
   ```python
   class BatchResult(TypedDict):
       batch_id: str
       issues: list[dict[str, Any]]
       status: str
       # ... other fields
   ```
3. Update function signatures to use these types.
4. Don't try to type everything — focus on the 2-3 most-passed dict shapes.

### Review import/merge payloads

**Files**: `app/commands/review/importing/parse.py`, `app/commands/review/merge.py`

Same approach — find the top dict shapes being passed around, define TypedDicts, update signatures.

**Stop if**: You find the dict shapes are genuinely polymorphic (different keys depending on context). In that case, document the shapes in a comment block instead of creating TypedDicts.

---

## P8b: Make concern generators data-driven (Item 8 remainder)

**File**: `desloppify/engine/concerns.py`

The `_try_make_concern()` factory was already extracted. Two things remain:

### Convert `_build_summary()` from if-blocks to lookup table

Current:
```python
if concern_type == "mixed_responsibilities": return "..."
if concern_type == "structural_complexity": return "..."
if concern_type == "duplication_design": return "..."
```

Target:
```python
_SUMMARY_TEMPLATES: dict[str, str] = {
    "mixed_responsibilities": "Multiple detectors flagged {file} ...",
    "structural_complexity": "Complexity signals in {file} ...",
    "duplication_design": "Duplication patterns in {file} ...",
    # ...
}

def _build_summary(concern_type: str, signals: dict) -> str:
    template = _SUMMARY_TEMPLATES.get(concern_type)
    if template:
        return template.format(**signals)
    return f"Design signals from {signals.get('file', 'unknown')}"
```

### Convert `_build_question()` from if-chain to condition list

Current: chain of `if condition: parts.append(...)` blocks.

Target:
```python
_QUESTION_PARTS: list[tuple[Callable[[dict], bool], str]] = [
    (lambda s: len(s.get("detectors", [])) >= MIN_DETECTORS, "Multiple detector types flagged this area..."),
    (lambda s: bool(s.get("funcs")), "Complex functions: {funcs}"),
    (lambda s: s.get("max_params", 0) > 5, "High parameter counts (max {max_params})"),
    # ...
]

def _build_question(concern_type: str, signals: dict) -> str:
    parts = [tmpl.format(**signals) for pred, tmpl in _QUESTION_PARTS if pred(signals)]
    return " ".join(parts) if parts else "What structural improvements would help here?"
```

Read the actual code first — the conditions may be more nuanced than this sketch. Keep the data-driven approach only where it genuinely simplifies the code. If some conditions have complex logic that doesn't reduce to a simple predicate, leave those as explicit if-blocks.

---

## P8c: Expand command options dataclasses (Item 9)

**Files**: `app/commands/review/cmd.py`, `app/commands/scan/cmd.py`, `app/commands/show/cmd.py`

The `NextOptions` pattern was already applied to `next/cmd.py`. Expand to the next 3 worst offenders:

### `review/cmd.py` (~25 getattr calls)

1. Read the file. Find the cluster of getattr calls.
2. Define a frozen dataclass:
   ```python
   @dataclass(frozen=True)
   class ReviewOptions:
       merge: bool = False
       run_batches: bool = False
       import_run_dir: str | None = None
       dry_run: bool = False
       # ... all other options

       @classmethod
       def from_args(cls, args: argparse.Namespace) -> ReviewOptions:
           return cls(
               merge=bool(getattr(args, "merge", False)),
               # ...
           )
   ```
3. Replace all `getattr(args, ...)` calls with `opts.field_name`

### `scan/cmd.py` and `show/cmd.py`

Same pattern. Only do these if they have 5+ getattr calls.

**Don't**: Apply this to every command file. Focus on the 3-4 worst offenders. Commands with <5 getattr calls aren't worth the overhead.

---

## P8d: Rename/split text_utils.py (Item 15)

**File**: `desloppify/base/text_utils.py`

**The problem**: Contains `get_project_root()` (path resolution), `get_area()` (path manipulation), `is_numeric()` (type predicate), `read_code_snippet()` (file I/O), and `strip_c_style_comments()` (text processing). The name says "text" but most is path/I/O work.

**Preferred approach**: Split rather than rename.

1. Read the file. Categorize every function as either:
   - **Path/project**: `get_project_root()`, `get_area()`, `rel()` → belongs in `base/discovery/paths.py` (already exists)
   - **Text/code**: `is_numeric()`, `strip_c_style_comments()`, `read_code_snippet()` → stays in `text_utils.py`

2. Move path functions to `base/discovery/paths.py` using the move tool:
   ```bash
   # Or manually: cut functions from text_utils.py, paste into paths.py, update imports
   ```

3. If `text_utils.py` is left with <30 lines of real code, consider inlining those functions into their single caller rather than keeping a near-empty module.

4. Update all importers:
   ```bash
   grep -rn 'from desloppify.base.text_utils import\|from desloppify.base import text_utils' desloppify/ --include='*.py' | grep -v __pycache__
   ```

5. Run tests.

**Stop if**: `get_project_root()` is imported by 50+ files. In that case, the rename churn isn't worth it — just rename the module to `base/project_utils.py` or `base/code_utils.py` instead of splitting.

---

## Verification

```bash
python -m pytest desloppify/tests/ -q
```
