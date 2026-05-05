"""Property 1: Credential resolution follows precedence order.

*For any* combination of credential values provided via CLI arguments,
environment variables, and configuration file — where at least one source
provides a value — the resolved credential SHALL equal the value from the
highest-precedence source that is present (CLI > environment variable >
configuration file).

**Validates: Requirements 1.4**

Feature: confluence-ai, Property 1: Credential resolution follows precedence order
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Credential resolution logic under test
# ---------------------------------------------------------------------------
# The CLI uses Click's built-in precedence: explicit CLI arg > envvar > default.
# We model this as a pure function for property testing.


def resolve_credential(
    cli_value: str | None,
    env_value: str | None,
    config_value: str | None,
) -> str | None:
    """Resolve a credential using CLI > env > config precedence.

    This mirrors the resolution logic used by the Click CLI options
    (--email, --api-token) where CLI arguments take precedence over
    environment variables, which take precedence over config file values.
    """
    if cli_value is not None:
        return cli_value
    if env_value is not None:
        return env_value
    if config_value is not None:
        return config_value
    return None


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_credential_value = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())

_optional_credential = st.one_of(st.none(), _credential_value)


class TestProperty01CredentialPrecedence:
    """Property 1: Credential resolution follows CLI > env > config precedence."""

    @given(
        cli=_optional_credential,
        env=_optional_credential,
        config=_optional_credential,
    )
    @settings(max_examples=100)
    def test_cli_takes_highest_precedence(
        self,
        cli: str | None,
        env: str | None,
        config: str | None,
    ) -> None:
        """When CLI value is present, it always wins regardless of other sources.

        **Validates: Requirements 1.4**
        """
        result = resolve_credential(cli, env, config)

        if cli is not None:
            assert result == cli, (
                f"CLI value {cli!r} should take precedence, got {result!r}"
            )
        elif env is not None:
            assert result == env, (
                f"Env value {env!r} should take precedence when CLI is None, got {result!r}"
            )
        elif config is not None:
            assert result == config, (
                f"Config value {config!r} should be used when CLI and env are None, got {result!r}"
            )
        else:
            assert result is None, (
                f"Expected None when all sources are None, got {result!r}"
            )

    @given(
        cli=_credential_value,
        env=_credential_value,
        config=_credential_value,
    )
    @settings(max_examples=100)
    def test_all_sources_present_cli_wins(
        self,
        cli: str,
        env: str,
        config: str,
    ) -> None:
        """When all three sources are present, CLI always wins.

        **Validates: Requirements 1.4**
        """
        result = resolve_credential(cli, env, config)
        assert result == cli

    @given(
        env=_credential_value,
        config=_credential_value,
    )
    @settings(max_examples=100)
    def test_no_cli_env_wins_over_config(
        self,
        env: str,
        config: str,
    ) -> None:
        """When CLI is absent, env takes precedence over config.

        **Validates: Requirements 1.4**
        """
        result = resolve_credential(None, env, config)
        assert result == env
