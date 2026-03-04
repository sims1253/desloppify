# P5: Module Decomposition — Split Oversized Command Modules

**Effort**: Large (4-6 hours)
**Risk**: Medium — structural changes to large files, but localized to specific command packages
**Files touched**: `app/commands/plan/triage/stages.py`, `app/commands/review/runner_process.py`, `app/commands/review/runner_parallel.py`

These are the three largest non-test modules in the codebase (989, 766, and 697 LOC). Each mixes multiple responsibilities that should be separated.

---

## General approach

For each module:
1. Read the entire file
2. Identify distinct responsibility clusters (validation, state mutation, rendering, I/O)
3. Extract each cluster into a sibling module in the same package
4. Leave a thin orchestrator in the original file
5. Run tests after each extraction to catch regressions immediately

**Rules:**
- Keep write-side effects (save_plan, filesystem writes, subprocess calls) centralized and explicit
- Don't change function signatures unless genuinely needed
- Name extracted modules descriptively (`_validation.py`, `_persistence.py`, `_rendering.py`)
- Update `__init__.py` re-exports if the package has them

---

## P5a: Split `app/commands/plan/triage/stages.py` (989 LOC)

This is the biggest file. Read it first to understand what it does, then split by responsibility.

**Likely clusters** (verify by reading):
- Stage definition/policy (what stages exist, what order, what criteria)
- Stage execution (running each stage, collecting results)
- Stage rendering/display (terminal output, progress bars)
- State persistence (saving triage results, updating plan)

**Target**: The original `stages.py` should become a ~100-200 line orchestrator that imports from the extracted modules.

**After splitting:**
```bash
python -m pytest desloppify/tests/ -q
# Also run any triage-specific tests:
python -m pytest desloppify/tests/ -k triage -v
```

---

## P5b: Split `app/commands/review/runner_process.py` (766 LOC)

**Likely clusters:**
- Process setup/configuration
- Subprocess execution (the actual codex/LLM runner)
- Output parsing/extraction
- Error handling and retry logic
- Followup scan orchestration

**Target**: runner_process.py should become a ~150-200 line module focused on process execution, with setup/parsing/followup extracted.

---

## P5c: Split `app/commands/review/runner_parallel.py` (697 LOC)

**Likely clusters:**
- Parallelization strategy (batch sizing, worker allocation)
- Worker execution loop
- Result collection and aggregation
- Progress reporting
- Error/failure handling

**Target**: runner_parallel.py keeps the main execution loop, with strategy/reporting/aggregation extracted.

---

## Important notes

- **Do NOT rename** the original files. Keep `stages.py`, `runner_process.py`, `runner_parallel.py` as the entry points. Extract siblings.
- **Preserve all public APIs**. If other modules import from these files, those imports must still work.
- **Test after each split**, not all at once. If a split breaks tests, revert and try a smaller extraction.
- **Don't over-split**. If a responsibility cluster is <50 lines, it's probably not worth extracting.

---

## Verification

```bash
python -m pytest desloppify/tests/ -q
```

All 4056+ tests must pass. Run full suite, not just targeted tests.
