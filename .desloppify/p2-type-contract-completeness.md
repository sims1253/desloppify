# P2: Type Contract Completeness

**Effort**: Medium (3-5 hours total)
**Risk**: Very low — pure type annotations, zero runtime behavior changes
**Files touched**: `engine/_state/schema.py`, `engine/_plan/schema.py`, `engine/_work_queue/*.py`, `intelligence/narrative/core.py`

This workstream makes the three most important data structures in the codebase explicitly typed: state, plan, and work queue items. Currently they're folklore — you have to grep `.get()` calls across dozens of files to understand their shape.

---

## P2a: Complete StateModel TypedDict

**File**: `desloppify/engine/_state/schema.py`

`StateModel` currently lists ~16 fields, but code throughout the system accesses fields that aren't declared:

1. **Find all missing fields:**
   ```bash
   grep -rn 'state\["' desloppify/ --include='*.py' | grep -v __pycache__ | grep -v tests/ | sed 's/.*state\["\([^"]*\)".*/\1/' | sort -u
   ```
   Compare this list against the fields in the `StateModel` TypedDict.

2. **For each missing field**, determine its type by reading where it's set (usually in `engine/_state/schema.py` `empty_state()` or `ensure_state_defaults()`, or in merge/persistence code).

3. **Add the field** to `StateModel` with the correct type. Use `NotRequired[T]` for fields that may not be present on old state files. Use `T | None` for fields that are explicitly nullable.

4. Fields likely missing (verify against actual code):
   - `scan_path`, `tool_hash`, `scan_completeness`
   - `potentials`, `codebase_metrics`
   - Any fields added by v0.9.0 refactoring

---

## P2b: Complete PlanModel TypedDict

**File**: `desloppify/engine/_plan/schema.py`

Same approach as StateModel:

1. **Find all missing fields:**
   ```bash
   grep -rn 'plan\["' desloppify/ --include='*.py' | grep -v __pycache__ | grep -v tests/ | sed 's/.*plan\["\([^"]*\)".*/\1/' | sort -u
   ```
2. Compare against current `PlanModel` fields
3. Add missing fields with correct types

---

## P2c: Create WorkQueueItem TypedDict

**Files**: `desloppify/engine/_work_queue/` (new type in a types module, plus signature updates)

Work queue items are the most-accessed untyped data structure — ~58 distinct keys across ~150+ `.get()` calls.

1. **Collect all keys:**
   ```bash
   grep -rn '\.get("' desloppify/engine/_work_queue/ --include='*.py' | grep -v __pycache__ | sed 's/.*\.get("\([^"]*\)".*/\1/' | sort -u
   ```
   Also check `item["key"]` bracket access patterns.

2. **Define the TypedDict** — put it in `engine/_work_queue/types.py` (or at the top of `core.py`):
   ```python
   class WorkQueueItem(TypedDict, total=False):
       id: str
       detector: str
       file: str
       tier: int
       confidence: str
       summary: str
       # ... all other fields
   ```
   Use `total=False` since most fields are optional depending on item type.

3. **Update function signatures** in `_work_queue/`:
   - `build_issue_items() -> list[WorkQueueItem]`
   - `build_subjective_items() -> list[WorkQueueItem]`
   - `item_sort_key(item: WorkQueueItem) -> ...`
   - `_apply_plan_order(items: list[WorkQueueItem], ...) -> ...`
   - Any other functions that accept or return queue items

4. Optionally define `ClusterItem(TypedDict)` for cluster-specific shapes if there's a clear boundary.

---

## P2d: Make NarrativeContext required fields explicit

**File**: `desloppify/intelligence/narrative/core.py`

`NarrativeContext` declares all fields as `Optional` with `None` defaults, but several are de facto required.

1. Read the class and identify which fields are actually always passed by callers
2. Read `compute_narrative()` to see which fields cause silent partial output when `None`
3. Split into required and optional:
   ```python
   @dataclass
   class NarrativeContext:
       # Required — compute_narrative fails without these
       state: dict[str, Any]
       history: list[dict[str, Any]]
       lang: str
       # Optional — enhance output but have sensible defaults
       plan: dict[str, Any] | None = None
       config_overrides: dict[str, Any] | None = None
   ```
4. Update callers if any were passing `None` for required fields (they shouldn't be)

---

## Verification

```bash
python -m pytest desloppify/tests/ -q
# Also run mypy/pyright if available to verify type annotations catch real issues
```
