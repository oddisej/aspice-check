"""Unit tests for core data model classes."""

import pytest

from aspice_eval.models import (
    VALID_RATINGS,
    CapabilityLevelResult,
    CompletenessReport,
    CriteriaEntry,
    CriteriaRating,
    EvaluationConfig,
    EvaluationResult,
    KBMetadata,
    ModelConfig,
    SDPDocument,
    ValidationResult,
)


class TestEvaluationConfigDefaults:
    """Verify EvaluationConfig defaults match ASPICE conventions."""

    def test_default_target_capability_level_is_3(self):
        config = EvaluationConfig()
        assert config.target_capability_level == 3

    def test_default_process_groups(self):
        config = EvaluationConfig()
        assert config.process_groups == ["SWE", "SYS", "MAN", "SUP"]

    def test_default_kb_path(self):
        config = EvaluationConfig()
        assert config.kb_path == "knowledge_base"

    def test_default_standard(self):
        config = EvaluationConfig()
        assert config.standard == "aspice"

    def test_default_output_path_is_none(self):
        config = EvaluationConfig()
        assert config.output_path is None

    def test_custom_values_override_defaults(self):
        config = EvaluationConfig(
            sdp_path="/tmp/sdp.md",
            target_capability_level=5,
            process_groups=["SWE"],
            kb_path="/custom/kb",
            standard="cmmi",
            output_path="/tmp/report.md",
        )
        assert config.target_capability_level == 5
        assert config.process_groups == ["SWE"]
        assert config.kb_path == "/custom/kb"
        assert config.standard == "cmmi"
        assert config.output_path == "/tmp/report.md"


class TestCriteriaRatingConstraint:
    """Verify CriteriaRating.rating is constrained to ASPICE values."""

    @pytest.mark.parametrize("rating", sorted(VALID_RATINGS))
    def test_valid_ratings_accepted(self, rating: str):
        cr = CriteriaRating(
            criteria_id="SWE.1-PA1.1-001",
            process_group="SWE",
            process_attribute="PA 1.1",
            capability_level=1,
            rating=rating,
        )
        assert cr.rating == rating

    @pytest.mark.parametrize(
        "bad_rating",
        [
            "fully achieved",
            "FULLY ACHIEVED",
            "Achieved",
            "None",
            "",
            "F",
            "L",
            "P",
            "N",
        ],
    )
    def test_invalid_ratings_rejected(self, bad_rating: str):
        with pytest.raises(ValueError, match="Invalid rating"):
            CriteriaRating(
                criteria_id="SWE.1-PA1.1-001",
                process_group="SWE",
                process_attribute="PA 1.1",
                capability_level=1,
                rating=bad_rating,
            )


class TestCriteriaEntry:
    """Verify CriteriaEntry instantiation."""

    def test_create_criteria_entry(self):
        entry = CriteriaEntry(
            process_group="SWE",
            process_id="SWE.1",
            process_name="Software Requirements Analysis",
            capability_level=2,
            process_attribute="PA 2.1",
            process_attribute_name="Performance Management",
            criteria_id="SWE.1-PA2.1-001",
            description="The process is planned.",
            expected_evidence=[
                {"type": "plan", "description": "A requirements plan"}
            ],
            evaluation_guidance="Look for a plan.",
        )
        assert entry.process_group == "SWE"
        assert entry.criteria_id == "SWE.1-PA2.1-001"
        assert entry.example_evidence == []

    def test_example_evidence_defaults_to_empty(self):
        entry = CriteriaEntry(
            process_group="MAN",
            process_id="MAN.3",
            process_name="Project Management",
            capability_level=1,
            process_attribute="PA 1.1",
            process_attribute_name="Process Performance",
            criteria_id="MAN.3-PA1.1-001",
            description="desc",
            expected_evidence=[{"type": "record", "description": "rec"}],
            evaluation_guidance="guidance",
        )
        assert entry.example_evidence == []


class TestOtherModels:
    """Verify remaining dataclass instantiation and defaults."""

    def test_capability_level_result(self):
        result = CapabilityLevelResult(
            process_group="SWE",
            achieved_level=2,
            target_level=3,
        )
        assert result.attribute_ratings == {}
        assert result.blocking_attributes == []

    def test_evaluation_result_defaults(self):
        result = EvaluationResult()
        assert result.ratings == []
        assert result.sdp_metadata == {}
        assert result.evaluation_timestamp == ""
        assert isinstance(result.config, EvaluationConfig)

    def test_validation_result_defaults(self):
        vr = ValidationResult()
        assert vr.is_valid is True
        assert vr.schema_errors == []
        assert vr.completeness_gaps == []
        assert vr.warnings == []

    def test_completeness_report_defaults(self):
        cr = CompletenessReport()
        assert cr.is_complete is True
        assert cr.missing_entries == []
        assert cr.total_expected == 0
        assert cr.total_found == 0

    def test_sdp_document_defaults(self):
        doc = SDPDocument()
        assert doc.content == ""
        assert doc.file_path == ""
        assert doc.section_headers == []
        assert doc.metadata == {}

    def test_kb_metadata(self):
        meta = KBMetadata(
            standard_name="Automotive SPICE",
            short_name="ASPICE",
            version="4.0",
            release_date="2023-12",
            source_references=[{"title": "VDA", "url": "https://example.com"}],
            license_note="Public summaries only.",
            kb_version="1.0.0",
            last_updated="2025-01-15",
            process_groups=[{"code": "SWE", "name": "Software Engineering"}],
            capability_levels=[{"level": 1, "name": "Performed"}],
            rating_scale=[{"rating": "Fully achieved", "abbreviation": "F"}],
        )
        assert meta.short_name == "ASPICE"
        assert meta.version == "4.0"

    def test_model_config_defaults(self):
        mc = ModelConfig()
        assert mc.provider == ""
        assert mc.model_name == ""
        assert mc.temperature == 0.0
        assert mc.max_tokens == 8192
        assert mc.api_key is None

    def test_model_config_with_api_key(self):
        mc = ModelConfig(
            provider="openai",
            model_name="gpt-4",
            temperature=0.7,
            max_tokens=8192,
            api_key="sk-test",
        )
        assert mc.provider == "openai"
        assert mc.api_key == "sk-test"
