"""R language plugin — lintr + tree-sitter."""

from desloppify.languages._framework.generic_support.core import generic_lang
from desloppify.languages._framework.treesitter import R_SPEC
from desloppify.languages.r import test_coverage as r_test_coverage_hooks

generic_lang(
    name="r",
    extensions=[".R", ".r"],
    tools=[
        {
            "label": "lintr",
            "cmd": (
                'Rscript -e \'cat(paste(capture.output('
                'lintr::lint_dir(".", show_notifications=FALSE)'
                '), collapse="\\n"))\''
            ),
            "fmt": "gnu",
            "id": "lintr_lint",
            "tier": 2,
            "fix_cmd": None,
        },
    ],
    exclude=[".Rhistory", ".RData", ".Rproj.user", "renv", "packrat"],
    depth="shallow",
    detect_markers=["DESCRIPTION", ".Rproj"],
    default_src="R",
    treesitter_spec=R_SPEC,
    test_coverage_module=r_test_coverage_hooks,
)

__all__ = [
    "generic_lang",
    "R_SPEC",
]
