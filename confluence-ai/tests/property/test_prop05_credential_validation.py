"""Property 5: Credential Validation (export side).

**Validates: Requirements 6.6, 6.7, 7.7**

For any call to :func:`confluence_ai.export.export_page` where either
``email`` or ``api_token`` is empty or ``None``, the function SHALL raise
:class:`~confluence_ai.exceptions.AuthenticationError` with a message that
names the missing field. This check runs *before* the URL is validated and
before any network I/O is attempted.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from confluence_ai.exceptions import AuthenticationError
from confluence_ai.export import export_page


# A Confluence-shaped URL — valid enough to pass URL parsing, so any
# AuthenticationError we see must be coming from credential validation
# rather than URL parsing. The export function validates credentials
# *before* parsing the URL, but we still use a realistic URL to guard
# against regressions in the ordering contract.
_VALID_URL = (
    "https://acme.atlassian.net/wiki/spaces/ENG/pages/123456/My-Page"
)

# "Empty-ish" credential values: Python falsy strings plus None. These
# are the values the function must reject at the credential check.
_empty_credential_st = st.one_of(
    st.none(),
    st.just(""),
)

# Non-empty credentials — used as the "good" value on the opposite field
# so we can isolate which field triggers the error.
_nonempty_credential_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=32,
).filter(lambda s: s.strip() != "")


class TestProperty05CredentialValidation:
    """Property 5: Credential validation rejects empty email / api_token."""

    @given(
        email=_empty_credential_st,
        api_token=_nonempty_credential_st,
    )
    @settings(max_examples=50, deadline=None)
    def test_empty_email_raises_authentication_error(
        self,
        email: str | None,
        api_token: str,
    ) -> None:
        """Empty or None ``email`` raises ``AuthenticationError`` naming the field.

        The error must fire before any filesystem or network I/O, so
        the output directory is never touched and we pass a dummy path.

        **Validates: Requirements 6.6**
        """
        with pytest.raises(AuthenticationError) as exc_info:
            export_page(
                _VALID_URL,
                "/tmp/never-written",
                email=email,  # type: ignore[arg-type]
                api_token=api_token,
            )
        # The message must name the missing field so the caller can fix it.
        assert "email" in str(exc_info.value).lower(), (
            f"AuthenticationError message should name 'email'; "
            f"got: {exc_info.value!s}"
        )

    @given(
        email=_nonempty_credential_st,
        api_token=_empty_credential_st,
    )
    @settings(max_examples=50, deadline=None)
    def test_empty_api_token_raises_authentication_error(
        self,
        email: str,
        api_token: str | None,
    ) -> None:
        """Empty or None ``api_token`` raises ``AuthenticationError`` naming the field.

        **Validates: Requirements 6.6**
        """
        with pytest.raises(AuthenticationError) as exc_info:
            export_page(
                _VALID_URL,
                "/tmp/never-written",
                email=email,
                api_token=api_token,  # type: ignore[arg-type]
            )
        message = str(exc_info.value).lower()
        assert "api" in message and "token" in message, (
            f"AuthenticationError message should name 'api_token' / "
            f"'API token'; got: {exc_info.value!s}"
        )

    @given(
        email=_empty_credential_st,
        api_token=_empty_credential_st,
    )
    @settings(max_examples=50, deadline=None)
    def test_both_credentials_empty_raises_authentication_error(
        self,
        email: str | None,
        api_token: str | None,
    ) -> None:
        """When both credentials are empty, ``AuthenticationError`` is raised.

        The exact field named does not matter — what matters is that
        some ``AuthenticationError`` is raised before any network I/O.

        **Validates: Requirements 6.6**
        """
        with pytest.raises(AuthenticationError):
            export_page(
                _VALID_URL,
                "/tmp/never-written",
                email=email,  # type: ignore[arg-type]
                api_token=api_token,  # type: ignore[arg-type]
            )
