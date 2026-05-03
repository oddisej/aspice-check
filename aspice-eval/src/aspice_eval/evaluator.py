"""Gap analysis evaluator for ASPICE SDP compliance assessment.

Provides an AI-powered evaluator that assesses SDP documents against
knowledge base criteria. The base class defines a generic interface
with a ``_call_model`` method that can be overridden for different
LLM providers. A ``MockEvaluator`` subclass is included for testing.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 6.3
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from aspice_eval.exceptions import AIModelError, AIResponseParseError
from aspice_eval.models import (
    VALID_RATINGS,
    CriteriaEntry,
    CriteriaRating,
    EvaluationConfig,
    EvaluationResult,
    ModelConfig,
    SDPDocument,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_RETRIES: int = 3
_BASE_BACKOFF_SECONDS: float = 1.0


class GapAnalysisEvaluator:
    """AI-powered evaluator that assesses SDP compliance against KB criteria.

    The evaluator constructs a structured prompt from the SDP content and
    criteria, sends it to an AI model via :meth:`_call_model`, and parses
    the JSON response into :class:`CriteriaRating` objects.

    Subclass and override :meth:`_call_model` to integrate with a specific
    LLM provider (OpenAI, Anthropic, Bedrock, etc.).

    Parameters
    ----------
    model_config:
        Configuration for the AI model (provider, model name, temperature, etc.).
    """

    def __init__(self, model_config: ModelConfig) -> None:
        self._model_config = model_config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        sdp: SDPDocument,
        criteria: list[CriteriaEntry],
        config: EvaluationConfig,
    ) -> EvaluationResult:
        """Evaluate the SDP against all provided criteria.

        Constructs a prompt with the SDP content and KB criteria as context,
        sends it to the AI model, and parses the response into per-criteria
        ratings. Implements retry with exponential backoff for transient
        AI model failures.

        When the combined prompt (SDP + all criteria) would exceed the
        model's context window, criteria are automatically split into
        batches by process group and evaluated separately. Results from
        all batches are merged into a single ``EvaluationResult``.

        Parameters
        ----------
        sdp:
            The parsed SDP document.
        criteria:
            List of criteria to evaluate against.
        config:
            Evaluation configuration (target level, groups, etc.).

        Returns
        -------
        EvaluationResult
            Per-criteria ratings with evidence, gaps, and recommendations.

        Raises
        ------
        AIModelError
            If the AI model call fails after all retry attempts.
        """
        max_ctx = self._model_config.max_context_tokens
        max_criteria_per_batch = 6

        # Token tracking
        total_input_tokens = 0
        total_output_tokens = 0
        num_batches = 0

        if len(criteria) <= max_criteria_per_batch:
            prompt = self._build_prompt(sdp, criteria, config)
            estimated = self._estimate_tokens(prompt)

            if estimated <= max_ctx:
                raw_response = self._call_model_with_retry(prompt)
                ratings = self._parse_response(raw_response, criteria)

                input_tok = self._estimate_tokens(prompt)
                output_tok = self._estimate_tokens(raw_response)

                return EvaluationResult(
                    ratings=ratings,
                    sdp_metadata={
                        "file_path": sdp.file_path,
                        "section_headers": sdp.section_headers,
                        "model_provider": self._model_config.provider,
                        "model_name": self._model_config.model_name,
                    },
                    evaluation_timestamp=datetime.now(timezone.utc).isoformat(),
                    config=config,
                    token_usage={
                        "input_tokens": input_tok,
                        "output_tokens": output_tok,
                        "total_tokens": input_tok + output_tok,
                        "num_batches": 1,
                    },
                )

        # Chunking required
        batches = self._chunk_criteria(criteria, sdp, max_ctx, max_criteria_per_batch)
        batch_results: list[EvaluationResult] = []

        for batch in batches:
            batch_prompt = self._build_prompt(sdp, batch, config)
            raw_response = self._call_model_with_retry(batch_prompt)

            input_tok = self._estimate_tokens(batch_prompt)
            output_tok = self._estimate_tokens(raw_response)
            total_input_tokens += input_tok
            total_output_tokens += output_tok
            num_batches += 1

            try:
                batch_ratings = self._parse_response(raw_response, batch)
            except AIResponseParseError:
                import sys
                batch_ids = [c.criteria_id for c in batch]
                print(
                    f"Warning: Failed to parse response for batch "
                    f"({len(batch)} criteria: {batch_ids[0]}..{batch_ids[-1]}). "
                    f"Skipping.",
                    file=sys.stderr,
                )
                continue

            batch_results.append(
                EvaluationResult(
                    ratings=batch_ratings,
                    sdp_metadata={
                        "file_path": sdp.file_path,
                        "section_headers": sdp.section_headers,
                        "model_provider": self._model_config.provider,
                        "model_name": self._model_config.model_name,
                    },
                    evaluation_timestamp=datetime.now(
                        timezone.utc
                    ).isoformat(),
                    config=config,
                )
            )

        merged = self._merge_results(batch_results)
        merged.token_usage = {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "total_tokens": total_input_tokens + total_output_tokens,
            "num_batches": num_batches,
        }
        return merged

    # ------------------------------------------------------------------
    # Token estimation and chunking
    # ------------------------------------------------------------------

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Estimate the number of tokens in a text string.

        Uses a simple heuristic of 4 characters per token, which is a
        conservative approximation for English text with code/JSON.

        Parameters
        ----------
        text:
            The text to estimate tokens for.

        Returns
        -------
        int
            Estimated token count.
        """
        return len(text) // 4

    def _chunk_criteria(
        self,
        criteria: list[CriteriaEntry],
        sdp: SDPDocument,
        max_context_tokens: int,
        max_criteria_per_batch: int = 15,
    ) -> list[list[CriteriaEntry]]:
        """Split criteria into batches for chunked evaluation.

        Groups criteria by ``process_id`` (e.g., SWE.1, SWE.2) and creates
        batches where each batch has at most ``max_criteria_per_batch``
        criteria and fits within the context window.

        Parameters
        ----------
        criteria:
            Full list of criteria to split.
        sdp:
            The SDP document (needed to estimate per-batch prompt size).
        max_context_tokens:
            Maximum tokens allowed per prompt.
        max_criteria_per_batch:
            Maximum number of criteria per batch (to keep output manageable).

        Returns
        -------
        list[list[CriteriaEntry]]
            List of criteria batches.
        """
        if not criteria:
            return []

        # Group criteria by process_id, preserving order of first appearance
        by_process: dict[str, list[CriteriaEntry]] = {}
        for entry in criteria:
            key = entry.process_id or entry.process_group
            by_process.setdefault(key, []).append(entry)

        # Estimate the base prompt size (SDP + instructions, without criteria)
        base_prompt = self._build_prompt(sdp, [], EvaluationConfig())
        base_tokens = self._estimate_tokens(base_prompt)

        batches: list[list[CriteriaEntry]] = []
        current_batch: list[CriteriaEntry] = []
        current_tokens = base_tokens

        for _process_id, process_criteria in by_process.items():
            # If a single process has more criteria than the batch limit,
            # split it into sub-batches of max_criteria_per_batch
            for sub_start in range(0, len(process_criteria), max_criteria_per_batch):
                sub_batch = process_criteria[sub_start : sub_start + max_criteria_per_batch]

                group_json = json.dumps(
                    [self._criteria_to_dict(c) for c in sub_batch],
                    indent=2,
                )
                group_tokens = self._estimate_tokens(group_json)

                would_exceed_tokens = (current_tokens + group_tokens) > max_context_tokens
                would_exceed_count = (len(current_batch) + len(sub_batch)) > max_criteria_per_batch

                if current_batch and (would_exceed_tokens or would_exceed_count):
                    batches.append(current_batch)
                    current_batch = list(sub_batch)
                    current_tokens = base_tokens + group_tokens
                else:
                    current_batch.extend(sub_batch)
                    current_tokens += group_tokens

        if current_batch:
            batches.append(current_batch)

        return batches

    @staticmethod
    def _merge_results(
        batch_results: list[EvaluationResult],
    ) -> EvaluationResult:
        """Merge evaluation results from multiple batches into one.

        Combines all ratings from all batches. Uses metadata from the
        first batch result for the merged result's metadata fields.

        Parameters
        ----------
        batch_results:
            List of ``EvaluationResult`` objects from individual batches.

        Returns
        -------
        EvaluationResult
            A single merged result containing all ratings.
        """
        if not batch_results:
            return EvaluationResult()

        all_ratings: list[CriteriaRating] = []
        for result in batch_results:
            all_ratings.extend(result.ratings)

        first = batch_results[0]
        return EvaluationResult(
            ratings=all_ratings,
            sdp_metadata=first.sdp_metadata,
            evaluation_timestamp=first.evaluation_timestamp,
            config=first.config,
        )

    # ------------------------------------------------------------------
    # Model interaction (override for real providers)
    # ------------------------------------------------------------------

    def _call_model(self, prompt: str) -> str:
        """Send a prompt to the AI model and return the raw response.

        Override this method in subclasses to integrate with a specific
        LLM provider. The default implementation raises ``AIModelError``
        to signal that no provider is configured.

        Parameters
        ----------
        prompt:
            The fully constructed evaluation prompt.

        Returns
        -------
        str
            The raw model response (expected to be a JSON array).

        Raises
        ------
        AIModelError
            If the model call fails.
        """
        raise AIModelError(
            "No AI model provider configured. "
            "Override _call_model() or use MockEvaluator for testing.",
            provider=self._model_config.provider,
            model_name=self._model_config.model_name,
        )

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        sdp: SDPDocument,
        criteria: list[CriteriaEntry],
        config: EvaluationConfig,
    ) -> str:
        """Construct a structured evaluation prompt.

        The prompt instructs the AI model to:
        1. Rate each criterion using the ASPICE rating scale.
        2. Cite specific SDP sections as evidence.
        3. Identify gaps where the SDP falls short.
        4. Provide remediation recommendations for each gap.

        Returns
        -------
        str
            The complete prompt string.
        """
        criteria_json = json.dumps(
            [self._criteria_to_dict(c) for c in criteria],
            indent=2,
        )

        return (
            "You are an Automotive SPICE (ASPICE) compliance assessor. "
            "Evaluate the following Software Development Process (SDP) document "
            "against the provided ASPICE criteria.\n\n"
            "## Instructions\n\n"
            "For each criterion, provide a JSON object with these fields:\n"
            "- criteria_id: The criterion identifier\n"
            "- rating: One of \"Fully achieved\", \"Largely achieved\", "
            "\"Partially achieved\", \"Not achieved\"\n"
            "- evidence_found: List of specific SDP sections/quotes that "
            "serve as evidence\n"
            "- gaps: List of specific gaps identified (empty if Fully achieved)\n"
            "- recommendations: List of remediation recommendations "
            "(must be non-empty when gaps is non-empty)\n"
            "- sdp_sections_assessed: List of SDP section headers assessed\n\n"
            "Return ONLY a JSON array of rating objects. No other text.\n\n"
            f"## Target Capability Level: {config.target_capability_level}\n\n"
            f"## Process Groups: {', '.join(config.process_groups)}\n\n"
            "## ASPICE Criteria\n\n"
            f"```json\n{criteria_json}\n```\n\n"
            "## SDP Document\n\n"
            f"```\n{sdp.content}\n```\n"
        )

    # ------------------------------------------------------------------
    # Retry logic
    # ------------------------------------------------------------------

    def _call_model_with_retry(self, prompt: str) -> str:
        """Call the model with exponential backoff retry on AIModelError.

        Parameters
        ----------
        prompt:
            The evaluation prompt.

        Returns
        -------
        str
            The raw model response.

        Raises
        ------
        AIModelError
            If all retry attempts are exhausted.
        """
        last_error: AIModelError | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                return self._call_model(prompt)
            except AIModelError as exc:
                last_error = exc
                if attempt < _MAX_RETRIES:
                    backoff = _BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
                    time.sleep(backoff)

        # All retries exhausted
        assert last_error is not None
        raise AIModelError(
            f"AI model call failed after {_MAX_RETRIES} attempts: "
            f"{last_error}",
            provider=self._model_config.provider,
            model_name=self._model_config.model_name,
            attempt=_MAX_RETRIES,
        )

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_response(
        self,
        raw_response: str,
        criteria: list[CriteriaEntry],
    ) -> list[CriteriaRating]:
        """Parse the AI model's JSON response into CriteriaRating objects.

        Handles malformed responses gracefully: if some entries parse
        successfully but others fail, the valid entries are returned as
        partial results. An ``AIResponseParseError`` is raised only when
        the entire response is unparseable.

        Parameters
        ----------
        raw_response:
            The raw JSON string from the model.
        criteria:
            The original criteria list (for cross-referencing).

        Returns
        -------
        list[CriteriaRating]
            Parsed ratings (may be partial if some entries failed).

        Raises
        ------
        AIResponseParseError
            If the response cannot be parsed as JSON at all.
        """
        # Build a lookup for criteria metadata
        criteria_lookup: dict[str, CriteriaEntry] = {
            c.criteria_id: c for c in criteria
        }

        # Preprocess: extract JSON from the response.
        # Models sometimes wrap JSON in markdown code fences or add preamble text.
        cleaned = self._extract_json(raw_response)

        if not cleaned:
            raise AIResponseParseError(
                "AI response is empty or contains no JSON content.",
                raw_response=raw_response,
            )

        # Try to parse the JSON response
        try:
            data = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError) as exc:
            raise AIResponseParseError(
                f"Failed to parse AI response as JSON: {exc}",
                raw_response=raw_response,
            ) from exc

        if not isinstance(data, list):
            raise AIResponseParseError(
                "Expected a JSON array of rating objects, "
                f"got {type(data).__name__}.",
                raw_response=raw_response,
            )

        ratings: list[CriteriaRating] = []
        parse_errors: list[str] = []

        for idx, item in enumerate(data):
            try:
                rating = self._parse_single_rating(item, criteria_lookup)
                ratings.append(rating)
            except (KeyError, ValueError, TypeError) as exc:
                parse_errors.append(f"Entry {idx}: {exc}")

        # If nothing parsed at all, raise
        if not ratings and parse_errors:
            raise AIResponseParseError(
                f"All {len(parse_errors)} rating entries failed to parse.",
                raw_response=raw_response,
                partial_results=[],
            )

        return ratings

    def _parse_single_rating(
        self,
        item: dict[str, Any],
        criteria_lookup: dict[str, CriteriaEntry],
    ) -> CriteriaRating:
        """Parse a single rating dict into a CriteriaRating.

        Enforces the invariant that non-empty gaps require non-empty
        recommendations.
        """
        criteria_id = item["criteria_id"]
        rating_value = item["rating"]

        # Validate rating value
        if rating_value not in VALID_RATINGS:
            raise ValueError(
                f"Invalid rating {rating_value!r} for {criteria_id}. "
                f"Must be one of: {', '.join(sorted(VALID_RATINGS))}"
            )

        evidence_found = item.get("evidence_found", [])
        gaps = item.get("gaps", [])
        recommendations = item.get("recommendations", [])
        sdp_sections = item.get("sdp_sections_assessed", [])

        # Enforce gap-recommendation invariant
        if gaps and not recommendations:
            recommendations = [
                f"Address identified gap: {gap}" for gap in gaps
            ]

        # Resolve process group and other metadata from criteria lookup
        entry = criteria_lookup.get(criteria_id)
        if entry is not None:
            process_group = entry.process_group
            process_attribute = entry.process_attribute
            capability_level = entry.capability_level
        else:
            # Fallback: extract from the item itself if provided
            process_group = item.get("process_group", "")
            process_attribute = item.get("process_attribute", "")
            capability_level = item.get("capability_level", 0)

        return CriteriaRating(
            criteria_id=criteria_id,
            process_group=process_group,
            process_attribute=process_attribute,
            capability_level=capability_level,
            rating=rating_value,
            evidence_found=evidence_found,
            gaps=gaps,
            recommendations=recommendations,
            sdp_sections_assessed=sdp_sections,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_json(text: str) -> str:
        """Extract JSON content from a model response.

        Handles common cases where the model wraps JSON in markdown
        code fences, adds preamble text, or returns truncated output.

        Parameters
        ----------
        text:
            The raw model response.

        Returns
        -------
        str
            The extracted JSON string, or the original text if no
            wrapper is detected.
        """
        import re

        stripped = text.strip()
        if not stripped:
            return ""

        # Case 1: markdown code fence ```json ... ``` or ``` ... ```
        fence_match = re.search(
            r"```(?:json)?\s*\n?(.*?)```",
            stripped,
            re.DOTALL,
        )
        if fence_match:
            return fence_match.group(1).strip()

        # Case 2: response starts with '[' — already JSON
        if stripped.startswith("["):
            return stripped

        # Case 3: find the first '[' and last ']' — extract the array
        first_bracket = stripped.find("[")
        last_bracket = stripped.rfind("]")
        if first_bracket != -1 and last_bracket > first_bracket:
            return stripped[first_bracket : last_bracket + 1]

        # Fallback: return as-is and let json.loads handle the error
        return stripped

    @staticmethod
    def _criteria_to_dict(entry: CriteriaEntry) -> dict[str, Any]:
        """Convert a CriteriaEntry to a dict for prompt serialization."""
        return {
            "criteria_id": entry.criteria_id,
            "process_group": entry.process_group,
            "process_id": entry.process_id,
            "process_name": entry.process_name,
            "capability_level": entry.capability_level,
            "process_attribute": entry.process_attribute,
            "description": entry.description,
            "expected_evidence": entry.expected_evidence,
            "evaluation_guidance": entry.evaluation_guidance,
        }


class MockEvaluator(GapAnalysisEvaluator):
    """Deterministic evaluator for testing — no AI model calls.

    Returns predictable ratings based on a simple heuristic:
    criteria at capability level 1 are rated "Fully achieved",
    level 2 as "Largely achieved", level 3 as "Partially achieved",
    and levels 4–5 as "Not achieved".

    Optionally accepts a custom response builder for fine-grained
    control in tests.
    """

    # Default rating by capability level
    _LEVEL_RATINGS: dict[int, str] = {
        1: "Fully achieved",
        2: "Largely achieved",
        3: "Partially achieved",
        4: "Not achieved",
        5: "Not achieved",
    }

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        *,
        custom_ratings: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(model_config or ModelConfig())
        self._custom_ratings = custom_ratings

    def _call_model(self, prompt: str) -> str:
        """Return a deterministic JSON response without calling any AI model.

        If ``custom_ratings`` were provided at construction, those are
        returned directly. Otherwise, a default rating is generated for
        each criterion found in the prompt.
        """
        if self._custom_ratings is not None:
            return json.dumps(self._custom_ratings)

        # Parse criteria from the prompt to generate deterministic ratings
        # The prompt embeds criteria as a JSON block between ```json and ```
        ratings: list[dict[str, Any]] = []
        try:
            json_start = prompt.index("```json\n") + len("```json\n")
            json_end = prompt.index("\n```\n\n## SDP Document")
            criteria_data = json.loads(prompt[json_start:json_end])

            for entry in criteria_data:
                cl = entry.get("capability_level", 1)
                rating_value = self._LEVEL_RATINGS.get(cl, "Not achieved")

                gaps: list[str] = []
                recommendations: list[str] = []
                if rating_value in ("Partially achieved", "Not achieved"):
                    gaps = [
                        f"Insufficient evidence for {entry.get('criteria_id', 'unknown')}"
                    ]
                    recommendations = [
                        f"Enhance documentation to address {entry.get('process_attribute', 'unknown')}"
                    ]

                ratings.append(
                    {
                        "criteria_id": entry.get("criteria_id", ""),
                        "rating": rating_value,
                        "evidence_found": [
                            "Section found in SDP"
                        ] if rating_value != "Not achieved" else [],
                        "gaps": gaps,
                        "recommendations": recommendations,
                        "sdp_sections_assessed": ["Overview"],
                    }
                )
        except (ValueError, json.JSONDecodeError):
            # If prompt parsing fails, return empty array
            pass

        return json.dumps(ratings)
