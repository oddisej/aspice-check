"""Property 1: Package Isolation.

Validates: Requirements 1.1, 1.2, 1.3, 1.4

For any symbol in confluence_ai.__all__ or aspice_eval.__all__, importing
that symbol shall not cause the other package (or aspice_check) to appear
in sys.modules.
"""

from __future__ import annotations

import subprocess
import sys


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_prop01_confluence_ai_does_not_load_aspice_eval() -> None:
    """Importing confluence_ai does not load aspice_eval or aspice_check.

    **Validates: Requirements 1.1, 1.2**

    Runs a subprocess that imports confluence_ai and checks sys.modules
    for aspice_eval or aspice_check entries.
    """
    code = (
        "import sys; "
        "import confluence_ai; "
        "loaded = [m for m in sys.modules if m.startswith('aspice_eval') or m.startswith('aspice_check')]; "
        "print(','.join(loaded) if loaded else 'CLEAN')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Process failed: {result.stderr}"
    output = result.stdout.strip()
    assert output == "CLEAN", (
        f"Importing confluence_ai loaded unexpected modules: {output}"
    )


def test_prop01_aspice_eval_does_not_load_confluence_ai() -> None:
    """Importing aspice_eval does not load confluence_ai or aspice_check.

    **Validates: Requirements 1.3, 1.4**

    Runs a subprocess that imports aspice_eval and checks sys.modules
    for confluence_ai or aspice_check entries.
    """
    code = (
        "import sys; "
        "import aspice_eval; "
        "loaded = [m for m in sys.modules if m.startswith('confluence_ai') or m.startswith('aspice_check')]; "
        "print(','.join(loaded) if loaded else 'CLEAN')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Process failed: {result.stderr}"
    output = result.stdout.strip()
    assert output == "CLEAN", (
        f"Importing aspice_eval loaded unexpected modules: {output}"
    )
