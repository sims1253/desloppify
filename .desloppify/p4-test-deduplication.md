# P4: Review Test Suite Deduplication

**Effort**: Medium (2-3 hours)
**Risk**: Low — test-only changes, no production code modified
**Files touched**: `tests/review/` and `tests/review/integration/` (test files only)

---

## The Problem

Review test cases are split across `tests/review/` and `tests/review/integration/` with substantial overlap:

- `tests/review/review_commands_cases.py` (~2781 lines) vs `tests/review/integration/review_commands_cases.py` (~2782 lines) — nearly identical
- Similar overlap pattern in misc/coverage/work-queue case modules

This means:
- Bug fixes must be applied in two places
- Tests can drift apart silently
- Maintenance cost is doubled

---

## Step 1: Identify all duplicated case modules

```bash
# Find matching filenames across the two directories
for f in desloppify/tests/review/*.py; do
    base=$(basename "$f")
    integration="desloppify/tests/review/integration/$base"
    if [ -f "$integration" ]; then
        echo "=== $base ==="
        diff <(wc -l < "$f") <(wc -l < "$integration")
        diff "$f" "$integration" | head -20
        echo ""
    fi
done
```

---

## Step 2: For each pair of near-identical files

1. **Diff them** to find the actual differences:
   ```bash
   diff desloppify/tests/review/review_commands_cases.py desloppify/tests/review/integration/review_commands_cases.py
   ```

2. **Decide which is canonical**. Usually the one in `tests/review/` is the original and `tests/review/integration/` is the copy.

3. **Make the integration version import from canonical**:
   ```python
   # tests/review/integration/review_commands_cases.py
   # Instead of duplicating all test cases, import from canonical location
   from desloppify.tests.review.review_commands_cases import *  # noqa: F401,F403
   ```

   Or better — if the integration file adds extra setup (like a different fixture or conftest), keep only that extra setup and import test cases from the canonical module.

4. If there are genuine differences (not just whitespace/line count), merge the best parts into the canonical version and delete the duplicate.

---

## Step 3: Check for test files that exist in ONLY one location

```bash
# Files only in integration/
for f in desloppify/tests/review/integration/*.py; do
    base=$(basename "$f")
    if [ ! -f "desloppify/tests/review/$base" ]; then
        echo "integration-only: $base"
    fi
done

# Files only in review/
for f in desloppify/tests/review/*.py; do
    base=$(basename "$f")
    if [ ! -f "desloppify/tests/review/integration/$base" ] && [ "$base" != "__init__.py" ] && [ "$base" != "conftest.py" ]; then
        echo "review-only: $base"
    fi
done
```

Unique files are fine — they don't need deduplication.

---

## Step 4: Verify test count doesn't decrease

Before making changes, record the test count:
```bash
python -m pytest desloppify/tests/review/ -q 2>&1 | tail -3
```

After deduplication, the test count should be the same or HIGHER (if duplicate tests were accidentally masking each other).

---

## Verification

```bash
python -m pytest desloppify/tests/ -q
```

All tests must pass. Test count should not decrease.
