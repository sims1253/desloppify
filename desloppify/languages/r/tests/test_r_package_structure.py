"""Tests for R package structure parsing."""

from __future__ import annotations

from pathlib import Path

from desloppify.languages.r.package_structure import (
    RPackageInfo,
    discover_package,
    is_r_package,
    parse_description,
    parse_namespace,
)


def _write(path: Path, rel_path: str, content: str) -> Path:
    target = path / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return target


def test_parse_description_basic(tmp_path):
    _write(
        tmp_path,
        "DESCRIPTION",
        "Package: mypkg\nVersion: 1.0.0\n"
        "Title: My Package\n"
        "Description: A test package.\n"
        "License: MIT\n",
    )
    info = parse_description(tmp_path / "DESCRIPTION")
    assert info.name == "mypkg"
    assert info.version == "1.0.0"
    assert info.license == "MIT"


def test_parse_description_with_dependencies(tmp_path):
    _write(
        tmp_path,
        "DESCRIPTION",
        "Package: mypkg\n"
        "Depends: R (>= 3.5.0)\n"
        "Imports: dplyr (>= 1.0.0), ggplot2, tidyr\n"
        "Suggests: testthat (>= 3.0.0), knitr\n",
    )
    info = parse_description(tmp_path / "DESCRIPTION")
    assert "R" in info.depends
    assert "dplyr" in info.imports
    assert "ggplot2" in info.imports
    assert "tidyr" in info.imports
    assert "testthat" in info.suggests
    assert "knitr" in info.suggests
    # Version conditions should be stripped
    assert "(>= 1.0.0)" not in info.imports


def test_parse_description_multiline(tmp_path):
    _write(
        tmp_path,
        "DESCRIPTION",
        "Package: mypkg\n"
        "Description: This is a long description\n"
        "    that spans multiple lines.\n"
        "License: MIT\n",
    )
    info = parse_description(tmp_path / "DESCRIPTION")
    assert "long description" in info.description
    assert "multiple lines" in info.description


def test_parse_description_missing_file(tmp_path):
    info = parse_description(tmp_path / "DESCRIPTION")
    assert info.name == ""


def test_parse_namespace_exports(tmp_path):
    _write(
        tmp_path,
        "NAMESPACE",
        "export(my_func)\nexport(helper)\nexportClasses(MyClass)\n",
    )
    fns, cls = parse_namespace(tmp_path / "NAMESPACE")
    assert "my_func" in fns
    assert "helper" in fns
    assert "MyClass" in cls


def test_parse_namespace_s3_methods(tmp_path):
    _write(
        tmp_path,
        "NAMESPACE",
        "S3method(print, my_class)\nexport(my_generic)\n",
    )
    fns, cls = parse_namespace(tmp_path / "NAMESPACE")
    assert "my_generic" in fns
    assert "print" in fns


def test_parse_namespace_missing_file(tmp_path):
    fns, cls = parse_namespace(tmp_path / "NAMESPACE")
    assert fns == []
    assert cls == []


def test_discover_package_full(tmp_path):
    _write(tmp_path, "DESCRIPTION", "Package: mypkg\nVersion: 0.1.0\n")
    _write(tmp_path, "NAMESPACE", "export(main_func)\n")
    _write(tmp_path, "R/main.R", "main_func <- function() {}\n")
    _write(tmp_path, "R/utils.R", "helper <- function() {}\n")

    info = discover_package(tmp_path)
    assert info.name == "mypkg"
    assert info.has_namespace is True
    assert info.has_r_directory is True
    assert "main_func" in info.exported_functions
    assert any("main.R" in f for f in info.r_files)
    assert any("utils.R" in f for f in info.r_files)


def test_discover_package_no_namespace(tmp_path):
    _write(tmp_path, "DESCRIPTION", "Package: simple\nVersion: 1.0\n")
    _write(tmp_path, "R/func.R", "f <- function() {}\n")

    info = discover_package(tmp_path)
    assert info.name == "simple"
    assert info.has_namespace is False
    assert info.has_r_directory is True


def test_is_r_package(tmp_path):
    _write(tmp_path, "DESCRIPTION", "Package: mypkg\n")
    assert is_r_package(tmp_path) is True

    empty = tmp_path / "empty"
    empty.mkdir()
    assert is_r_package(empty) is False
