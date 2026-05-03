"""Knowledge base loader for ASPICE criteria files.

Loads, validates, and queries ASPICE criteria from YAML files organized
by process group. Converts the structured YAML format (processes with
base practices for CL1, generic practices for CL2-5) into flat
CriteriaEntry objects for evaluation.

Requirements: 1.1, 1.5, 2.1, 2.2, 8.3
"""

from __future__ import annotations

import pathlib
from typing import Any

import yaml

from aspice_eval.exceptions import KBValidationError
from aspice_eval.kb_validator import KBValidator
from aspice_eval.models import (
    CriteriaEntry,
    KBMetadata,
    ValidationResult,
)


class KnowledgeBase:
    """Loads, validates, and queries ASPICE criteria from YAML files.

    Parameters
    ----------
    kb_path:
        Path to the knowledge base root directory (e.g. ``knowledge_base``).

    Raises
    ------
    FileNotFoundError
        If *kb_path* does not exist.
    """

    def __init__(self, kb_path: str | pathlib.Path) -> None:
        self._kb_path = pathlib.Path(kb_path)
        if not self._kb_path.exists():
            raise FileNotFoundError(
                f"Knowledge base path does not exist: {self._kb_path}"
            )
        self._schema_path = self._kb_path / "schema" / "criteria_schema.json"
        self._criteria_files: list[dict[str, Any]] = []
        self._metadata_raw: dict[str, Any] | None = None
        self._standard_dir: pathlib.Path | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, standard: str = "aspice") -> None:
        """Load all criteria YAML files for the given standard.

        Parses every ``*.yaml`` file in the standard directory (excluding
        files prefixed with ``_`` such as ``_metadata.yaml``), validates
        each against the JSON Schema, and stores the parsed data for
        later querying.

        Parameters
        ----------
        standard:
            The standard identifier (subdirectory name under *kb_path*).

        Raises
        ------
        FileNotFoundError
            If the standard directory does not exist.
        KBValidationError
            If any YAML file fails schema validation.
        """
        self._standard_dir = self._kb_path / standard
        if not self._standard_dir.exists():
            raise FileNotFoundError(
                f"Standard directory does not exist: {self._standard_dir}"
            )

        # Load metadata first
        metadata_path = self._standard_dir / "_metadata.yaml"
        if metadata_path.exists():
            with open(metadata_path) as fh:
                self._metadata_raw = yaml.safe_load(fh)

        # Build validator
        validator = KBValidator(
            self._schema_path,
            metadata_path=metadata_path if metadata_path.exists() else None,
        )

        # Load and validate each criteria file
        self._criteria_files = []
        for yaml_file in sorted(self._standard_dir.glob("*.yaml")):
            if yaml_file.name.startswith("_"):
                continue
            with open(yaml_file) as fh:
                data = yaml.safe_load(fh)
            # validate_schema raises KBValidationError on failure
            validator.validate_schema(data)
            self._criteria_files.append(data)

    def validate(self) -> ValidationResult:
        """Run schema and completeness validation on the loaded KB.

        Returns
        -------
        ValidationResult
            Result with ``is_valid``, ``schema_errors``,
            ``completeness_gaps``, and ``warnings``.
        """
        result = ValidationResult()

        if not self._criteria_files:
            result.is_valid = False
            result.schema_errors.append("No criteria files loaded.")
            return result

        metadata_path = (
            self._standard_dir / "_metadata.yaml"
            if self._standard_dir
            else None
        )

        validator = KBValidator(
            self._schema_path,
            metadata_path=str(metadata_path) if metadata_path and metadata_path.exists() else None,
        )

        # Schema validation (already done at load time, but re-check)
        for cf in self._criteria_files:
            try:
                validator.validate_schema(cf)
            except KBValidationError as exc:
                result.is_valid = False
                result.schema_errors.append(str(exc))

        # Completeness validation
        if self._metadata_raw is not None:
            report = validator.validate_completeness(
                self._criteria_files, metadata=self._metadata_raw
            )
            if not report.is_complete:
                result.is_valid = False
                for gap in report.missing_entries:
                    result.completeness_gaps.append(
                        f"{gap.get('process_group', '?')}: "
                        f"{gap.get('process_attribute', '?')} "
                        f"(CL{gap.get('capability_level', '?')}) — "
                        f"{gap.get('reason', 'unknown')}"
                    )
        else:
            result.warnings.append(
                "No metadata file found; completeness validation skipped."
            )

        return result

    def get_criteria(
        self,
        process_groups: list[str],
        max_capability_level: int,
    ) -> list[CriteriaEntry]:
        """Retrieve criteria filtered by process groups and capability level.

        Converts the loaded YAML data into :class:`CriteriaEntry` objects:

        - **CL1 (PA 1.1):** One entry per base practice per process.
        - **CL2–5:** One entry per generic practice, applicable to all
          processes in the group.

        Parameters
        ----------
        process_groups:
            List of process group codes (e.g. ``["SWE", "MAN"]``).
        max_capability_level:
            Include criteria up to and including this level (1–5).

        Returns
        -------
        list[CriteriaEntry]
            Matching criteria entries.
        """
        entries: list[CriteriaEntry] = []

        for cf in self._criteria_files:
            pg = cf.get("process_group", {})
            group_code = pg.get("code", "")

            if group_code not in process_groups:
                continue

            # --- CL1: base practices per process ---
            if max_capability_level >= 1:
                for proc in cf.get("processes", []):
                    entries.extend(
                        self._base_practice_entries(group_code, proc)
                    )

            # --- CL2–5: generic practices ---
            gp_section = cf.get("generic_practices", {}) or {}
            for _pa_key, pa_data in gp_section.items():
                cl = pa_data.get("capability_level", 0)
                if cl > max_capability_level:
                    continue
                entries.extend(
                    self._generic_practice_entries(group_code, pa_data)
                )

        return entries

    def get_metadata(self) -> KBMetadata:
        """Load and return metadata for the loaded standard.

        Returns
        -------
        KBMetadata
            Metadata including standard name, version, process groups, etc.

        Raises
        ------
        FileNotFoundError
            If no metadata has been loaded.
        """
        if self._metadata_raw is None:
            raise FileNotFoundError(
                "No metadata loaded. Call load() first or ensure "
                "_metadata.yaml exists in the standard directory."
            )

        meta = self._metadata_raw
        std = meta.get("standard", meta)

        return KBMetadata(
            standard_name=std.get("name", ""),
            short_name=std.get("short_name", ""),
            version=std.get("version", ""),
            release_date=std.get("release_date", ""),
            source_references=std.get("source_references", []),
            license_note=std.get("license_note", ""),
            kb_version=meta.get("kb_version", ""),
            last_updated=meta.get("last_updated", ""),
            process_groups=meta.get("process_groups", []),
            capability_levels=meta.get("capability_levels", []),
            rating_scale=meta.get("rating_scale", []),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _base_practice_entries(
        group_code: str,
        process: dict[str, Any],
    ) -> list[CriteriaEntry]:
        """Convert a process's base practices into CriteriaEntry objects."""
        entries: list[CriteriaEntry] = []
        process_id = process.get("process_id", "")
        process_name = process.get("process_name", "")

        # Build expected_evidence from output_information_items
        expected_evidence = [
            {"type": item.get("item_id", ""), "description": item.get("name", "")}
            for item in process.get("output_information_items", [])
        ]

        for bp in process.get("base_practices", []):
            bp_id = bp.get("bp_id", "")
            description = bp.get("description", "")
            notes = bp.get("notes", [])

            # Build evaluation guidance from description + notes
            guidance_parts = [description]
            guidance_parts.extend(notes)
            evaluation_guidance = " ".join(guidance_parts)

            entries.append(
                CriteriaEntry(
                    process_group=group_code,
                    process_id=process_id,
                    process_name=process_name,
                    capability_level=1,
                    process_attribute="PA 1.1",
                    process_attribute_name="Process performance",
                    criteria_id=f"{process_id}-{bp_id}",
                    description=description,
                    expected_evidence=expected_evidence,
                    evaluation_guidance=evaluation_guidance,
                    example_evidence=process.get("example_evidence", []),
                )
            )
        return entries

    @staticmethod
    def _generic_practice_entries(
        group_code: str,
        pa_data: dict[str, Any],
    ) -> list[CriteriaEntry]:
        """Convert a generic practice PA section into CriteriaEntry objects."""
        entries: list[CriteriaEntry] = []
        pa_id = pa_data.get("process_attribute_id", "")
        pa_name = pa_data.get("process_attribute_name", "")
        cl = pa_data.get("capability_level", 0)

        # Build expected_evidence from output_information_items if present
        expected_evidence = [
            {"type": item.get("item_id", ""), "description": item.get("name", "")}
            for item in pa_data.get("output_information_items", [])
        ]

        for gp in pa_data.get("practices", []):
            gp_id = gp.get("gp_id", "")
            description = gp.get("description", "")
            notes = gp.get("notes", [])

            guidance_parts = [description]
            guidance_parts.extend(notes)
            evaluation_guidance = " ".join(guidance_parts)

            entries.append(
                CriteriaEntry(
                    process_group=group_code,
                    process_id=group_code,
                    process_name="",
                    capability_level=cl,
                    process_attribute=pa_id,
                    process_attribute_name=pa_name,
                    criteria_id=f"{group_code}-{gp_id}",
                    description=description,
                    expected_evidence=expected_evidence,
                    evaluation_guidance=evaluation_guidance,
                    example_evidence=pa_data.get("example_evidence", []),
                )
            )
        return entries
