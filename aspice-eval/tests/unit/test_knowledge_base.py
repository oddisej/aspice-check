"""Unit tests for the KnowledgeBase loader class.

Tests loading, validation, criteria filtering, and metadata retrieval
for the restructured KB format (processes + generic_practices).

Requirements: 1.1, 1.5, 2.1, 2.2, 8.3
"""

from __future__ import annotations

import pathlib
import textwrap

import pytest
import yaml

from aspice_eval.exceptions import KBValidationError
from aspice_eval.knowledge_base import KnowledgeBase
from aspice_eval.models import CriteriaEntry, KBMetadata, ValidationResult

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_KB_ROOT = pathlib.Path(__file__).resolve().parents[2] / "knowledge_base"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def kb() -> KnowledgeBase:
    """Return a KnowledgeBase pointed at the real KB directory."""
    return KnowledgeBase(str(_KB_ROOT))


@pytest.fixture
def loaded_kb(kb: KnowledgeBase) -> KnowledgeBase:
    """Return a KnowledgeBase that has already loaded the aspice standard."""
    kb.load("aspice")
    return kb


@pytest.fixture
def tmp_kb(tmp_path: pathlib.Path) -> pathlib.Path:
    """Create a minimal temporary KB directory structure."""
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    aspice_dir = tmp_path / "aspice"
    aspice_dir.mkdir()
    return tmp_path


def _write_schema(tmp_kb: pathlib.Path) -> None:
    """Copy the real schema into the temp KB."""
    import json
    import shutil

    src = _KB_ROOT / "schema" / "criteria_schema.json"
    dst = tmp_kb / "schema" / "criteria_schema.json"
    shutil.copy2(src, dst)


def _write_metadata(tmp_kb: pathlib.Path, meta: dict) -> None:
    """Write a metadata YAML file into the temp KB."""
    path = tmp_kb / "aspice" / "_metadata.yaml"
    with open(path, "w") as fh:
        yaml.dump(meta, fh, default_flow_style=False)


def _write_criteria_file(tmp_kb: pathlib.Path, filename: str, data: dict) -> None:
    """Write a criteria YAML file into the temp KB."""
    path = tmp_kb / "aspice" / filename
    with open(path, "w") as fh:
        yaml.dump(data, fh, default_flow_style=False)


