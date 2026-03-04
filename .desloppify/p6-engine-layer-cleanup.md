# P6: Engine Layer Cleanup — Circular Dependency Fix + Orchestration Splits

**Effort**: Medium-large (4-6 hours)
**Risk**: Medium — moving scoring logic between modules, splitting state machine files
**Files touched**: `engine/_state/scoring.py`, `engine/_scoring/` (new file), `app/commands/scan/workflow.py`, `engine/_plan/stale_dimensions.py`, `engine/_plan/auto_cluster.py`

This workstream fixes the most important architectural smell in the engine layer: the state module computes scores (which creates a circular dependency), and several orchestration modules mix policy, queue mutation, and persistence.

---

## P6a: Fix the circular dependency — move scoring logic out of state

**Primary files**: `engine/_state/scoring.py` → `engine/_scoring/state_integration.py` (new)

**The problem**: `_state/scoring.py` contains `_update_objective_health()` and `_recompute_stats()` which need scoring functions from `engine/_scoring`. But `_scoring` transitively imports state types. This creates a cycle that's currently broken with deferred imports at line ~286-292:

```python
# Current: deferred imports inside _update_objective_health()
from desloppify.engine._scoring.detection import merge_potentials
from desloppify.engine._scoring.results.core import (
    compute_health_score,
    compute_score_bundle,
)
```

**The fix**:

1. Read `engine/_state/scoring.py` fully. Identify `_update_objective_health()` and `_recompute_stats()` — understand what state they read and write.

2. Create `engine/_scoring/state_integration.py`. Move both functions there:
   ```python
   """Bridge between state persistence and scoring computation.

   This module owns the score-recomputation step that runs before state is written.
   The dependency direction is: _scoring/state_integration → _state (reads state),
   _scoring/state_integration → _scoring (calls scoring functions).
   State persistence calls this module, never the reverse.
   """
   ```

3. In the new module, the imports that were deferred become normal module-level imports (since we're now IN the `_scoring` package).

4. Back in `engine/_state/scoring.py`, replace the moved functions with imports from the new module. The persistence layer calls `state_integration.recompute_stats(state)` instead of the local function.

5. **Verify the cycle is broken**: The deferred imports in `_state/scoring.py` should be gone. Run:
   ```bash
   grep -n 'from desloppify.engine._scoring' desloppify/engine/_state/scoring.py
   ```
   If any remain, they should now be module-level (not inside function bodies).

6. Run tests:
   ```bash
   python -m pytest desloppify/tests/ -q
   ```

**Stop if**: Moving the functions creates new circular imports elsewhere. In that case, the transitive cycle is deeper than expected — document what you found and escalate.

---

## P6b: Split scan/plan orchestration state machines

Three modules mix policy decisions, queue mutation, and persistence sequencing. Each should be split into policy + orchestration.

### `engine/_plan/stale_dimensions.py`

1. Read the file. It handles stale/unscored/under-target/triage/workflow synthetic queue logic.
2. Identify pure policy functions (e.g., "is this dimension stale?", "which issues are under target?") vs mutation functions (e.g., "update the queue", "mark dimensions").
3. Extract policy functions to `engine/_plan/stale_policy.py`
4. Keep the orchestration (which calls policy then mutates) in `stale_dimensions.py`
5. Run tests.

### `engine/_plan/auto_cluster.py`

1. Read the file. It handles grouping strategy + cluster lifecycle + override synchronization.
2. Extract grouping strategy (pure functions that decide how to cluster) to `engine/_plan/cluster_strategy.py`
3. Keep lifecycle/sync orchestration in `auto_cluster.py`
4. Run tests.

### `app/commands/scan/workflow.py` (516 LOC)

1. Read the file. It does runtime prep + scan generation + merge/persist + reminders.
2. This is smaller (516 LOC) — only split if there are clear 100+ line clusters of distinct responsibility.
3. Likely candidates: extract runtime setup to `scan/runtime_setup.py`, extract post-scan merge/persist to `scan/post_scan.py`
4. If the splits would produce files <80 lines each, skip this one — 516 LOC is manageable.
5. Run tests.

---

## Verification

```bash
python -m pytest desloppify/tests/ -q
# Specifically verify scoring still works:
python -m pytest desloppify/tests/ -k "scoring or score" -v
```
