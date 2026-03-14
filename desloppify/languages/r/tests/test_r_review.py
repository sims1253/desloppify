"""Tests for R review guidance hooks."""

from __future__ import annotations

from desloppify.languages.r.review import (
    HOLISTIC_REVIEW_DIMENSIONS,
    api_surface,
    module_patterns,
)


def test_holistic_dimensions_include_core_dimensions():
    assert "cross_module_architecture" in HOLISTIC_REVIEW_DIMENSIONS
    assert "design_coherence" in HOLISTIC_REVIEW_DIMENSIONS
    assert "test_strategy" in HOLISTIC_REVIEW_DIMENSIONS


def test_module_patterns_extracts_library_names():
    content = "library(dplyr)\nrequire(ggplot2)\nx <- 1"
    patterns = module_patterns(content)
    assert "dplyr" in patterns
    assert "ggplot2" in patterns


def test_module_patterns_ignores_base_r():
    content = "library(base)\nx <- 1"
    patterns = module_patterns(content)
    assert "base" in patterns


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
