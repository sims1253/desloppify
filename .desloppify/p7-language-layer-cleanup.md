# P7: Language Layer Cleanup — Tree-Sitter Decomposition + Language Config Splits

**Effort**: Large (5-7 hours)
**Risk**: Medium — structural changes to the language framework and plugin assembly modules
**Files touched**: `languages/_framework/treesitter/_imports.py`, `languages/typescript/__init__.py`, `languages/python/__init__.py`, and potentially other large language `__init__.py` files

---

## P7a: Decompose tree-sitter import resolver monolith

**Primary file**: `desloppify/languages/_framework/treesitter/_imports.py` (774 LOC)

**The problem**: This file mixes three distinct responsibilities:
1. Dependency graph building (shared infrastructure)
2. Per-language import resolution rules (`resolve_python_import`, `resolve_ts_import`, `resolve_go_import`, etc.)
3. Module-level mutable caching (`_GO_MODULE_CACHE` and similar)

**Step 1: Read and map responsibilities**

Read the entire file. For each function, annotate which responsibility it belongs to:
- **Graph core**: Functions that build/traverse the import graph regardless of language
- **Language resolvers**: Functions named `resolve_<lang>_import` or similar
- **Cache**: Module-level mutable state and functions that manage it

**Step 2: Split into modules**

Create sibling modules in the same `treesitter/` package:

```
languages/_framework/treesitter/
├── __init__.py          (existing)
├── _imports.py          (keep as thin orchestrator / public API)
├── _import_graph.py     (NEW: shared graph building, traversal)
├── _import_resolvers.py (NEW: per-language resolve_*_import functions)
├── _import_cache.py     (NEW: cache abstraction)
├── _complexity.py       (existing)
├── _extractors.py       (existing)
└── phases.py            (existing)
```

**Step 3: Handle the mutable cache**

Replace bare module-level dicts like `_GO_MODULE_CACHE = {}` with an explicit cache class:
```python
class ImportCache:
    """Encapsulated import resolution cache, scoped per scan."""
    def __init__(self):
        self._go_modules: dict[str, str] = {}
        # ... other caches

    def clear(self):
        self._go_modules.clear()
```

If the cache needs to be module-level for performance, that's fine — but wrap it so there's a clear `reset()` method for test isolation.

**Step 4: Keep _imports.py as the public interface**

`_imports.py` should become a thin re-export layer:
```python
from ._import_graph import build_import_graph, ...
from ._import_resolvers import resolve_python_import, resolve_ts_import, ...
```

This preserves backward compatibility — all existing importers of `_imports` keep working.

**Step 5: Verify**

```bash
python -m pytest desloppify/tests/ -q
# Specifically test tree-sitter functionality:
python -m pytest desloppify/tests/ -k "treesitter or tree_sitter or imports" -v
```

**Stop if**: You find that the resolvers share significant internal state with the graph builder in ways that make splitting create excessive cross-module coupling. In that case, just split out the cache and leave the rest.

---

## P7b: Decompose large language config assembly modules

**Primary files**: `languages/typescript/__init__.py`, `languages/python/__init__.py`
**Secondary**: `languages/csharp/__init__.py`, `languages/dart/__init__.py`, `languages/go/__init__.py`, `languages/gdscript/__init__.py`

**The problem**: Large language `__init__.py` files carry too many responsibilities: registration, detector wiring, fixer setup, zone rules, review hooks. For TypeScript and Python this is hundreds of lines in a single file.

**Step 1: Assess which files are actually big enough to split**

```bash
wc -l desloppify/languages/*/__init__.py | sort -rn | head -10
```

Only split files that are >200 LOC. The generic language stubs (2-line `__init__.py` files) should NOT be touched.

**Step 2: For each large language __init__.py**

Read the file and identify these responsibility clusters:
- **Detector registration**: `_get_<lang>_detectors()` or similar
- **Fixer registration**: `_get_<lang>_fixers()` or similar
- **Review configuration**: dimension hooks, review constraints
- **Zone/path rules**: language-specific zone classification
- **Config assembly**: the `LangConfig(...)` construction at the bottom

**Step 3: Extract into config sub-modules**

For a language like TypeScript:
```
languages/typescript/
├── __init__.py          (keep: thin assembly, LangConfig construction)
├── _detectors.py        (NEW: _get_ts_detectors(), detector wiring)
├── _fixers.py           (NEW: _get_ts_fixers(), fixer wiring — may already exist in fixers/)
├── _review.py           (NEW: review dimension config, hooks)
├── commands.py           (existing)
├── detectors/            (existing)
├── extractors.py         (existing)
├── fixers/               (existing)
├── phases.py             (existing)
└── ...
```

**Step 4: Keep __init__.py as the assembly surface**

`__init__.py` becomes a ~50-100 line file that imports from the config sub-modules and constructs `LangConfig`. This is the "wiring" file — it should be obvious at a glance what a language plugin provides.

**Step 5: Only do this for languages where it actually helps**

If a language's `__init__.py` is <150 LOC, don't split it. The overhead of multiple files isn't worth it for small configs.

---

## Verification

```bash
python -m pytest desloppify/tests/ -q
# Verify language detection still works:
python -m desloppify --lang typescript scan --help
python -m desloppify --lang python scan --help
```
