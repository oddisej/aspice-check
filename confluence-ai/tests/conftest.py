"""Shared test configuration and Hypothesis settings profiles.

Mirrors the profiles in ``aspice-eval/tests/conftest.py`` and provides a set
of reusable Hypothesis strategies that property tests across the monorepo
can import.

The strategies intentionally live at the ``tests/`` root (rather than in a
``strategies.py`` module) so they are discoverable via ``conftest.py``
autoload and can be imported with ``from tests.conftest import ...``.
"""

from __future__ import annotations

import string

from hypothesis import settings, strategies as st

# ---------------------------------------------------------------------------
# Hypothesis profiles
# ---------------------------------------------------------------------------

# CI profile: thorough testing with 100 examples per property
settings.register_profile("ci", max_examples=100)

# Dev profile: faster feedback with 50 examples per property
settings.register_profile("dev", max_examples=50)

# Default to CI profile for consistent test coverage
settings.load_profile("ci")


# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------

# Non-empty ASCII identifiers usable as provider names / registry keys.
# Restricted to characters that are safe as Python identifiers plus ``-`` and
# ``_`` so they can double as CLI-friendly slugs (e.g. "bedrock", "openai-gpt4").
_IDENTIFIER_ALPHABET = string.ascii_letters + string.digits + "_-"

valid_provider_name_st = st.text(
    alphabet=_IDENTIFIER_ALPHABET,
    min_size=1,
    max_size=32,
).filter(lambda s: s.strip() != "")
"""Strategy producing non-empty ASCII identifier-like provider names."""


invalid_provider_name_st: st.SearchStrategy[object] = st.one_of(
    st.just(""),
    # Whitespace-only strings of varying length
    st.text(alphabet=" \t\n\r", min_size=1, max_size=8),
    # Non-string types
    st.none(),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.lists(st.integers(), max_size=3),
    st.dictionaries(st.text(max_size=3), st.integers(), max_size=3),
)
"""Strategy producing values that are NOT valid provider names.

Includes empty strings, whitespace-only strings, and non-string types.
"""


def _make_dynamic_class(name: str, base: type = object) -> type:
    """Construct a new class object with ``name`` extending ``base``."""
    # ``type`` must receive a ``str`` name — coerce defensively.
    cls_name = name if name.isidentifier() else f"Cls_{abs(hash(name))}"
    return type(cls_name, (base,), {})


valid_class_type_st: st.SearchStrategy[type] = st.builds(
    _make_dynamic_class,
    st.text(alphabet=string.ascii_letters, min_size=1, max_size=16),
)
"""Strategy yielding dynamically created class objects.

Useful for testing ``register_*`` functions that accept class objects and
validate them via ``issubclass``.
"""


invalid_class_type_st: st.SearchStrategy[object] = st.one_of(
    st.text(max_size=16),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.none(),
    st.dictionaries(st.text(max_size=3), st.integers(), max_size=3),
    st.lists(st.integers(), max_size=3),
    st.tuples(st.integers(), st.integers()),
)
"""Strategy producing values that are NOT classes.

Useful for exercising the ``TypeError`` path of registration helpers that
require a class object.
"""


# POSIX-style path segments. Exclude characters that are illegal on most
# filesystems (``/`` is used as the separator, NUL is forbidden) and keep
# segments printable to make failures easy to read.
_PATH_SEGMENT_ALPHABET = string.ascii_letters + string.digits + "_-."


def _assemble_path(segments: list[str], absolute: bool) -> str:
    joined = "/".join(segments)
    return f"/{joined}" if absolute else joined


path_like_st: st.SearchStrategy[str] = st.builds(
    _assemble_path,
    st.lists(
        st.text(alphabet=_PATH_SEGMENT_ALPHABET, min_size=1, max_size=16).filter(
            lambda s: s not in {".", ".."}
        ),
        min_size=1,
        max_size=5,
    ),
    st.booleans(),
)
"""Strategy producing POSIX-style path strings (absolute or relative).

The strategy avoids NUL bytes, empty segments, and ``.``/``..`` to keep the
generated paths unambiguous for tests that treat them as opaque keys.
"""