def _make_minimal_process(process_id: str = "TST.1", process_name: str = "Test Process"):
    """Return a minimal valid process dict."""
    return {
        "process_id": process_id,
        "process_name": process_name,
        "process_purpose": "The purpose is to test.",
        "process_outcomes": [{"id": 1, "description": "Test outcome."}],
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


def _make_minimal_generic_practices():
    """Return a minimal generic_practices dict with one PA."""
    return {
        "PA_2_1": {
            "process_attribute_id": "PA 2.1",
            "process_attribute_name": "Process performance management",
            "capability_level": 2,
            "practices": [
                {
                    "gp_id": "GP 2.1.1",
                    "title": "Test GP",
                    "description": "A test generic practice.",
                },
            ],
        },
    }


def _make_full_generic_practices():
    """Return a complete generic_practices dict covering PA 2.1 through PA 5.2."""
    pa_map = {
        "PA_2_1": ("PA 2.1", "Process performance management", 2),
        "PA_2_2": ("PA 2.2", "Work product management", 2),
        "PA_3_1": ("PA 3.1", "Process definition", 3),
        "PA_3_2": ("PA 3.2", "Process deployment", 3),
        "PA_4_1": ("PA 4.1", "Quantitative analysis", 4),
        "PA_4_2": ("PA 4.2", "Quantitative control", 4),
        "PA_5_1": ("PA 5.1", "Process innovation", 5),
        "PA_5_2": ("PA 5.2", "Process optimization", 5),
    }
    result = {}
    for key, (pa_id, pa_name, cl) in pa_map.items():
        result[key] = {
            "process_attribute_id": pa_id,
            "process_attribute_name": pa_name,
            "capability_level": cl,
            "practices": [
                {
                    "gp_id": f"GP {pa_id.replace('PA ', '')}.1",
                    "title": f"Practice for {pa_id}",
                    "description": f"Generic practice for {pa_id}.",
                },
            ],
        }
    return result


# ===================================================================
# Constructor tests
# ===================================================================


class TestKnowledgeBaseInit:
    """Tests for KnowledgeBase.__init__()."""

    def test_valid_path(self):
        kb = KnowledgeBase(str(_KB_ROOT))
        assert kb is not None

    def test_nonexistent_path_raises(self, tmp_path: pathlib.Path):
        bad_path = tmp_path / "nonexistent"
        with pytest.raises(FileNotFoundError, match="does not exist"):
            KnowledgeBase(str(bad_path))

    def test_accepts_pathlib_path(self):
        kb = KnowledgeBase(_KB_ROOT)
        assert kb is not None


# ===================================================================
# Load tests
# ===================================================================


class TestLoad:
    """Tests for KnowledgeBase.load()."""

    def test_load_aspice(self, kb: KnowledgeBase):
        kb.load("aspice")
        # Should have loaded criteria files (swe, sys, man, sup)
        assert len(kb._criteria_files) >= 4

    def test_load_nonexistent_standard_raises(self, kb: KnowledgeBase):
        with pytest.raises(FileNotFoundError, match="does not exist"):
            kb.load("nonexistent_standard")

    def test_load_stores_metadata(self, loaded_kb: KnowledgeBase):
        assert loaded_kb._metadata_raw is not None
        assert "kb_version" in loaded_kb._metadata_raw

    def test_load_validates_schema(self, tmp_kb: pathlib.Path):
        """Loading a file with invalid schema raises KBValidationError."""
        _write_schema(tmp_kb)
        # Write an invalid criteria file (missing required fields)
        _write_criteria_file(tmp_kb, "bad.yaml", {"invalid": True})

        kb = KnowledgeBase(str(tmp_kb))
        with pytest.raises(KBValidationError):
            kb.load("aspice")

    def test_load_skips_underscore_files(self, tmp_kb: pathlib.Path):
        """Files starting with _ (like _metadata.yaml) are not validated as criteria."""
        _write_schema(tmp_kb)
        _write_metadata(tmp_kb, {"kb_version": "1.0.0"})
        _write_criteria_file(
            tmp_kb,
            "tst.yaml",
            {
                "process_group": {"code": "TST", "name": "Test"},
                "processes": [_make_minimal_process()],
            },
        )
        kb = KnowledgeBase(str(tmp_kb))
        kb.load("aspice")
        # Only tst.yaml should be loaded, not _metadata.yaml
        assert len(kb._criteria_files) == 1


# ===================================================================
# Validate tests
# ===================================================================


class TestValidate:
    """Tests for KnowledgeBase.validate()."""

    def test_validate_returns_validation_result(self, loaded_kb: KnowledgeBase):
        result = loaded_kb.validate()
        assert isinstance(result, ValidationResult)

    def test_validate_no_files_loaded(self, kb: KnowledgeBase):
        result = kb.validate()
        assert result.is_valid is False
        assert any("No criteria files" in e for e in result.schema_errors)

    def test_validate_with_real_kb(self, loaded_kb: KnowledgeBase):
        result = loaded_kb.validate()
        # Schema should pass for real KB
        assert len(result.schema_errors) == 0


# ===================================================================
# get_criteria tests
# ===================================================================


class TestGetCriteria:
    """Tests for KnowledgeBase.get_criteria()."""

    def test_returns_criteria_entries(self, loaded_kb: KnowledgeBase):
        entries = loaded_kb.get_criteria(["SWE"], max_capability_level=1)
        assert len(entries) > 0
        assert all(isinstance(e, CriteriaEntry) for e in entries)

    def test_filters_by_process_group(self, loaded_kb: KnowledgeBase):
        entries = loaded_kb.get_criteria(["SWE"], max_capability_level=5)
        assert all(e.process_group == "SWE" for e in entries)

    def test_filters_by_max_capability_level(self, loaded_kb: KnowledgeBase):
        entries = loaded_kb.get_criteria(["SWE"], max_capability_level=2)
        assert all(e.capability_level <= 2 for e in entries)

    def test_cl1_entries_are_base_practices(self, loaded_kb: KnowledgeBase):
        entries = loaded_kb.get_criteria(["SWE"], max_capability_level=1)
        assert all(e.capability_level == 1 for e in entries)
        assert all(e.process_attribute == "PA 1.1" for e in entries)
        # criteria_id should be like "SWE.1-BP1"
        assert all("-BP" in e.criteria_id for e in entries)

    def test_cl2_entries_are_generic_practices(self, loaded_kb: KnowledgeBase):
        entries = loaded_kb.get_criteria(["SWE"], max_capability_level=2)
        cl2_entries = [e for e in entries if e.capability_level == 2]
        assert len(cl2_entries) > 0
        # criteria_id should be like "SWE-GP2.1.1"
        assert all("-GP" in e.criteria_id for e in cl2_entries)

    def test_multiple_groups(self, loaded_kb: KnowledgeBase):
        entries = loaded_kb.get_criteria(["SWE", "MAN"], max_capability_level=1)
        groups = {e.process_group for e in entries}
        assert "SWE" in groups
        assert "MAN" in groups

    def test_empty_groups_returns_empty(self, loaded_kb: KnowledgeBase):
        entries = loaded_kb.get_criteria([], max_capability_level=5)
        assert entries == []

    def test_unknown_group_returns_empty(self, loaded_kb: KnowledgeBase):
        entries = loaded_kb.get_criteria(["UNKNOWN"], max_capability_level=5)
        assert entries == []

    def test_criteria_entry_fields_populated(self, loaded_kb: KnowledgeBase):
        """Verify that CriteriaEntry fields are properly populated."""
        entries = loaded_kb.get_criteria(["SWE"], max_capability_level=1)
        entry = entries[0]
        assert entry.process_group == "SWE"
        assert entry.process_id.startswith("SWE.")
        assert entry.process_name != ""
        assert entry.capability_level == 1
        assert entry.process_attribute == "PA 1.1"
        assert entry.process_attribute_name == "Process performance"
        assert entry.criteria_id != ""
        assert entry.description != ""
        assert isinstance(entry.expected_evidence, list)
        assert entry.evaluation_guidance != ""

    def test_generic_practice_entry_fields(self, loaded_kb: KnowledgeBase):
        """Verify generic practice CriteriaEntry fields."""
        entries = loaded_kb.get_criteria(["SWE"], max_capability_level=2)
        gp_entries = [e for e in entries if e.capability_level == 2]
        assert len(gp_entries) > 0
        entry = gp_entries[0]
        assert entry.process_group == "SWE"
        assert entry.process_id == "SWE"  # group-level for generic practices
        assert entry.capability_level == 2
        assert entry.process_attribute.startswith("PA 2.")
        assert entry.criteria_id.startswith("SWE-GP")

    def test_base_practice_criteria_id_format(self, loaded_kb: KnowledgeBase):
        """Verify criteria_id format for base practices: {process_id}-{bp_id}."""
        entries = loaded_kb.get_criteria(["MAN"], max_capability_level=1)
        for entry in entries:
            # Should be like "MAN.3-BP1"
            parts = entry.criteria_id.split("-")
            assert len(parts) == 2
            assert parts[0].startswith("MAN.")
            assert parts[1].startswith("BP")

    def test_with_temp_kb(self, tmp_kb: pathlib.Path):
        """Test criteria loading with a controlled temp KB."""
        _write_schema(tmp_kb)
        _write_metadata(tmp_kb, {
            "standard": {"name": "Test", "short_name": "TST", "version": "1.0"},
            "kb_version": "1.0.0",
            "process_groups": [
                {"code": "TST", "name": "Test", "processes": ["TST.1"]},
            ],
        })
        _write_criteria_file(tmp_kb, "tst.yaml", {
            "process_group": {"code": "TST", "name": "Test"},
            "processes": [_make_minimal_process()],
            "generic_practices": _make_minimal_generic_practices(),
        })

        kb = KnowledgeBase(str(tmp_kb))
        kb.load("aspice")

        # CL1 only
        cl1 = kb.get_criteria(["TST"], max_capability_level=1)
        assert len(cl1) == 1
        assert cl1[0].criteria_id == "TST.1-BP1"
        assert cl1[0].process_name == "Test Process"

        # CL1 + CL2
        cl2 = kb.get_criteria(["TST"], max_capability_level=2)
        assert len(cl2) == 2
        gp_entry = [e for e in cl2 if e.capability_level == 2][0]
        assert gp_entry.criteria_id == "TST-GP 2.1.1"
        assert gp_entry.process_attribute == "PA 2.1"


# ===================================================================
# get_metadata tests
# ===================================================================


class TestGetMetadata:
    """Tests for KnowledgeBase.get_metadata()."""

    def test_returns_kb_metadata(self, loaded_kb: KnowledgeBase):
        meta = loaded_kb.get_metadata()
        assert isinstance(meta, KBMetadata)

    def test_metadata_fields(self, loaded_kb: KnowledgeBase):
        meta = loaded_kb.get_metadata()
        assert meta.standard_name == "Automotive SPICE"
        assert meta.short_name == "ASPICE"
        assert meta.version == "4.0"
        assert meta.kb_version != ""
        assert meta.release_date != ""
        assert len(meta.process_groups) >= 4
        assert len(meta.capability_levels) >= 6
        assert len(meta.rating_scale) == 4

    def test_kb_version_present(self, loaded_kb: KnowledgeBase):
        meta = loaded_kb.get_metadata()
        assert meta.kb_version == "2.0.0"

    def test_metadata_not_loaded_raises(self, kb: KnowledgeBase):
        with pytest.raises(FileNotFoundError, match="No metadata loaded"):
            kb.get_metadata()

    def test_source_references(self, loaded_kb: KnowledgeBase):
        meta = loaded_kb.get_metadata()
        assert len(meta.source_references) > 0
        assert "title" in meta.source_references[0]
        assert "url" in meta.source_references[0]

    def test_license_note(self, loaded_kb: KnowledgeBase):
        meta = loaded_kb.get_metadata()
        assert meta.license_note != ""
