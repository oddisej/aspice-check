"""Unit tests for the KBValidator class.

Tests schema validation against criteria_schema.json and completeness
checking for the restructured KB format (processes + generic_practices).

Requirements: 8.1, 8.2
"""

from __future__ import annotations

import json
import pathlib

import pytest
import yaml

from aspice_eval.exceptions import KBValidationError
from aspice_eval.kb_validator import KBValidator

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_KB_ROOT = pathlib.Path(__file__).resolve().parents[2] / "knowledge_base"
_SCHEMA_PATH = _KB_ROOT / "schema" / "criteria_schema.json"
_METADATA_PATH = _KB_ROOT / "aspice" / "_metadata.yaml"
_ASPICE_DIR = _KB_ROOT / "aspice"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def schema_path() -> pathlib.Path:
    return _SCHEMA_PATH


@pytest.fixture
def metadata_path() -> pathlib.Path:
    return _METADATA_PATH


@pytest.fixture
def validator(schema_path: pathlib.Path, metadata_path: pathlib.Path) -> KBValidator:
    return KBValidator(schema_path, metadata_path=metadata_path)


@pytest.fixture
def validator_no_meta(schema_path: pathlib.Path) -> KBValidator:
    return KBValidator(schema_path)


@pytest.fixture
def metadata(metadata_path: pathlib.Path) -> dict:
    with open(metadata_path) as fh:
        return yaml.safe_load(fh)


def _make_valid_process(**overrides):
    """Return a minimal valid process entry."""
    proc = {
        "process_id": "TST.1",
        "process_name": "Test Process",
        "process_purpose": "The purpose is to test.",
        "process_outcomes": [
            {"id": 1, "description": "Test outcome."},
        ],
        "base_practices": [
            {
                "bp_id": "BP1",
                "title": "Test practice",
                "description": "A test base practice.",
                "maps_to_outcomes": [1],
            },
        ],
        "output_information_items": [
            {"item_id": "99-00", "name": "Test item", "maps_to_outcomes": [1]},
        ],
    }
    proc.update(overrides)
    return proc


def _make_valid_doc(**overrides):
    """Return a minimal valid criteria document."""
    doc = {
        "process_group": {"code": "TST", "name": "Test Group"},
        "processes": [_make_valid_process()],
    }
    doc.update(overrides)
    return doc


def _make_generic_practice(pa_key: str, pa_id: str, cl: int):
    """Return a minimal valid generic practice entry."""
    return {
        "process_attribute_id": pa_id,
        "process_attribute_name": f"Attribute {pa_id}",
        "capability_level": cl,
        "practices": [
            {
                "gp_id": f"GP {pa_id.replace('PA ', '')}.1",
                "title": f"Practice for {pa_id}",
                "description": f"Generic practice for {pa_id}.",
            },
        ],
    }


def _make_full_generic_practices():
    """Return a complete generic_practices dict covering PA 2.1 through PA 5.2."""
    pa_map = {
        "PA_2_1": ("PA 2.1", 2),
        "PA_2_2": ("PA 2.2", 2),
        "PA_3_1": ("PA 3.1", 3),
        "PA_3_2": ("PA 3.2", 3),
        "PA_4_1": ("PA 4.1", 4),
        "PA_4_2": ("PA 4.2", 4),
        "PA_5_1": ("PA 5.1", 5),
        "PA_5_2": ("PA 5.2", 5),
    }
    return {
        key: _make_generic_practice(key, pa_id, cl)
        for key, (pa_id, cl) in pa_map.items()
    }


# ===================================================================
# Schema validation tests
# ===================================================================


