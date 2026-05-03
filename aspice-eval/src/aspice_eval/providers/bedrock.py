"""Amazon Bedrock provider for the ASPICE evaluation tool.

Implements the ``BedrockEvaluator`` class that uses the Bedrock
Runtime Converse API to evaluate SDP documents against ASPICE
criteria.

Requirements: 4.1, 4.5
"""

from __future__ import annotations

from aspice_eval.evaluator import GapAnalysisEvaluator
from aspice_eval.exceptions import AIModelError
from aspice_eval.models import ModelConfig


class BedrockEvaluator(GapAnalysisEvaluator):
    """Evaluator using Amazon Bedrock's Converse API.

    Parameters
    ----------
    model_config:
        Configuration including ``model_name`` (the Bedrock model ID)
        and ``region`` (AWS region, defaults to ``"us-east-1"``).
    """

    def __init__(self, model_config: ModelConfig) -> None:
        super().__init__(model_config)
        try:
            import boto3  # type: ignore[import-untyped]
        except ImportError as exc:
            raise AIModelError(
                "The 'boto3' package is required for the Bedrock provider. "
                "Install it with: pip install aspice-eval[bedrock]",
                provider="bedrock",
                model_name=model_config.model_name,
            ) from exc

        self._client = boto3.client(
            "bedrock-runtime",
            region_name=model_config.region or "us-east-1",
        )
        self._model_id = model_config.model_name

    def _call_model(self, prompt: str) -> str:
        """Send a prompt to Amazon Bedrock and return the response text.

        Uses the Converse API which provides a unified interface across
        all Bedrock-hosted models.

        Raises
        ------
        AIModelError
            On throttling, access denied, model not found, or other
            boto3 ``ClientError`` exceptions.
        """
        try:
            response = self._client.converse(
                modelId=self._model_id,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={
                    "temperature": self._model_config.temperature,
                    "maxTokens": self._model_config.max_tokens,
                },
            )
            return response["output"]["message"]["content"][0]["text"]
        except Exception as exc:
            # Map boto3 ClientError subtypes to AIModelError
            error_code = ""
            if hasattr(exc, "response"):
                error_code = exc.response.get("Error", {}).get("Code", "")  # type: ignore[union-attr]

            if error_code == "ThrottlingException":
                raise AIModelError(
                    f"Bedrock rate limit exceeded: {exc}",
                    provider="bedrock",
                    model_name=self._model_id,
                ) from exc
            elif error_code == "AccessDeniedException":
                raise AIModelError(
                    f"Access denied to Bedrock model '{self._model_id}': {exc}",
                    provider="bedrock",
                    model_name=self._model_id,
                ) from exc
            elif error_code in ("ModelNotFoundError", "ValidationException"):
                raise AIModelError(
                    f"Bedrock model '{self._model_id}' not found or invalid: {exc}",
                    provider="bedrock",
                    model_name=self._model_id,
                ) from exc
            else:
                raise AIModelError(
                    f"Bedrock API error: {exc}",
                    provider="bedrock",
                    model_name=self._model_id,
                ) from exc
