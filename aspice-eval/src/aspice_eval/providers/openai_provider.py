"""OpenAI provider for the ASPICE evaluation tool.

Implements the ``OpenAIEvaluator`` class that uses the OpenAI Chat
Completions API to evaluate SDP documents against ASPICE criteria.

Requirements: 4.1, 4.5
"""

from __future__ import annotations

import os

from aspice_eval.evaluator import GapAnalysisEvaluator
from aspice_eval.exceptions import AIModelError
from aspice_eval.models import ModelConfig


class OpenAIEvaluator(GapAnalysisEvaluator):
    """Evaluator using the OpenAI Chat Completions API.

    The API key is resolved from ``config.api_key`` first, falling
    back to the ``OPENAI_API_KEY`` environment variable.

    Parameters
    ----------
    model_config:
        Configuration including ``model_name`` (e.g. ``"gpt-4o"``)
        and optionally ``api_key``.
    """

    def __init__(self, model_config: ModelConfig) -> None:
        super().__init__(model_config)
        try:
            from openai import OpenAI  # type: ignore[import-untyped]
        except ImportError as exc:
            raise AIModelError(
                "The 'openai' package is required for the OpenAI provider. "
                "Install it with: pip install aspice-eval[openai]",
                provider="openai",
                model_name=model_config.model_name,
            ) from exc

        api_key = model_config.api_key or os.environ.get("OPENAI_API_KEY")
        self._client = OpenAI(api_key=api_key)

    def _call_model(self, prompt: str) -> str:
        """Send a prompt to OpenAI and return the response text.

        Uses the Chat Completions API with ``response_format`` set to
        ``{"type": "json_object"}`` to encourage structured JSON output.

        Raises
        ------
        AIModelError
            On authentication errors, rate limits, or other OpenAI API
            exceptions.
        """
        try:
            response = self._client.chat.completions.create(
                model=self._model_config.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=self._model_config.temperature,
                max_tokens=self._model_config.max_tokens,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content
        except Exception as exc:
            exc_type = type(exc).__name__

            if "AuthenticationError" in exc_type:
                raise AIModelError(
                    f"OpenAI authentication failed: {exc}",
                    provider="openai",
                    model_name=self._model_config.model_name,
                ) from exc
            elif "RateLimitError" in exc_type:
                raise AIModelError(
                    f"OpenAI rate limit exceeded: {exc}",
                    provider="openai",
                    model_name=self._model_config.model_name,
                ) from exc
            else:
                raise AIModelError(
                    f"OpenAI API error: {exc}",
                    provider="openai",
                    model_name=self._model_config.model_name,
                ) from exc