class TestValidateSchema:
    """Tests for KBValidator.validate_schema()."""

    def test_valid_document_returns_empty_list(self, validator: KBValidator):
        doc = _make_valid_doc()
        errors = validator.validate_schema(doc)
        assert errors == []

    def test_valid_document_with_generic_practices(self, validator: KBValidator):
        doc = _make_valid_doc()
        doc["generic_practices"] = _make_full_generic_practices()
        errors = validator.validate_schema(doc)
        assert errors == []

    def test_missing_process_group_raises(self, validator: KBValidator):
        doc = _make_valid_doc()
        del doc["process_group"]
        with pytest.raises(KBValidationError) as exc_info:
            validator.validate_schema(doc)
        assert "process_group" in str(exc_info.value)
        assert len(exc_info.value.errors) > 0

    def test_missing_processes_raises(self, validator: KBValidator):
        doc = _make_valid_doc()
        del doc["processes"]
        with pytest.raises(KBValidationError) as exc_info:
            validator.validate_schema(doc)
        assert "processes" in str(exc_info.value)

    def test_empty_base_practices_raises(self, validator: KBValidator):
        proc = _make_valid_process()
        proc["base_practices"] = []
        doc = _make_valid_doc(processes=[proc])
        with pytest.raises(KBValidationError):
            validator.validate_schema(doc)

    def test_missing_bp_description_raises(self, validator: KBValidator):
        proc = _make_valid_process()
        del proc["base_practices"][0]["description"]
        doc = _make_valid_doc(processes=[proc])
        with pytest.raises(KBValidationError) as exc_info:
            validator.validate_schema(doc)
        assert "description" in str(exc_info.value)

    def test_error_carries_structured_context(self, validator: KBValidator):
        doc = _make_valid_doc()
        del doc["process_group"]
        with pytest.raises(KBValidationError) as exc_info:
            validator.validate_schema(doc)
        err = exc_info.value
        assert isinstance(err.errors, list)
        assert len(err.errors) >= 1
        assert "message" in err.errors[0]
        assert "path" in err.errors[0]

    def test_real_swe_file_passes_schema(self, validator: KBValidator):
        """Validate the actual swe.yaml file against the schema."""
        swe_path = _ASPICE_DIR / "swe.yaml"
        with open(swe_path) as fh:
            swe_data = yaml.safe_load(fh)
        errors = validator.validate_schema(swe_data)
        assert errors == []


# ===================================================================
# Completeness validation tests
# ===================================================================


