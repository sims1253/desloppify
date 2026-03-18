"""R language plugin — goodpractice, Jarl, lintr + tree-sitter + R-specific smells."""

from desloppify.languages._framework.base.types import DetectorPhase
from desloppify.languages._framework.generic_support.core import generic_lang
from desloppify.languages._framework.treesitter import R_SPEC
from desloppify.languages.r.phases_smells import phase_smells
from desloppify.languages.r import test_coverage as r_test_coverage_hooks
from desloppify.languages.r.review import (
    HOLISTIC_REVIEW_DIMENSIONS,
    LOW_VALUE_PATTERN,
    REVIEW_GUIDANCE,
    api_surface,
    module_patterns,
)

generic_lang(
    name="r",
    extensions=[".R", ".r"],
    tools=[
        {
            "label": "jarl",
            "cmd": "jarl check .",
            "fmt": "gnu",
            "id": "jarl_lint",
            "tier": 2,
            "fix_cmd": "jarl check . --fix --allow-dirty",
        },
        {
            "label": "lintr",
            "cmd": (
                "Rscript -e \"lintr::lint_dir('.')\""
            ),
            "fmt": "gnu",
            "id": "lintr_lint",
            "tier": 3,
            "fix_cmd": None,
        },
        {
            "label": "goodpractice",
            "cmd": (
                "Rscript -e "
                "\"library(goodpractice); "
                "g <- gp('.'); "
                "cat(jsonlite::toJSON(results(g), pretty=TRUE))\""
            ),
            "fmt": "goodpractice",
            "id": "goodpractice",
            "tier": 3,
            "fix_cmd": None,
        },
        {
            "label": "covr",
            "cmd": "Rscript -e \"cat(covr::package_coverage())\"",
            "fmt": "covr",
            "id": "covr_coverage",
            "tier": 3,
            "fix_cmd": None,
        },
        {
            "label": "R CMD check",
            "cmd": "R CMD check --no-manual --no-build-vignettes .",
            "fmt": "r_cmd_check",
            "id": "r_cmd_check",
            "tier": 3,
            "fix_cmd": None,
        },
    ],
    exclude=[
        ".Rhistory",
        ".RData",
        ".Rproj.user",
        "renv",
        "packrat",
        "man",
        "Meta",
        "doc",
        "inst/doc",
        "NAMESPACE",
    ],
    depth="shallow",
    detect_markers=["DESCRIPTION", ".Rproj"],
    default_src="R",
    treesitter_spec=R_SPEC,
    custom_phases=[
        DetectorPhase("R code smells", phase_smells),
    ],
    test_coverage_module=r_test_coverage_hooks,
    review={
        "holistic_review_dimensions": HOLISTIC_REVIEW_DIMENSIONS,
        "review_guidance": REVIEW_GUIDANCE,
        "review_low_value_pattern": LOW_VALUE_PATTERN,
        "review_module_patterns_fn": module_patterns,
        "review_api_surface_fn": api_surface,
    },
)

__all__ = [
    "generic_lang",
    "R_SPEC",
]
