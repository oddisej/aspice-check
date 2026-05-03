"""Unit tests for prompt chunking logic in GapAnalysisEvaluator.

Tests token estimation, criteria batching by process group, result
merging, and the evaluate() method's chunking integration.

Requirements: 4.1, 4.4
"""

from __future__ import annotations

from aspice_eval.evaluator import GapAnalysisEvaluator, MockEvaluator
from aspice_eval.models import (
    CriteriaEntry,
    CriteriaRating,
    EvaluationConfig,
    EvaluationResult,
    ModelConfig,
    SDPDocument,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_criteria_entry(
    process_group: str = "SWE",
    process_id: str = "SWE.1",
    capability_level: int = 1,
    criteria_id: str = "SWE.1-PA1.1-001",
) -> CriteriaEntry:
    """Create a minimal CriteriaEntry for testing."""
    return CriteriaEntry(
        process_group=process_group,
        process_id=process_id,
        process_name=f"{process_id} Process",
        capability_level=capability_level,
        process_attribute=f"PA {capability_level}.1",
        process_attribute_name=f"Attribute {capability_level}.1",
        criteria_id=criteria_id,
        description=f"Description for {criteria_id}",
        expected_evidence=[{"type": "document", "description": "Evidence"}],
        evaluation_guidance=f"Guidance for {criteria_id}",
    )


def _make_sdp(content: str = "# SDP\n\nSample content.") -> SDPDocument:
    """Create a minimal SDPDocument for testing."""
    return SDPDocument(
        content=content,
        file_path="test.md",
        section_headers=["SDP"],
    )


# ---------------------------------------------------------------------------
# Token estimation tests
# ---------------------------------------------------------------------------


class TestEstimateTokens:
    """Tests for _estimate_tokens using the 4 chars/token heuristic."""

    def test_empty_string(self) -> None:
        assert GapAnalysisEvaluator._estimate_tokens("") == 0

    def test_four_chars_equals_one_token(self) -> None:
        assert GapAnalysisEvaluator._estimate_tokens("abcd") == 1

    def test_eight_chars_equals_two_tokens(self) -> None:
        assert GapAnalysisEvaluator._estimate_tokens("abcdefgh") == 2

    def test_partial_token_truncated(self) -> None:
        # 7 chars -> 7 // 4 = 1 token (integer division)
        assert GapAnalysisEvaluator._estimate_tokens("abcdefg") == 1

    def test_known_length(self) -> None:
        text = "a" * 400
        assert GapAnalysisEvaluator._estimate_tokens(text) == 100

    def test_single_char(self) -> None:
        assert GapAnalysisEvaluator._estimate_tokens("x") == 0


# ---------------------------------------------------------------------------
# Chunking tests
# ---------------------------------------------------------------------------


class TestChunkCriteria:
    """Tests for _chunk_criteria splitting by process group."""

    def test_small_criteria_single_batch(self) -> None:
        """When all criteria fit within the context window, return one batch."""
        evaluator = MockEvaluator(ModelConfig(max_context_tokens=100_000))
        sdp = _make_sdp()
        criteria = [
            _make_criteria_entry("SWE", "SWE.1", 1, "SWE.1-PA1.1-001"),
            _make_criteria_entry("SYS", "SYS.1", 1, "SYS.1-PA1.1-001"),
        ]

        batches = evaluator._chunk_criteria(criteria, sdp, 100_000)

        assert len(batches) == 1
        assert len(batches[0]) == 2

    def test_large_criteria_split_by_group(self) -> None:
        """When criteria exceed the context window, split by process group."""
        evaluator = MockEvaluator(ModelConfig(max_context_tokens=100_000))
        sdp = _make_sdp()

        # Create criteria for two groups
        swe_criteria = [
            _make_criteria_entry("SWE", "SWE.1", i, f"SWE.1-PA{i}.1-001")
            for i in range(1, 4)
        ]
        sys_criteria = [
            _make_criteria_entry("SYS", "SYS.1", i, f"SYS.1-PA{i}.1-001")
            for i in range(1, 4)
        ]
        criteria = swe_criteria + sys_criteria

        # Use a very small context window to force splitting
        batches = evaluator._chunk_criteria(criteria, sdp, 500)

        # Should produce multiple batches
        assert len(batches) >= 2

        # All criteria should be present across batches
        all_ids = set()
        for batch in batches:
            for c in batch:
                all_ids.add(c.criteria_id)

        expected_ids = {c.criteria_id for c in criteria}
        assert all_ids == expected_ids

    def test_each_batch_groups_by_process_group(self) -> None:
        """Criteria within a batch should come from complete process groups."""
        evaluator = MockEvaluator(ModelConfig(max_context_tokens=100_000))
        sdp = _make_sdp()

        criteria = [
            _make_criteria_entry("SWE", "SWE.1", 1, "SWE.1-PA1.1-001"),
            _make_criteria_entry("SWE", "SWE.2", 1, "SWE.2-PA1.1-001"),
            _make_criteria_entry("SYS", "SYS.1", 1, "SYS.1-PA1.1-001"),
            _make_criteria_entry("MAN", "MAN.3", 1, "MAN.3-PA1.1-001"),
        ]

        # Force splitting so each group is its own batch
        batches = evaluator._chunk_criteria(criteria, sdp, 500)

        # Each batch should contain criteria from consistent groups
        for batch in batches:
            groups_in_batch = {c.process_group for c in batch}
            # A batch may contain multiple groups, but each group's
            # criteria should be fully contained (not split across batches)
            for group in groups_in_batch:
                group_criteria_in_batch = [
                    c for c in batch if c.process_group == group
                ]
                group_criteria_total = [
                    c for c in criteria if c.process_group == group
                ]
                assert group_criteria_in_batch == group_criteria_total

    def test_empty_criteria_returns_empty(self) -> None:
        """Empty criteria list produces no batches."""
        evaluator = MockEvaluator(ModelConfig(max_context_tokens=100_000))
        sdp = _make_sdp()

        batches = evaluator._chunk_criteria([], sdp, 100_000)

        assert batches == []


# ---------------------------------------------------------------------------
# Merge results tests
# ---------------------------------------------------------------------------


class TestMergeResults:
    """Tests for _merge_results combining batch results."""

    def test_merge_combines_all_ratings(self) -> None:
        """Merged result contains all ratings from all batches."""
        rating_a = CriteriaRating(
            criteria_id="SWE.1-PA1.1-001",
            process_group="SWE",
            process_attribute="PA 1.1",
            capability_level=1,
            rating="Fully achieved",
        )
        rating_b = CriteriaRating(
            criteria_id="SYS.1-PA1.1-001",
            process_group="SYS",
            process_attribute="PA 1.1",
            capability_level=1,
            rating="Largely achieved",
        )

        result_a = EvaluationResult(
            ratings=[rating_a],
            sdp_metadata={"file_path": "test.md"},
            evaluation_timestamp="2025-01-01T00:00:00Z",
            config=EvaluationConfig(),
        )
        result_b = EvaluationResult(
            ratings=[rating_b],
            sdp_metadata={"file_path": "test.md"},
            evaluation_timestamp="2025-01-01T00:00:01Z",
            config=EvaluationConfig(),
        )

        merged = GapAnalysisEvaluator._merge_results([result_a, result_b])

        assert len(merged.ratings) == 2
        ids = {r.criteria_id for r in merged.ratings}
        assert ids == {"SWE.1-PA1.1-001", "SYS.1-PA1.1-001"}

    def test_merge_preserves_first_batch_metadata(self) -> None:
        """Merged result uses metadata from the first batch."""
        result_a = EvaluationResult(
            ratings=[],
            sdp_metadata={"file_path": "first.md"},
            evaluation_timestamp="2025-01-01T00:00:00Z",
            config=EvaluationConfig(sdp_path="first.md"),
        )
        result_b = EvaluationResult(
            ratings=[],
            sdp_metadata={"file_path": "second.md"},
            evaluation_timestamp="2025-01-01T00:00:01Z",
            config=EvaluationConfig(sdp_path="second.md"),
        )

        merged = GapAnalysisEvaluator._merge_results([result_a, result_b])

        assert merged.sdp_metadata == {"file_path": "first.md"}
        assert merged.evaluation_timestamp == "2025-01-01T00:00:00Z"
        assert merged.config.sdp_path == "first.md"

    def test_merge_empty_list_returns_empty_result(self) -> None:
        """Merging an empty list returns a default EvaluationResult."""
        merged = GapAnalysisEvaluator._merge_results([])

        assert merged.ratings == []
        assert merged.sdp_metadata == {}
        assert merged.evaluation_timestamp == ""

    def test_merge_single_batch_returns_same_ratings(self) -> None:
        """Merging a single batch returns its ratings unchanged."""
        rating = CriteriaRating(
            criteria_id="MAN.3-PA1.1-001",
            process_group="MAN",
            process_attribute="PA 1.1",
            capability_level=1,
            rating="Partially achieved",
            gaps=["Missing plan"],
            recommendations=["Create a plan"],
        )
        result = EvaluationResult(
            ratings=[rating],
            sdp_metadata={"file_path": "test.md"},
            evaluation_timestamp="2025-01-01T00:00:00Z",
            config=EvaluationConfig(),
        )

        merged = GapAnalysisEvaluator._merge_results([result])

        assert len(merged.ratings) == 1
        assert merged.ratings[0].criteria_id == "MAN.3-PA1.1-001"

    def test_merge_multiple_batches_preserves_all_fields(self) -> None:
        """Merged ratings preserve all fields (gaps, recommendations, etc.)."""
        rating_with_gaps = CriteriaRating(
            criteria_id="SWE.1-PA2.1-001",
            process_group="SWE",
            process_attribute="PA 2.1",
            capability_level=2,
            rating="Partially achieved",
            evidence_found=["Section 3"],
            gaps=["Missing metrics"],
            recommendations=["Add metrics tracking"],
            sdp_sections_assessed=["Section 3"],
        )
        rating_full = CriteriaRating(
            criteria_id="SYS.1-PA1.1-001",
            process_group="SYS",
            process_attribute="PA 1.1",
            capability_level=1,
            rating="Fully achieved",
            evidence_found=["Section 1", "Section 2"],
        )

        result_a = EvaluationResult(ratings=[rating_with_gaps])
        result_b = EvaluationResult(ratings=[rating_full])

        merged = GapAnalysisEvaluator._merge_results([result_a, result_b])

        swe_rating = next(
            r for r in merged.ratings if r.criteria_id == "SWE.1-PA2.1-001"
        )
        assert swe_rating.gaps == ["Missing metrics"]
        assert swe_rating.recommendations == ["Add metrics tracking"]
        assert swe_rating.evidence_found == ["Section 3"]

        sys_rating = next(
            r for r in merged.ratings if r.criteria_id == "SYS.1-PA1.1-001"
        )
        assert sys_rating.rating == "Fully achieved"
        assert sys_rating.evidence_found == ["Section 1", "Section 2"]


# ---------------------------------------------------------------------------
# Integration: evaluate() with chunking
# ---------------------------------------------------------------------------


class TestEvaluateWithChunking:
    """Tests that evaluate() uses chunking when the prompt exceeds the context window."""

    def test_small_document_not_chunked(self) -> None:
        """A small SDP + criteria set should produce a single-call evaluation."""
        config = ModelConfig(max_context_tokens=100_000)
        evaluator = MockEvaluator(config)
        sdp = _make_sdp("# Small SDP\n\nShort content.")
        criteria = [
            _make_criteria_entry("SWE", "SWE.1", 1, "SWE.1-PA1.1-001"),
        ]
        eval_config = EvaluationConfig(
            sdp_path="test.md",
            process_groups=["SWE"],
        )

        result = evaluator.evaluate(sdp, criteria, eval_config)

        assert len(result.ratings) == 1
        assert result.ratings[0].criteria_id == "SWE.1-PA1.1-001"

    def test_large_document_chunked(self) -> None:
        """When the prompt exceeds max_context_tokens, chunking kicks in."""
        # Use a very small context window to force chunking
        config = ModelConfig(max_context_tokens=500)
        evaluator = MockEvaluator(config)
        sdp = _make_sdp("# SDP\n\n" + "Content. " * 100)
        criteria = [
            _make_criteria_entry("SWE", "SWE.1", 1, "SWE.1-PA1.1-001"),
            _make_criteria_entry("SYS", "SYS.1", 1, "SYS.1-PA1.1-001"),
            _make_criteria_entry("MAN", "MAN.3", 1, "MAN.3-PA1.1-001"),
        ]
        eval_config = EvaluationConfig(
            sdp_path="test.md",
            process_groups=["SWE", "SYS", "MAN"],
        )

        result = evaluator.evaluate(sdp, criteria, eval_config)

        # All criteria should be evaluated regardless of chunking
        result_ids = {r.criteria_id for r in result.ratings}
        expected_ids = {c.criteria_id for c in criteria}
        assert result_ids == expected_ids

    def test_max_context_tokens_configurable(self) -> None:
        """max_context_tokens can be set via ModelConfig."""
        config = ModelConfig(max_context_tokens=50_000)
        assert config.max_context_tokens == 50_000

    def test_default_max_context_tokens(self) -> None:
        """Default max_context_tokens is 100,000."""
        config = ModelConfig()
        assert config.max_context_tokens == 100_000
