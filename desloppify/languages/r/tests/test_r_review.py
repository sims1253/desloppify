"""Tests for R review guidance hooks."""

from __future__ import annotations

from desloppify.languages.r.review import (
    HOLISTIC_REVIEW_DIMENSIONS,
    REVIEW_GUIDANCE,
    api_surface,
    module_patterns,
)


def test_holistic_dimensions_include_core_dimensions():
    assert "cross_module_architecture" in HOLISTIC_REVIEW_DIMENSIONS
    assert "design_coherence" in HOLISTIC_REVIEW_DIMENSIONS
    assert "test_strategy" in HOLISTIC_REVIEW_DIMENSIONS


def test_holistic_dimensions_include_posit_derived_dimensions():
    assert "cran_readiness" in HOLISTIC_REVIEW_DIMENSIONS
    assert "api_lifecycle_health" in HOLISTIC_REVIEW_DIMENSIONS
    assert "vectorization_discipline" in HOLISTIC_REVIEW_DIMENSIONS
    assert "package_organization" in HOLISTIC_REVIEW_DIMENSIONS
    assert "convention_outlier" in HOLISTIC_REVIEW_DIMENSIONS


def test_review_guidance_includes_vectorization_checks():
    assert any("vectorized" in p for p in REVIEW_GUIDANCE["patterns"])
    assert any("ifelse()" in p or "any()" in p for p in REVIEW_GUIDANCE["patterns"])


def test_review_guidance_includes_cran_readiness():
    assert any("@return" in p for p in REVIEW_GUIDANCE["patterns"])
    assert any("@examples" in p for p in REVIEW_GUIDANCE["patterns"])
    assert any("title case" in p.lower() for p in REVIEW_GUIDANCE["patterns"])
    assert any('"This package"' in p for p in REVIEW_GUIDANCE["patterns"])


def test_review_guidance_includes_lifecycle_checks():
    assert any("lifecycle::badge" in p for p in REVIEW_GUIDANCE["patterns"])
    assert any("deprecate_warn" in p for p in REVIEW_GUIDANCE["patterns"])
    assert any("signal_stage" in p for p in REVIEW_GUIDANCE["patterns"])


def test_review_guidance_includes_test_quality():
    assert any("self-sufficient" in p for p in REVIEW_GUIDANCE["patterns"])
    assert any("withr::local_" in p for p in REVIEW_GUIDANCE["patterns"])
    assert any("context()" in p for p in REVIEW_GUIDANCE["patterns"])


def test_review_guidance_includes_r_code_red_flags():
    assert any("partial argument" in p for p in REVIEW_GUIDANCE["patterns"])
    assert any("early return" in p.lower() for p in REVIEW_GUIDANCE["patterns"])
    assert any("return()" in p for p in REVIEW_GUIDANCE["patterns"])
    assert any("setwd()" in p for p in REVIEW_GUIDANCE["patterns"])


def test_module_patterns_extracts_library_names():
    content = "library(dplyr)\nrequire(ggplot2)\nx <- 1"
    patterns = module_patterns(content)
    assert any("dplyr" in p for p in patterns)
    assert any("ggplot2" in p for p in patterns)


def test_module_patterns_ignores_base_r():
    content = "library(base)\nx <- 1"
    patterns = module_patterns(content)
    assert any("base" in p for p in patterns)


def test_module_patterns_detects_exports():
    content = "#' @export\n#' @return A value\nmy_fun <- function() {}\n"
    patterns = module_patterns(content)
    assert "has_exports" in patterns
    assert "has_documented_returns" in patterns


def test_module_patterns_detects_lifecycle():
    content = "#' lifecycle::badge(\"deprecated\")\n"
    patterns = module_patterns(content)
    assert "has_lifecycle_badges" in patterns


def test_api_surface_extracts_functions():
    file_contents = {
        "R/transform.R": "transform_data <- function(x) { x }\n_helper <- function() {}\n",
        "R/utils.R": "format_output <- function(x) { x }\n",
    }
    surface = api_surface(file_contents)
    assert "transform_data" in surface["public_functions"]
    assert "format_output" in surface["public_functions"]
    assert "_helper" not in surface["public_functions"]


def test_api_surface_extracts_r6_classes():
    file_contents = {
        "R/person.R": 'Person <- R6Class("Person",\n  public = list(\n    greet = function() {}\n  )\n)\n',
    }
    surface = api_surface(file_contents)
    assert "Person" in surface["r6_classes"]


def test_api_surface_extracts_s3_constructors():
    file_contents = {
        "R/person.R": "create_person <- function(name) {\n  structure(list(name = name), class = 'person')\n}\n",
    }
    surface = api_surface(file_contents)
    assert "create_person" in surface["s3_constructors"]


def test_api_surface_empty():
    surface = api_surface({})
    assert surface["public_functions"] == []
    assert surface["r6_classes"] == []
    assert surface["s3_constructors"] == []


def test_api_surface_detects_exported_missing_return():
    file_contents = {
        "R/foo.R": (
            "#' @export\n"
            "#' Do a thing\n"
            "#' @param x input\n"
            "foo <- function(x) { x + 1 }\n"
        ),
    }
    surface = api_surface(file_contents)
    assert len(surface["exported_missing_return"]) == 1
    assert "R/foo.R" in surface["exported_missing_return"][0]


def test_api_surface_exported_with_return_is_ok():
    file_contents = {
        "R/foo.R": (
            "#' @export\n"
            "#' Do a thing\n"
            "#' @param x input\n"
            "#' @return A numeric value\n"
            "#' @examples\n"
            "#' foo(1)\n"
            "foo <- function(x) { x + 1 }\n"
        ),
    }
    surface = api_surface(file_contents)
    assert surface["exported_missing_return"] == []
    assert surface["exported_missing_examples"] == []


def test_api_surface_detects_t_f_literals():
    file_contents = {
        "R/bad.R": "x <- T\ny <- F\nz <- TRUE\n",
    }
    surface = api_surface(file_contents)
    assert len(surface["uses_t_f_literal"]) == 2
    # TRUE should not be flagged
    assert all("TRUE" not in loc for loc in surface["uses_t_f_literal"])


def test_api_surface_detects_library_inside_function():
    file_contents = {
        "R/bad.R": (
            "my_func <- function(x) {\n"
            "  library(dplyr)\n"
            "  x %>% mutate(y = 1)\n"
            "}\n"
        ),
    }
    surface = api_surface(file_contents)
    assert any("my_func" in loc for loc in surface["library_inside_function"])


def test_api_surface_tolerates_library_at_top_level():
    file_contents = {
        "R/good.R": (
            "library(dplyr)\n\n"
            "my_func <- function(x) {\n"
            "  x %>% mutate(y = 1)\n"
            "}\n"
        ),
    }
    surface = api_surface(file_contents)
    assert surface["library_inside_function"] == []