class TestValidateCompleteness:
    """Tests for KBValidator.validate_completeness()."""

    def test_complete_single_group(self, validator: KBValidator):
        """A group with all processes and all generic PAs is complete."""
        meta = {
            "process_groups": [
                {"code": "TST", "name": "Test", "processes": ["TST.1"]},
            ],
        }
        doc = _make_valid_doc()
        doc["generic_practices"] = _make_full_generic_practices()
        report = validator.validate_completeness([doc], metadata=meta)
        assert report.is_complete is True
        assert report.missing_entries == []
        # 1 process (CL1) + 8 generic PAs = 9 expected
        assert report.total_expected == 9
        assert report.total_found == 9

    def test_missing_process_base_practices(self, validator: KBValidator):
        """A process without base practices is flagged as missing CL1."""
        meta = {
            "process_groups": [
                {"code": "TST", "name": "Test", "processes": ["TST.1", "TST.2"]},
            ],
        }
        doc = _make_valid_doc()
        doc["generic_practices"] = _make_full_generic_practices()
        # TST.1 has base practices, TST.2 is missing from the processes list
        report = validator.validate_completeness([doc], metadata=meta)
        assert report.is_complete is False
        missing_ids = [m["process_id"] for m in report.missing_entries if "process_id" in m]
        assert "TST.2" in missing_ids

    def test_missing_generic_practice(self, validator: KBValidator):
        """A missing PA in generic_practices is flagged."""
        meta = {
            "process_groups": [
                {"code": "TST", "name": "Test", "processes": ["TST.1"]},
            ],
        }
        doc = _make_valid_doc()
        gp = _make_full_generic_practices()
        del gp["PA_3_2"]  # Remove PA 3.2
        doc["generic_practices"] = gp
        report = validator.validate_completeness([doc], metadata=meta)
        assert report.is_complete is False
        missing_pas = [m["process_attribute"] for m in report.missing_entries]
        assert "PA 3.2" in missing_pas

    def test_no_generic_practices_section(self, validator: KBValidator):
        """A file with no generic_practices section is missing all CL2-5 PAs."""
        meta = {
            "process_groups": [
                {"code": "TST", "name": "Test", "processes": ["TST.1"]},
            ],
        }
        doc = _make_valid_doc()
        # No generic_practices key at all
        report = validator.validate_completeness([doc], metadata=meta)
        assert report.is_complete is False
        # 8 generic PAs should be missing
        missing_pas = [m["process_attribute"] for m in report.missing_entries]
        assert len(missing_pas) == 8

    def test_missing_criteria_file_for_group(self, validator: KBValidator):
        """A group with no criteria file at all is fully missing."""
        meta = {
            "process_groups": [
                {"code": "TST", "name": "Test", "processes": ["TST.1"]},
                {"code": "XYZ", "name": "Unknown", "processes": ["XYZ.1"]},
            ],
        }
        doc = _make_valid_doc()
        doc["generic_practices"] = _make_full_generic_practices()
        report = validator.validate_completeness([doc], metadata=meta)
        assert report.is_complete is False
        xyz_missing = [m for m in report.missing_entries if m["process_group"] == "XYZ"]
        # 1 process (CL1) + 8 generic PAs = 9 missing for XYZ
        assert len(xyz_missing) == 9

    def test_metadata_required(self, validator_no_meta: KBValidator):
        """Completeness check raises ValueError when no metadata is available."""
        with pytest.raises(ValueError, match="Metadata is required"):
            validator_no_meta.validate_completeness([_make_valid_doc()])

    def test_metadata_argument_overrides_constructor(self, validator: KBValidator):
        """Metadata passed as argument takes precedence over constructor metadata."""
        custom_meta = {
            "process_groups": [
                {"code": "TST", "name": "Test", "processes": ["TST.1"]},
            ],
        }
        doc = _make_valid_doc()
        doc["generic_practices"] = _make_full_generic_practices()
        report = validator.validate_completeness([doc], metadata=custom_meta)
        # Should use custom_meta (1 group) not the real metadata (4 groups)
        assert report.total_expected == 9
        assert report.is_complete is True

    def test_real_kb_completeness(self, validator: KBValidator):
        """Validate completeness of the actual KB files against real metadata."""
        criteria_files = []
        for yaml_file in sorted(_ASPICE_DIR.glob("*.yaml")):
            if yaml_file.name.startswith("_"):
                continue
            with open(yaml_file) as fh:
                criteria_files.append(yaml.safe_load(fh))

        with open(_METADATA_PATH) as fh:
            meta = yaml.safe_load(fh)

        report = validator.validate_completeness(criteria_files, metadata=meta)
        # Report should have meaningful counts
        assert report.total_expected > 0
        assert report.total_found > 0
        # Log gaps for visibility (not asserting complete since KB may be WIP)
        if not report.is_complete:
            for gap in report.missing_entries:
                print(f"  Gap: {gap}")


class TestValidateCompletenessCountsAccuracy:
    """Verify that total_expected and total_found are accurate."""

    def test_counts_match_expectations(self, validator: KBValidator):
        meta = {
            "process_groups": [
                {"code": "A", "name": "Alpha", "processes": ["A.1", "A.2"]},
                {"code": "B", "name": "Beta", "processes": ["B.1"]},
            ],
        }
        # Group A: both processes present, all generic PAs
        doc_a = {
            "process_group": {"code": "A", "name": "Alpha"},
            "processes": [
                _make_valid_process(process_id="A.1"),
                _make_valid_process(process_id="A.2"),
            ],
            "generic_practices": _make_full_generic_practices(),
        }
        # Group B: process present, missing PA_5_1 and PA_5_2
        gp_b = _make_full_generic_practices()
        del gp_b["PA_5_1"]
        del gp_b["PA_5_2"]
        doc_b = {
            "process_group": {"code": "B", "name": "Beta"},
            "processes": [_make_valid_process(process_id="B.1")],
            "generic_practices": gp_b,
        }

        report = validator.validate_completeness([doc_a, doc_b], metadata=meta)
        # Group A: 2 processes + 8 PAs = 10
        # Group B: 1 process + 8 PAs = 9
        assert report.total_expected == 19
        # Group A: all 10 found
        # Group B: 1 process + 6 PAs = 7 found
        assert report.total_found == 17
        assert len(report.missing_entries) == 2
        assert report.is_complete is False
