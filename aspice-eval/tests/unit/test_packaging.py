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

    def test_core_dependencies(self) -> None:
        """Core dependencies (pyyaml, jsonschema, click) are declared."""
        requires = importlib.metadata.requires("aspice-eval") or []
        dep_names = [r.split(">")[0].split("<")[0].split("=")[0].split(";")[0].strip().lower() for r in requires]
        assert "pyyaml" in dep_names, (
            f"pyyaml not in dependencies: {dep_names}"
        )
        assert "jsonschema" in dep_names, (
            f"jsonschema not in dependencies: {dep_names}"
        )
        assert "click" in dep_names, (
            f"click not in dependencies: {dep_names}"
        )

    def test_no_confluence_dependencies(self) -> None:
        """aspice-eval SHALL NOT depend on Confluence libraries (Req 1.6, 1.7)."""
        requires = importlib.metadata.requires("aspice-eval") or []
        all_deps_lower = " ".join(requires).lower()
        assert "atlassian-python-api" not in all_deps_lower, (
            "atlassian-python-api should not be in aspice-eval dependencies"
        )
        assert "confluence-exporter" not in all_deps_lower, (
            "confluence-exporter should not be in aspice-eval dependencies"
        )
        assert "confluence-ai" not in all_deps_lower, (
            "confluence-ai should not be in aspice-eval dependencies"
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
