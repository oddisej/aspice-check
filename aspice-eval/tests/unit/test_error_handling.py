"""Unit tests for error handling across the ASPICE evaluation tool.

Tests cover:
- FileNotFoundError for missing SDP and KB paths
- UnsupportedFormatError message content
- InvalidConfigError for out-of-range target levels and unknown process groups
- KBValidationError for malformed YAML

Requirements: 3.3, 7.1
"""

from __future__ import annotations

import os
import pathlib
import textwrap

import pytest
import yaml

from aspice_eval.exceptions import (
    InvalidConfigError,
    KBValidationError,
    UnsupportedFormatError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _kb_path() -> str:
    """Return the path to the real knowledge_base directory."""
    return str(
        pathlib.Path(__file__).resolve().parents[2] / "knowledge_base"
    )


# ---------------------------------------------------------------------------
# FileNotFoundError tests
# ---------------------------------------------------------------------------


class TestFileNotFoundErrors:
    """FileNotFoundError is raised for missing SDP and KB paths."""

    def test_missing_sdp_path_raises(self):
        from aspice_eval.sdp_ingester import SDPIngester

        ingester = SDPIngester()
        with pytest.raises(FileNotFoundError, match="SDP document not found"):
            ingester.ingest("/nonexistent/path/sdp.md")

    def test_missing_kb_path_raises(self):
        from aspice_eval.knowledge_base import KnowledgeBase

        with pytest.raises(FileNotFoundError, match="does not exist"):
            KnowledgeBase("/nonexistent/knowledge_base")

    def test_missing_standard_dir_raises(self, tmp_path):
        from aspice_eval.knowledge_base import KnowledgeBase

        # Create a KB directory but no standard subdirectory
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "schema").mkdir()
        kb = KnowledgeBase(str(kb_dir))
        with pytest.raises(FileNotFoundError, match="does not exist"):
            kb.load("aspice")

    def test_cli_validate_config_missing_kb_path(self):
        from aspice_eval.cli import _validate_config

        with pytest.raises(FileNotFoundError, match="does not exist"):
            _validate_config(
                target_level=3,
                groups=["SWE"],
                kb_path="/nonexistent/kb",
            )


# ---------------------------------------------------------------------------
# UnsupportedFormatError tests
# ---------------------------------------------------------------------------


class TestUnsupportedFormatError:
    """UnsupportedFormatError carries descriptive message content."""

    def test_docx_rejected_with_message(self, tmp_path):
        from aspice_eval.sdp_ingester import SDPIngester

        docx_file = tmp_path / "sdp.docx"
        docx_file.write_text("fake docx content")

        ingester = SDPIngester()
        with pytest.raises(UnsupportedFormatError, match="Unsupported file format") as exc_info:
            ingester.ingest(str(docx_file))

        assert ".docx" in str(exc_info.value)
        assert "Markdown" in str(exc_info.value)
        assert exc_info.value.actual_extension == ".docx"

    def test_pdf_rejected_with_message(self, tmp_path):
        from aspice_eval.sdp_ingester import SDPIngester

        pdf_file = tmp_path / "sdp.pdf"
        pdf_file.write_text("fake pdf content")

        ingester = SDPIngester()
        with pytest.raises(UnsupportedFormatError, match="Unsupported file format") as exc_info:
            ingester.ingest(str(pdf_file))

        assert ".pdf" in str(exc_info.value)
        assert exc_info.value.actual_extension == ".pdf"

    def test_xlsx_rejected_with_message(self, tmp_path):
        from aspice_eval.sdp_ingester import SDPIngester

        xlsx_file = tmp_path / "sdp.xlsx"
        xlsx_file.write_text("fake xlsx content")

        ingester = SDPIngester()
        with pytest.raises(UnsupportedFormatError) as exc_info:
            ingester.ingest(str(xlsx_file))

        assert exc_info.value.actual_extension == ".xlsx"
        assert exc_info.value.file_path == str(xlsx_file)

    def test_exception_carries_structured_context(self):
        exc = UnsupportedFormatError(
            "Unsupported format .pdf",
            file_path="/tmp/doc.pdf",
            actual_extension=".pdf",
        )
        assert exc.file_path == "/tmp/doc.pdf"
        assert exc.actual_extension == ".pdf"
        assert "Unsupported format .pdf" in str(exc)


# ---------------------------------------------------------------------------
# InvalidConfigError tests
# ---------------------------------------------------------------------------


