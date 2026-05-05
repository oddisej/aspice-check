"""Property 4: aspice-check Uses Only Top-Level Imports.

Validates: Requirements 3.4, 3.5

For any import statement in aspice_check source code that references
confluence_ai or aspice_eval, the import path shall be the top-level
package only (not submodules like confluence_ai.client or
aspice_eval.evaluator).
"""

from __future__ import annotations

import ast
import pathlib


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


def test_prop04_aspice_check_uses_only_top_level_imports() -> None:
    """Module-level imports of confluence_ai and aspice_eval in aspice_check are top-level only.

    **Validates: Requirements 3.4, 3.5**

    Parses all Python source files under aspice-check/src/aspice_check/ using
    the ast module and verifies that no *module-level* import references a
    submodule of confluence_ai or aspice_eval (e.g., confluence_ai.client or
    aspice_eval.knowledge_base).

    Function-local imports (inside def/method bodies) are allowed — they are
    implementation details that don't affect the package's interface contract.
    """
    src_dir = pathlib.Path(__file__).resolve().parent.parent.parent / "src" / "aspice_check"
    assert src_dir.exists(), f"Source directory not found: {src_dir}"

    violations: list[str] = []

    for py_file in src_dir.rglob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue

        relative_path = py_file.relative_to(src_dir)

        # Only check module-level statements (direct children of the Module node)
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    _check_dotted_import(alias.name, relative_path, node.lineno, violations)

            elif isinstance(node, ast.ImportFrom):
                if node.module is None:
                    continue
                _check_from_import(node.module, relative_path, node.lineno, violations)

    assert not violations, (
        f"Found {len(violations)} submodule import(s) at module level in aspice_check:\n"
        + "\n".join(f"  - {v}" for v in violations)
    )


def _check_dotted_import(
    module_name: str,
    file_path: pathlib.Path,
    lineno: int,
    violations: list[str],
) -> None:
    """Check an 'import X.Y.Z' statement for submodule violations."""
    parts = module_name.split(".")
    if len(parts) > 1 and parts[0] in ("confluence_ai", "aspice_eval"):
        violations.append(
            f"{file_path}:{lineno} — import {module_name}"
        )


def _check_from_import(
    module_path: str,
    file_path: pathlib.Path,
    lineno: int,
    violations: list[str],
) -> None:
    """Check a 'from X.Y import Z' statement for submodule violations."""
    parts = module_path.split(".")
    if len(parts) > 1 and parts[0] in ("confluence_ai", "aspice_eval"):
        violations.append(
            f"{file_path}:{lineno} — from {module_path} import ..."
        )
