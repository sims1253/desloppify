# P1: Quick Safety & Correctness Wins

**Effort**: Small (1-2 hours total)
**Risk**: Very low — mechanical fixes, no behavioral changes except persistence signaling
**Files touched**: `app/commands/registry.py`, `engine/_state/persistence.py`, `engine/detectors/jscpd_adapter.py`, plus 3-5 files with assert replacements

---

## P1a: CommandHandler type fix

**File**: `desloppify/app/commands/registry.py`

One-line change. `CommandHandler = Callable[[Any], None]` should be `CommandHandler = Callable[[argparse.Namespace], None]`.

1. Add `import argparse` at the top (if not already present)
2. Change the type alias
3. Run `python -m pytest desloppify/tests/ -q`

This enables type checkers to catch any command handler that deviates from the expected signature.

---

## P1b: Replace assert guards with explicit errors

Production code paths use `assert` to enforce required payload invariants. These get stripped with `python -O`. Replace with explicit branches that raise `ValueError` or `CommandError`.

**How to find them all:**
```bash
grep -rn '^\s*assert ' desloppify/ --include='*.py' | grep -v __pycache__ | grep -v tests/ | grep -v conftest
```

**Known locations:**
- `app/commands/review/importing/helpers.py` — 3 asserts (e.g., `assert normalized_issues_data is not None`)
- `intelligence/review/importing/holistic.py` — `assert issue is not None`
- `app/commands/review/batch/core.py` — `assert issue is not None`, `assert isinstance(note_raw, dict)`

**For each assert:**
1. Read the surrounding context to understand what's being guarded
2. Replace with:
   ```python
   if condition_is_false:
       raise ValueError("description of what went wrong")
   ```
3. Use `CommandError` (from `desloppify.base.exception_sets`) if it's a user-facing error, `ValueError` for internal invariant violations

Run tests after all replacements.

---

## P1c: Harden jscpd adapter

**File**: `desloppify/engine/detectors/jscpd_adapter.py`

Two issues:

1. **SHA1 → SHA256**: Find `hashlib.sha1(...)` and replace with `hashlib.sha256(...)`. The hash is used for cluster IDs, not security, but SHA1 trips lint warnings and there's no reason not to use SHA256.

2. **Subprocess hardening**: Check the `subprocess.run(["npx", ...])` call. Ensure it uses explicit arguments (no shell=True), has a timeout, and handles CalledProcessError. If it already does all that, just document it with a comment.

Run tests after changes.

---

## P1d: Persistence load failure signaling

**File**: `desloppify/engine/_state/persistence.py`

**The problem**: If state JSON is corrupted, the load path silently falls back to `.json.bak`, then to `empty_state()`. The caller receives a valid-looking empty state and may overwrite real data.

**The fix** (choose the simplest approach):

1. Read the load function to understand the current fallback chain
2. Add a `LoadStatus` enum or simple string field:
   ```python
   class LoadStatus(enum.Enum):
       OK = "ok"
       RECOVERED_FROM_BACKUP = "recovered_from_backup"
       EMPTY_FALLBACK = "empty_fallback"
   ```
3. Return `(state, load_status)` from the load function
4. Update all callers to handle the status — at minimum, print a visible warning when status is not OK
5. Alternatively: just add a `logging.warning()` call at each fallback point and don't change the return type

The minimal approach (logging.warning at each fallback) is fine if changing the return type is too disruptive. The key requirement is that the user SEES something when their data is lost.

Run tests after changes. Existing tests may need updating if the return type changes.

---

## Verification

```bash
python -m pytest desloppify/tests/ -q
```

All 4056+ tests should still pass.
