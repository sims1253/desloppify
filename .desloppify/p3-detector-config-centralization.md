# P3: Detector Config Centralization & Private Import Cleanup

**Effort**: Medium (3-4 hours total)
**Risk**: Low-medium — changes registry data structure and import paths
**Files touched**: `base/registry.py`, `engine/_scoring/policy/core.py`, `engine/_state/merge.py`, `state.py`, `app/cli_support/parser.py`, scattered importers

---

## P3a: Centralize per-detector configuration in DetectorMeta

**Primary file**: `desloppify/base/registry.py`
**Secondary files**: `engine/_scoring/policy/core.py`, `engine/_state/merge.py`

**The problem**: Understanding what a single detector does requires reading 4-5 files. If you rename or remove a detector, you must update all of them manually.

**Step 1: Understand current scatter**

Read these files to map the per-detector configuration:
- `base/registry.py` — `DetectorMeta` dataclass, `DETECTORS` dict
- `engine/_scoring/policy/core.py` — `DETECTOR_SCORING_POLICIES` dict (maps detector → tier, dimension, scoring rules)
- `engine/_state/merge.py` — logic about which detectors mark subjective dimensions stale

**Step 2: Enrich DetectorMeta**

Add fields to the `DetectorMeta` frozen dataclass:
```python
@dataclass(frozen=True)
class DetectorMeta:
    name: str
    display: str
    dimension: str
    action_type: str
    guidance: str
    fixers: tuple[str, ...] = ()
    tool: str = ""
    structural: bool = False
    needs_judgment: bool = False
    standalone_threshold: str | None = None
    # NEW fields:
    tier: int = 2  # T1-T4 scoring weight
    marks_dims_stale: bool = False  # whether scan results mark subjective dims stale
```

**Step 3: Populate from existing policy**

For each detector in `DETECTORS`, set the `tier` and `marks_dims_stale` values by reading from the current `DETECTOR_SCORING_POLICIES` and merge logic.

**Step 4: Make policy modules read from registry**

Update `engine/_scoring/policy/core.py` to derive its `DETECTOR_SCORING_POLICIES` from the registry's `DetectorMeta.tier` field rather than maintaining a separate dict. Keep the policy module for any scoring logic that's more complex than a tier number.

**Step 5: Verify**

```bash
python -m pytest desloppify/tests/ -q
```

The goal is NOT to eliminate the scoring policy module — just to make `DetectorMeta` the authoritative first source so that adding/removing a detector only requires touching `registry.py`.

---

## P3b: Clean up cross-module private imports

**The problem**: Functions prefixed with `_` are imported across package boundaries, making refactoring brittle and ownership unclear.

**Step 1: Find the worst offenders**

```bash
# Find all cross-package imports of private symbols
grep -rn 'from desloppify\.[^ ]* import _' desloppify/ --include='*.py' | grep -v __pycache__ | grep -v tests/
```

**Step 2: For each private import crossing a package boundary:**

Option A: The function IS public API → remove the underscore prefix, add to `__all__` if applicable
Option B: The function should stay private → create a public wrapper or move the caller to the same package

**Known cases to fix:**
- `app/commands/review/cmd.py` imports `_do_run_batches` from the batch orchestrator → rename to `do_run_batches` (it's called from outside its module, so it's public)
- `app/cli_support/parser.py` imports `_add_plan_parser` from parser internals → rename to `add_plan_parser`
- Check `desloppify/state.py` for private scoring helper imports

**Step 3: Verify no other private-import patterns remain**

```bash
# Re-run the grep to confirm cleanup
grep -rn 'from desloppify\.[^ ]* import _' desloppify/ --include='*.py' | grep -v __pycache__ | grep -v tests/ | grep -v 'from desloppify\.\(.*\)\._' # exclude _internal subpackages
```

---

## Verification

```bash
python -m pytest desloppify/tests/ -q
```
