"""Unit tests for the criteria_schema.json JSON Schema.

Validates that the schema correctly accepts valid KB criteria files
(new structure with processes, base_practices, generic_practices)
and rejects invalid ones.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from jsonschema import validate, ValidationError

SCHEMA_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "knowledge_base"
    / "schema"
    / "criteria_schema.json"
)


@pytest.fixture
def schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def _make_valid_process(**overrides):
    """Return a minimal valid process entry."""
    proc = {
        "process_id": "SWE.1",
        "process_name": "Software Requirements Analysis",
        "process_purpose": "The purpose is to establish software requirements.",
        "process_outcomes": [
            {"id": 1, "description": "Software requirements are specified."},
        ],
        "base_practices": [
            {
                "bp_id": "BP1",
                "title": "Specify software requirements",
                "description": "Identify and document the functional and non-functional requirements.",
                "maps_to_outcomes": [1],
            },
        ],
        "output_information_items": [
            {
                "item_id": "17-00",
                "name": "Requirement",
                "maps_to_outcomes": [1],
            },
        ],
    }
    proc.update(overrides)
    return proc


def _make_valid_doc(**overrides):
    """Return a minimal valid criteria document."""
    doc = {
        "process_group": {"code": "SWE", "name": "Software Engineering"},
        "processes": [_make_valid_process()],
    }
    doc.update(overrides)
    return doc


class TestSchemaAcceptsValidDocuments:
    """Schema should accept well-formed criteria files."""

    def test_minimal_valid_document(self, schema):
        doc = _make_valid_doc()
        validate(instance=doc, schema=schema)

    def test_process_with_optional_fields(self, schema):
        proc = _make_valid_process()
        proc["evaluation_guidance"] = "Look for evidence of a plan."
        proc["example_evidence"] = [
            "Requirements plan in Confluence",
            "Sprint tracking in Jira",
        ]
        proc["base_practices"][0]["notes"] = [
            "Note 1: Characteristics of requirements are defined in standards."
        ]
        doc = _make_valid_doc(processes=[proc])
        validate(instance=doc, schema=schema)

    def test_multiple_processes(self, schema):
        proc2 = _make_valid_process(
            process_id="SWE.2",
            process_name="Software Architectural Design",
            process_purpose="The purpose is to establish a software architecture.",
        )
        doc = _make_valid_doc(processes=[_make_valid_process(), proc2])
        validate(instance=doc, schema=schema)

    def test_multiple_base_practices(self, schema):
        proc = _make_valid_process()
        proc["base_practices"].append(
            {
                "bp_id": "BP2",
                "title": "Structure software requirements",
                "description": "Structure and prioritize the software requirements.",
                "maps_to_outcomes": [1],
            }
        )
        doc = _make_valid_doc(processes=[proc])
        validate(instance=doc, schema=schema)

    def test_process_group_code_patterns(self, schema):
        for code in ("SWE", "SYS", "MAN", "SUP", "ACQ", "HWE", "MLE"):
            doc = _make_valid_doc()
            doc["process_group"]["code"] = code
            validate(instance=doc, schema=schema)

    def test_document_with_generic_practices(self, schema):
        doc = _make_valid_doc()
        doc["generic_practices"] = {
            "PA_2_1": {
                "process_attribute_id": "PA 2.1",
                "process_attribute_name": "Performance management",
                "capability_level": 2,
                "practices": [
                    {
                        "gp_id": "GP 2.1.1",
                        "title": "Identify the objectives",
                        "description": "The scope of the process activities is determined.",
                        "maps_to_achievements": [1],
                    },
                ],
            },
        }
        validate(instance=doc, schema=schema)

    def test_generic_practice_with_all_optional_fields(self, schema):
        doc = _make_valid_doc()
        doc["generic_practices"] = {
            "PA_3_1": {
                "process_attribute_id": "PA 3.1",
                "process_attribute_name": "Process definition",
                "capability_level": 3,
                "scope": "A measure of the extent to which a standard process is maintained.",
                "achievements": [
                    {"id": 1, "description": "A standard process is developed."},
                ],
                "practices": [
                    {
                        "gp_id": "GP 3.1.1",
                        "title": "Establish and maintain the standard process",
                        "description": "A suitable standard process is developed.",
                        "notes": ["Note 1: An example is a RASI representation."],
                        "maps_to_achievements": [1],
                    },
                ],
                "output_information_items": [
                    {
                        "item_id": "10-00",
                        "name": "Process description",
                        "maps_to_achievements": [1],
                    },
                ],
                "evaluation_guidance": "Verify that an org-level standard process exists.",
                "example_evidence": ["Organization process asset library"],
            },
        }
        validate(instance=doc, schema=schema)


class TestSchemaRejectsInvalidDocuments:
    """Schema should reject malformed criteria files."""

    def test_missing_process_group(self, schema):
        doc = _make_valid_doc()
        del doc["process_group"]
        with pytest.raises(ValidationError, match="process_group"):
            validate(instance=doc, schema=schema)

    def test_missing_processes(self, schema):
        doc = _make_valid_doc()
        del doc["processes"]
        with pytest.raises(ValidationError, match="processes"):
            validate(instance=doc, schema=schema)

    def test_missing_process_group_code(self, schema):
        doc = _make_valid_doc()
        del doc["process_group"]["code"]
        with pytest.raises(ValidationError, match="code"):
            validate(instance=doc, schema=schema)

    def test_missing_process_purpose(self, schema):
        proc = _make_valid_process()
        del proc["process_purpose"]
        doc = _make_valid_doc(processes=[proc])
        with pytest.raises(ValidationError, match="process_purpose"):
            validate(instance=doc, schema=schema)

    def test_missing_process_outcomes(self, schema):
        proc = _make_valid_process()
        del proc["process_outcomes"]
        doc = _make_valid_doc(processes=[proc])
        with pytest.raises(ValidationError, match="process_outcomes"):
            validate(instance=doc, schema=schema)

    def test_missing_base_practices(self, schema):
        proc = _make_valid_process()
        del proc["base_practices"]
        doc = _make_valid_doc(processes=[proc])
        with pytest.raises(ValidationError, match="base_practices"):
            validate(instance=doc, schema=schema)

    def test_empty_base_practices(self, schema):
        proc = _make_valid_process()
        proc["base_practices"] = []
        doc = _make_valid_doc(processes=[proc])
        with pytest.raises(ValidationError):
            validate(instance=doc, schema=schema)

    def test_missing_output_information_items(self, schema):
        proc = _make_valid_process()
        del proc["output_information_items"]
        doc = _make_valid_doc(processes=[proc])
        with pytest.raises(ValidationError, match="output_information_items"):
            validate(instance=doc, schema=schema)

    def test_empty_output_information_items(self, schema):
        proc = _make_valid_process()
        proc["output_information_items"] = []
        doc = _make_valid_doc(processes=[proc])
        with pytest.raises(ValidationError):
            validate(instance=doc, schema=schema)

    def test_bp_missing_description(self, schema):
        proc = _make_valid_process()
        del proc["base_practices"][0]["description"]
        doc = _make_valid_doc(processes=[proc])
        with pytest.raises(ValidationError, match="description"):
            validate(instance=doc, schema=schema)

    def test_bp_invalid_id_pattern(self, schema):
        proc = _make_valid_process()
        proc["base_practices"][0]["bp_id"] = "bp1"  # lowercase
        doc = _make_valid_doc(processes=[proc])
        with pytest.raises(ValidationError):
            validate(instance=doc, schema=schema)

    def test_outcome_missing_id(self, schema):
        proc = _make_valid_process()
        proc["process_outcomes"] = [{"description": "Missing id field."}]
        doc = _make_valid_doc(processes=[proc])
        with pytest.raises(ValidationError, match="id"):
            validate(instance=doc, schema=schema)

    def test_outcome_id_below_minimum(self, schema):
        proc = _make_valid_process()
        proc["process_outcomes"] = [{"id": 0, "description": "Zero id."}]
        doc = _make_valid_doc(processes=[proc])
        with pytest.raises(ValidationError):
            validate(instance=doc, schema=schema)

    def test_invalid_process_group_code_lowercase(self, schema):
        doc = _make_valid_doc()
        doc["process_group"]["code"] = "swe"
        with pytest.raises(ValidationError):
            validate(instance=doc, schema=schema)

    def test_invalid_process_group_code_too_long(self, schema):
        doc = _make_valid_doc()
        doc["process_group"]["code"] = "ABCDE"
        with pytest.raises(ValidationError):
            validate(instance=doc, schema=schema)

    def test_generic_practice_invalid_pa_pattern(self, schema):
        doc = _make_valid_doc()
        doc["generic_practices"] = {
            "PA_2_1": {
                "process_attribute_id": "PA2.1",  # missing space
                "process_attribute_name": "Performance management",
                "capability_level": 2,
                "practices": [
                    {
                        "gp_id": "GP 2.1.1",
                        "title": "Test",
                        "description": "Test desc.",
                    }
                ],
            },
        }
        with pytest.raises(ValidationError):
            validate(instance=doc, schema=schema)

    def test_generic_practice_capability_level_too_low(self, schema):
        doc = _make_valid_doc()
        doc["generic_practices"] = {
            "PA_2_1": {
                "process_attribute_id": "PA 2.1",
                "process_attribute_name": "Performance management",
                "capability_level": 1,  # must be 2-5
                "practices": [
                    {
                        "gp_id": "GP 2.1.1",
                        "title": "Test",
                        "description": "Test desc.",
                    }
                ],
            },
        }
        with pytest.raises(ValidationError):
            validate(instance=doc, schema=schema)
