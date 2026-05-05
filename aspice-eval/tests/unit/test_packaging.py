"""Unit tests for packaging configuration.

Tests that entry points, dependencies, and package data are correctly
declared in pyproject.toml.

Requirements: 11.1, 11.2, 11.3, 11.4, 11.5
"""

from __future__ import annotations

import importlib.metadata

import pytest


class TestEntryPoints:
    """Test that CLI entry points are resolvable."""

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
        import pathlib as _pathlib
        import importlib.resources as _pkg_resources

        pkg_root = _pathlib.Path(str(_pkg_resources.files("aspice_eval")))
        kb_path = pkg_root.parent.parent / "knowledge_base"
        assert kb_path.exists() or (pkg_root / "knowledge_base").exists()

    def test_kb_contains_aspice_metadata(self) -> None:
        """knowledge_base/aspice/_metadata.yaml exists."""
        import pathlib as _pathlib
        import importlib.resources as _pkg_resources

        pkg_root = _pathlib.Path(str(_pkg_resources.files("aspice_eval")))
        candidates = [
            pkg_root.parent.parent / "knowledge_base",
            pkg_root / "knowledge_base",
        ]
        for kb_path in candidates:
            metadata = kb_path / "aspice" / "_metadata.yaml"
            if metadata.exists():
                return
        pytest.fail("knowledge_base/aspice/_metadata.yaml not found")

    def test_kb_contains_criteria_files(self) -> None:
        """knowledge_base/aspice/ contains YAML criteria files."""
        import pathlib as _pathlib
        import importlib.resources as _pkg_resources

        pkg_root = _pathlib.Path(str(_pkg_resources.files("aspice_eval")))
        candidates = [
            pkg_root.parent.parent / "knowledge_base",
            pkg_root / "knowledge_base",
        ]
        for kb_path in candidates:
            aspice_dir = kb_path / "aspice"
            if aspice_dir.exists():
                yaml_files = list(aspice_dir.glob("*.yaml"))
                assert len(yaml_files) >= 5
                return
        pytest.fail("knowledge_base/aspice/ directory not found")
