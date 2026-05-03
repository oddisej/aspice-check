"""Property 15: Configuration accepts all valid parameter combinations.

Generate random target levels (1–5) and non-empty subsets of supported process
groups; verify ``EvaluationConfig`` accepts without error.  Verify default
target level is 3 when unspecified.

**Validates: Requirements 7.1, 7.3**
"""

from hypothesis import given, strategies as st

from aspice_eval.models import EvaluationConfig

SUPPORTED_GROUPS = ["SWE", "SYS", "MAN", "SUP"]

# Strategy: non-empty subsets of supported process groups
process_group_subsets = (
    st.lists(
        st.sampled_from(SUPPORTED_GROUPS),
        min_size=1,
        max_size=len(SUPPORTED_GROUPS),
    )
    .map(lambda xs: list(dict.fromkeys(xs)))  # deduplicate, preserve order
    .filter(lambda xs: len(xs) >= 1)
)


class TestProperty15ConfigValidation:
    """Property 15: Configuration accepts all valid parameter combinations."""

    @given(
        target_level=st.integers(min_value=1, max_value=5),
        groups=process_group_subsets,
    )
    def test_accepts_all_valid_combinations(
        self, target_level: int, groups: list[str]
    ) -> None:
        """EvaluationConfig accepts any target level 1-5 with any
        non-empty subset of supported process groups without error."""
        config = EvaluationConfig(
            target_capability_level=target_level,
            process_groups=groups,
        )
        assert config.target_capability_level == target_level
        assert config.process_groups == groups

    def test_default_target_level_is_3(self) -> None:
        """When no target level is specified, default is 3."""
        config = EvaluationConfig()
        assert config.target_capability_level == 3

    @given(groups=process_group_subsets)
    def test_default_target_level_with_custom_groups(
        self, groups: list[str]
    ) -> None:
        """When only process groups are specified, target level defaults to 3."""
        config = EvaluationConfig(process_groups=groups)
        assert config.target_capability_level == 3
        assert config.process_groups == groups
