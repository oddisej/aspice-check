"""Anthropic provider for the ASPICE evaluation tool.

Implements the ``AnthropicEvaluator`` class that uses the Anthropic
Messages API to evaluate SDP documents against ASPICE criteria.

Requirements: 4.1, 4.5
"""

from __future__ import annotations

import os

from aspice_eval.evaluator import GapAnalysisEvaluator
from aspice_eval.exceptions import AIModelError
from aspice_eval.models import ModelConfig


class AnthropicEvaluator(GapAnalysisEvaluator):
    """Evaluator using the Anthropic Messages API.

    The API key is resolved from ``config.api_key`` first, falling
    back to the ``ANTHROPIC_API_KEY`` environment variable.

    Parameters
    ----------
    model_config:
        Configuration including ``model_name`` (e.g.
        ``"claude-sonnet-4-20250514"``) and optionally ``api_key``.
    """

    def __init__(self, model_config: ModelConfig) -> None:
        super().__init__(model_config)
        try:
            import anthropic as anthropic_mod  # type: ignore[import-untyped]
        except ImportError as exc:
            raise AIModelError(
                "The 'anthropic' package is required for the Anthropic provider. "
                "Install it with: pip install aspice-eval[anthropic]",
                provider="anthropic",
                model_name=model_config.model_name,
            ) from exc

        api_key = model_config.api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client = anthropic_mod.Anthropic(api_key=api_key)

    def _call_model(self, prompt: str) -> str:
        """Send a prompt to Anthropic and return the response text.

        Uses the Messages API which is the primary interface for
        Claude models.

        Raises
        ------
        AIModelError
            On authentication errors, rate limits, or other Anthropic
            API exceptions.
        """
        try:
            response = self._client.messages.create(
                model=self._model_config.model_name,
                max_tokens=self._model_config.max_tokens,
                temperature=self._model_config.temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as exc:
            exc_type = type(exc).__name__

            if "AuthenticationError" in exc_type:
                raise AIModelError(
                    f"Anthropic authentication failed: {exc}",
                    provider="anthropic",
                    model_name=self._model_config.model_name,
                ) from exc
            elif "RateLimitError" in exc_type:
                raise AIModelError(
                    f"Anthropic rate limit exceeded: {exc}",
                    provider="anthropic",
                    model_name=self._model_config.model_name,
                ) from exc
            else:
                raise AIModelError(
                    f"Anthropic API error: {exc}",
                    provider="anthropic",
                    model_name=self._model_config.model_name,
                ) from exc
