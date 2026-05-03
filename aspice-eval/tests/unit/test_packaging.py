"""Unit tests for packaging configuration.

Tests that entry points, dependencies, and package data are correctly
declared in pyproject.toml.

Requirements: 11.1, 11.2, 11.3, 11.4, 11.5
"""

from __future__ import annotations

import importlib.metadata
import pathlib

import pytest


class TestEntryPoints:
    """Test that CLI entry points are resolvable."""

    def test_aspice_analyze_entry_point(self) -> None:
        """aspice-analyze entry point is registered."""
        eps = importlib.metadata.entry_points()
        # In Python 3.12+, entry_points() returns a SelectableGroups
        if hasattr(eps, "select"):
            console_scripts = eps.select(group="console_scripts")
        else:
            console_scripts = eps.get("console_scripts", [])

        names = [ep.name for ep in console_scripts]
        assert "aspice-analyze" in names, (
            f"aspice-analyze not found in console_scripts: {names}"
        )

    def test_aspice_eval_entry_point(self) -> None:
        """aspice-eval entry point is still registered."""
        eps = importlib.metadata.entry_points()
        if hasattr(eps, "select"):
            console_scripts = eps.select(group="console_scripts")
        else:
            console_scripts = eps.get("console_scripts", [])

        names = [ep.name for ep in console_scripts]
        assert "aspice-eval" in names


class TestDependencies:
    """Test that required dependencies are declared."""

    def test_atlassian_python_api_dependency(self) -> None:
        """atlassian-python-api is declared as a dependency."""
        requires = importlib.metadata.requires("aspice-eval") or []
        # Check that atlassian-python-api appears in requires
        dep_names = [r.split(">")[0].split("<")[0].split("=")[0].split(";")[0].strip().lower() for r in requires]
        assert "atlassian-python-api" in dep_names, (
            f"atlassian-python-api not in dependencies: {dep_names}"
        )

    def test_confluence_exporter_optional_dependency(self) -> None:
        """confluence-exporter is declared as an optional dependency."""
        requires = importlib.metadata.requires("aspice-eval") or []
        # confluence-exporter should appear with an extra marker
        ce_deps = [r for r in requires if "confluence-exporter" in r.lower()]
        assert len(ce_deps) > 0, (
            f"confluence-exporter not found in dependencies: {requires}"
        )


class TestKnowledgeBasePackageData:
    """Test that knowledge_base files are accessible."""

    def test_kb_directory_exists(self) -> None:
        """knowledge_base/ directory exists relative to the package."""
        from aspice_eval.analyze import _resolve_kb_path

        kb_path = _resolve_kb_path()
        assert pathlib.Path(kb_path).exists()

    def test_kb_contains_aspice_metadata(self) -> None:
        """knowledge_base/aspice/_metadata.yaml exists."""
        from aspice_eval.analyze import _resolve_kb_path

        kb_path = _resolve_kb_path()
        metadata = pathlib.Path(kb_path) / "aspice" / "_metadata.yaml"
        assert metadata.exists()

    def test_kb_contains_criteria_files(self) -> None:
        """knowledge_base/aspice/ contains YAML criteria files."""
        from aspice_eval.analyze import _resolve_kb_path

        kb_path = _resolve_kb_path()
        aspice_dir = pathlib.Path(kb_path) / "aspice"
        yaml_files = list(aspice_dir.glob("*.yaml"))
        # Should have at least _metadata.yaml + swe.yaml + sys.yaml + man.yaml + sup.yaml
        assert len(yaml_files) >= 5
