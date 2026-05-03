"""Shared test configuration and Hypothesis settings profiles."""

from hypothesis import settings

# CI profile: thorough testing with 100 examples per property
settings.register_profile("ci", max_examples=100)

# Dev profile: faster feedback with 50 examples per property
settings.register_profile("dev", max_examples=50)

# Default to CI profile for consistent test coverage
settings.load_profile("ci")