class TestInvalidConfigError:
    """InvalidConfigError for out-of-range target levels and unknown groups."""

    def test_target_level_zero_raises(self):
        from aspice_eval.cli import _validate_config

        with pytest.raises(InvalidConfigError, match="out of range") as exc_info:
            _validate_config(
                target_level=0,
                groups=["SWE"],
                kb_path=_kb_path(),
            )
        assert exc_info.value.parameter == "target_level"
        assert exc_info.value.actual_value == 0
        assert exc_info.value.expected_values == [1, 2, 3, 4, 5]

    def test_target_level_six_raises(self):
        from aspice_eval.cli import _validate_config

        with pytest.raises(InvalidConfigError, match="out of range") as exc_info:
            _validate_config(
                target_level=6,
                groups=["SWE"],
                kb_path=_kb_path(),
            )
        assert exc_info.value.parameter == "target_level"
        assert exc_info.value.actual_value == 6

    def test_negative_target_level_raises(self):
        from aspice_eval.cli import _validate_config

        with pytest.raises(InvalidConfigError, match="out of range"):
            _validate_config(
                target_level=-1,
                groups=["SWE"],
                kb_path=_kb_path(),
            )

    def test_unknown_process_group_raises(self):
        from aspice_eval.cli import _validate_config

        with pytest.raises(InvalidConfigError, match="Unknown process group") as exc_info:
            _validate_config(
                target_level=3,
                groups=["SWE", "INVALID"],
                kb_path=_kb_path(),
            )
        assert exc_info.value.parameter == "process_groups"
        assert "INVALID" in exc_info.value.actual_value

    def test_all_unknown_groups_raises(self):
        from aspice_eval.cli import _validate_config

        with pytest.raises(InvalidConfigError, match="Unknown process group") as exc_info:
            _validate_config(
                target_level=3,
                groups=["FOO", "BAR"],
                kb_path=_kb_path(),
            )
        assert "FOO" in exc_info.value.actual_value
        assert "BAR" in exc_info.value.actual_value

    def test_valid_config_does_not_raise(self):
        from aspice_eval.cli import _validate_config

        # Should not raise
        _validate_config(
            target_level=3,
            groups=["SWE", "MAN"],
            kb_path=_kb_path(),
        )

    def test_exception_carries_structured_context(self):
        exc = InvalidConfigError(
            "Target level 10 is out of range.",
            parameter="target_level",
            actual_value=10,
            expected_values=[1, 2, 3, 4, 5],
        )
        assert exc.parameter == "target_level"
        assert exc.actual_value == 10
        assert exc.expected_values == [1, 2, 3, 4, 5]
        assert "out of range" in str(exc)


# ---------------------------------------------------------------------------
# KBValidationError tests
# ---------------------------------------------------------------------------


class TestKBValidationError:
    """KBValidationError for malformed YAML content."""

    def test_malformed_yaml_missing_process_group(self, tmp_path):
        """A YAML file missing the required 'process_group' field fails validation."""
        from aspice_eval.kb_validator import KBValidator

        schema_path = (
            pathlib.Path(__file__).resolve().parents[2]
            / "knowledge_base"
            / "schema"
            / "criteria_schema.json"
        )
        validator = KBValidator(schema_path)

        malformed = {"criteria": []}  # missing process_group
        with pytest.raises(KBValidationError, match="Schema validation failed"):
            validator.validate_schema(malformed)

    def test_malformed_yaml_bad_criteria_entry(self, tmp_path):
        """A criteria entry missing required fields fails validation."""
        from aspice_eval.kb_validator import KBValidator

        schema_path = (
            pathlib.Path(__file__).resolve().parents[2]
            / "knowledge_base"
            / "schema"
            / "criteria_schema.json"
        )
        validator = KBValidator(schema_path)

        malformed = {
            "process_group": {"code": "SWE", "name": "Software Engineering"},
            "criteria": [
                {
                    "process_id": "SWE.1",
                    # Missing many required fields
                }
            ],
        }
        with pytest.raises(KBValidationError, match="Schema validation failed") as exc_info:
            validator.validate_schema(malformed)

        # The exception should carry structured error details
        assert len(exc_info.value.errors) > 0

    def test_exception_carries_structured_context(self):
        exc = KBValidationError(
            "Schema validation failed with 2 error(s)",
            file_path="/tmp/swe.yaml",
            errors=[
                {"message": "missing field", "path": ["criteria", 0, "process_id"]},
                {"message": "wrong type", "path": ["criteria", 0, "capability_level"]},
            ],
        )
        assert exc.file_path == "/tmp/swe.yaml"
        assert len(exc.errors) == 2
        assert exc.errors[0]["message"] == "missing field"

    def test_completely_invalid_structure(self):
        """A YAML file that is a list instead of a dict fails validation."""
        from aspice_eval.kb_validator import KBValidator

        schema_path = (
            pathlib.Path(__file__).resolve().parents[2]
            / "knowledge_base"
            / "schema"
            / "criteria_schema.json"
        )
        validator = KBValidator(schema_path)

        with pytest.raises(KBValidationError, match="Schema validation failed"):
            validator.validate_schema(["not", "a", "dict"])
