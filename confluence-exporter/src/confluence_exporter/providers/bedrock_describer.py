"""Amazon Bedrock image describer provider.

Implements ``BedrockImageDescriber`` using the Bedrock Runtime Converse API
with image content blocks for multimodal image description. Consistent with
the ``aspice-eval`` Bedrock provider pattern.

Requirements: 6.1, 6.5
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import os

from confluence_exporter.describer import ImageDescriber
from confluence_exporter.exceptions import ImageDescriptionError
from confluence_exporter.models import ImageContext, ImageDescriberConfig

logger = logging.getLogger(__name__)


class BedrockImageDescriber(ImageDescriber):
    """Image describer using Amazon Bedrock's Converse API.

    Uses the Converse API which provides a unified interface across all
    Bedrock-hosted models, including multimodal image support.

    Authentication uses the standard AWS credential chain (environment
    variables, ~/.aws/credentials, IAM role, etc.) — no explicit API key
    is needed.

    Parameters
    ----------
    config:
        Configuration including ``model`` (the Bedrock model ID, e.g.
        ``"anthropic.claude-sonnet-4-20250514-v1:0"``) and ``region``
        (AWS region, defaults to ``"us-east-1"``).
    """

    def __init__(self, config: ImageDescriberConfig) -> None:
        super().__init__(config)
        try:
            import boto3  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImageDescriptionError(
                image_path="",
                provider="bedrock",
                message=(
                    "The 'boto3' package is required for the Bedrock "
                    "provider. Install it with: "
                    "pip install confluence-exporter[bedrock]"
                ),
            ) from exc

        try:
            self._client = boto3.client(
                "bedrock-runtime",
                region_name=config.region or "us-east-1",
            )
        except Exception as exc:
            # Catch credential resolution errors (e.g. missing CRT dependency,
            # no AWS credentials configured, SSO session expired)
            raise ImageDescriptionError(
                image_path="",
                provider="bedrock",
                message=(
                    f"Failed to initialize Bedrock client: {exc}. "
                    "Ensure AWS credentials are configured and try: "
                    "pip install 'botocore[crt]'"
                ),
            ) from exc
        self._model_id = config.model

    def describe(self, image_path: str, context: ImageContext) -> str:
        """Send image to Bedrock with a description prompt.

        Reads the image as base64 and sends it via the Bedrock Converse
        API with an image content block alongside the text prompt.
        For Gliffy diagrams the prompt emphasises process flow elements.

        Maps boto3 ``ClientError`` subtypes to ``ImageDescriptionError``:
        - ``ThrottlingException`` → retryable error message
        - ``AccessDeniedException`` → access denied message
        - ``ModelNotFoundError`` / ``ValidationException`` → model not found
        - Other errors → generic Bedrock API error

        Raises
        ------
        ImageDescriptionError
            On any Bedrock API failure.
        """
        prompt = self._build_prompt(context)
        image_bytes = self._read_image_bytes(image_path)
        media_type = self._detect_media_type(image_path)

        try:
            response = self._client.converse(
                modelId=self._model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "image": {
                                    "format": _media_type_to_format(media_type),
                                    "source": {
                                        "bytes": image_bytes,
                                    },
                                },
                            },
                            {
                                "text": prompt,
                            },
                        ],
                    }
                ],
                inferenceConfig={
                    "temperature": self._config.temperature,
                    "maxTokens": self._config.max_tokens,
                },
            )
            return response["output"]["message"]["content"][0]["text"]
        except Exception as exc:
            error_code = ""
            if hasattr(exc, "response"):
                error_code = exc.response.get("Error", {}).get("Code", "")  # type: ignore[union-attr]

            if error_code == "ThrottlingException":
                raise ImageDescriptionError(
                    image_path=image_path,
                    provider="bedrock",
                    message=f"Bedrock rate limit exceeded: {exc}",
                ) from exc
            elif error_code == "AccessDeniedException":
                raise ImageDescriptionError(
                    image_path=image_path,
                    provider="bedrock",
                    message=(
                        f"Access denied to Bedrock model "
                        f"'{self._model_id}': {exc}"
                    ),
                ) from exc
            elif error_code in ("ModelNotFoundError", "ValidationException"):
                raise ImageDescriptionError(
                    image_path=image_path,
                    provider="bedrock",
                    message=(
                        f"Bedrock model '{self._model_id}' not found "
                        f"or invalid: {exc}"
                    ),
                ) from exc
            else:
                raise ImageDescriptionError(
                    image_path=image_path,
                    provider="bedrock",
                    message=f"Bedrock API error: {exc}",
                ) from exc

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_image_bytes(image_path: str) -> bytes:
        """Read an image file and return its raw bytes."""
        try:
            with open(image_path, "rb") as f:
                return f.read()
        except OSError as exc:
            raise ImageDescriptionError(
                image_path=image_path,
                provider="bedrock",
                message=f"Cannot read image file: {exc}",
            ) from exc

    @staticmethod
    def _detect_media_type(image_path: str) -> str:
        """Detect the MIME type of an image file."""
        mime_type, _ = mimetypes.guess_type(image_path)
        return mime_type or "image/png"


def _media_type_to_format(media_type: str) -> str:
    """Convert a MIME type to the Bedrock Converse API image format string.

    Bedrock expects: ``"png"``, ``"jpeg"``, ``"gif"``, or ``"webp"``.
    """
    mapping = {
        "image/png": "png",
        "image/jpeg": "jpeg",
        "image/jpg": "jpeg",
        "image/gif": "gif",
        "image/webp": "webp",
    }
    return mapping.get(media_type, "png")
