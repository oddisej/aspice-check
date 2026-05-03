"""Core data model classes for the ASPICE evaluation tool.

Defines dataclasses for knowledge base entries, evaluation results,
configuration, and validation outputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Valid ASPICE rating values
# ---------------------------------------------------------------------------

VALID_RATINGS: frozenset[str] = frozenset(
    {
        "Fully achieved",
        "Largely achieved",
        "Partially achieved",
        "Not achieved",
    }
)


# ---------------------------------------------------------------------------
# Knowledge Base models
# ---------------------------------------------------------------------------


@dataclass
class CriteriaEntry:
    """A single evaluable criterion in the knowledge base."""

    process_group: str
    process_id: str
    process_name: str
    capability_level: int
    process_attribute: str
    process_attribute_name: str
    criteria_id: str
    description: str
    expected_evidence: list[dict[str, str]]
    evaluation_guidance: str
    example_evidence: list[str] = field(default_factory=list)


@dataclass
class KBMetadata:
    """Metadata for a loaded standard in the knowledge base."""

    standard_name: str
    short_name: str
    version: str
    release_date: str
    source_references: list[dict[str, str]]
    license_note: str
    kb_version: str
    last_updated: str
    process_groups: list[dict[str, Any]]
    capability_levels: list[dict[str, Any]]
    rating_scale: list[dict[str, str]]


# ---------------------------------------------------------------------------
# Evaluation models
# ---------------------------------------------------------------------------


@dataclass
class CriteriaRating:
    """Result of evaluating a single criteria entry against the SDP.

    The ``rating`` field is validated on creation and must be one of the four
    ASPICE rating values defined in :data:`VALID_RATINGS`.
    """

    criteria_id: str
    process_group: str
    process_attribute: str
    capability_level: int
    rating: str
    evidence_found: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    sdp_sections_assessed: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.rating not in VALID_RATINGS:
            raise ValueError(
                f"Invalid rating {self.rating!r}. "
                f"Must be one of: {', '.join(sorted(VALID_RATINGS))}"
            )


@dataclass
class CapabilityLevelResult:
    """Capability level determination for a single process group."""

    process_group: str
    achieved_level: int
    target_level: int
    attribute_ratings: dict[str, str] = field(default_factory=dict)
    blocking_attributes: list[str] = field(default_factory=list)


@dataclass
class EvaluationConfig:
    """Configuration for an evaluation run.

    Defaults follow ASPICE industry conventions:
    - ``target_capability_level`` defaults to **3** (Established).
    - ``process_groups`` defaults to the four core groups.
    """

    sdp_path: str = ""
    target_capability_level: int = 3
    process_groups: list[str] = field(
        default_factory=lambda: ["SWE", "SYS", "MAN", "SUP"]
    )
    kb_path: str = "knowledge_base"
    standard: str = "aspice"
    output_path: str | None = None


@dataclass
class EvaluationResult:
    """Complete result of an evaluation run."""

    ratings: list[CriteriaRating] = field(default_factory=list)
    sdp_metadata: dict[str, Any] = field(default_factory=dict)
    evaluation_timestamp: str = ""
    config: EvaluationConfig = field(default_factory=EvaluationConfig)
    token_usage: dict[str, int] = field(default_factory=lambda: {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "num_batches": 0,
    })


# ---------------------------------------------------------------------------
# Validation models
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Result of KB validation."""

    is_valid: bool = True
    schema_errors: list[str] = field(default_factory=list)
    completeness_gaps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class CompletenessReport:
    """Report on knowledge base completeness."""

    is_complete: bool = True
    missing_entries: list[dict[str, Any]] = field(default_factory=list)
    total_expected: int = 0
    total_found: int = 0


# ---------------------------------------------------------------------------
# SDP Document model
# ---------------------------------------------------------------------------


@dataclass
class SDPDocument:
    """A parsed SDP document ready for evaluation."""

    content: str = ""
    file_path: str = ""
    section_headers: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Model / AI configuration
# ---------------------------------------------------------------------------


@dataclass
class ModelConfig:
    """Configuration for the AI model used by the evaluator."""

    provider: str = ""
    model_name: str = ""
    temperature: float = 0.0
    max_tokens: int = 8192
    api_key: str | None = None
    region: str = ""  # AWS region for Bedrock
    max_context_tokens: int = 100_000  # Max context window for chunking
