"""Knowledge base validator for ASPICE criteria files.

Validates KB YAML files against the JSON Schema and checks completeness
to ensure every expected (process_group, capability_level, process_attribute)
tuple is covered.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import yaml
from jsonschema import Draft7Validator, ValidationError

from aspice_eval.exceptions import KBValidationError
from aspice_eval.models import CompletenessReport


# PA keys in the generic_practices section, mapped to their capability level
_EXPECTED_GENERIC_PAS: dict[str, tuple[str, int]] = {
    "PA_2_1": ("PA 2.1", 2),
    "PA_2_2": ("PA 2.2", 2),
    "PA_3_1": ("PA 3.1", 3),
    "PA_3_2": ("PA 3.2", 3),
    "PA_4_1": ("PA 4.1", 4),
    "PA_4_2": ("PA 4.2", 4),
    "PA_5_1": ("PA 5.1", 5),
    "PA_5_2": ("PA 5.2", 5),
}


class KBValidator:
    """Validates knowledge base structure and completeness.

    Parameters
    ----------
    schema_path:
        Path to the ``criteria_schema.json`` file used for schema validation.
    metadata_path:
        Optional path to the ``_metadata.yaml`` file. When provided, the
        completeness check uses the metadata to determine which processes
        are expected per group.
    """

    def __init__(
        self,
        schema_path: str | pathlib.Path,
        metadata_path: str | pathlib.Path | None = None,
    ) -> None:
        self._schema_path = pathlib.Path(schema_path)
        self._schema = self._load_schema()
        self._validator = Draft7Validator(self._schema)
        self._metadata: dict[str, Any] | None = None
        if metadata_path is not None:
            self._metadata = self._load_metadata(pathlib.Path(metadata_path))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_schema(self, criteria_file: dict[str, Any]) -> list[ValidationError]:
        """Validate a parsed YAML dict against the criteria JSON Schema.

        Parameters
        ----------
        criteria_file:
            A dictionary representing a parsed KB YAML file (e.g. ``swe.yaml``).

        Returns
        -------
        list[ValidationError]
            A list of ``jsonschema.ValidationError`` objects. Empty when valid.

        Raises
        ------
        KBValidationError
            When the file has schema violations. The exception carries the
            list of errors for programmatic access.
        """
        errors = list(self._validator.iter_errors(criteria_file))
        if errors:
            messages = [e.message for e in errors]
            raise KBValidationError(
                f"Schema validation failed with {len(errors)} error(s): "
                + "; ".join(messages),
                errors=[
                    {"message": e.message, "path": list(e.absolute_path)}
                    for e in errors
                ],
            )
        return errors

    def validate_completeness(
        self,
        criteria_files: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> CompletenessReport:
        """Check that the KB covers all expected process/PA combinations.

        For **CL1** (PA 1.1): every process listed in the metadata must have
        at least one base practice in the corresponding criteria file.

        For **CL2–5**: the ``generic_practices`` section of each criteria file
        must contain entries for all eight expected PAs (PA 2.1 through PA 5.2).

        Parameters
        ----------
        criteria_files:
            List of parsed YAML dicts — one per process group file.
        metadata:
            Parsed ``_metadata.yaml`` dict. Falls back to the metadata
            provided at construction time if *None*.

        Returns
        -------
        CompletenessReport
            Report with ``is_complete``, ``missing_entries``,
            ``total_expected``, and ``total_found`` fields.
        """
        meta = metadata or self._metadata
        if meta is None:
            raise ValueError(
                "Metadata is required for completeness validation. "
                "Provide it via the constructor or as an argument."
            )

        # Build a lookup: group_code -> parsed criteria file dict
        file_by_group: dict[str, dict[str, Any]] = {}
        for cf in criteria_files:
            pg = cf.get("process_group", {})
            code = pg.get("code", "")
            if code:
                file_by_group[code] = cf

        missing: list[dict[str, Any]] = []
        total_expected = 0
        total_found = 0

        process_groups = meta.get("process_groups", [])

        for pg in process_groups:
            group_code = pg.get("code", "")
            expected_processes = pg.get("processes", [])
            cf = file_by_group.get(group_code)

            # --- CL1 check: each process must have base_practices -----------
            for proc_id in expected_processes:
                total_expected += 1
                if cf is None:
                    missing.append(
                        {
                            "process_group": group_code,
                            "capability_level": 1,
                            "process_attribute": "PA 1.1",
                            "process_id": proc_id,
                            "reason": f"No criteria file found for group {group_code}",
                        }
                    )
                    continue

                # Find the process in the file's processes list
                found = False
                for proc in cf.get("processes", []):
                    if proc.get("process_id") == proc_id:
                        bps = proc.get("base_practices", [])
                        if bps:
                            found = True
                        break

                if found:
                    total_found += 1
                else:
                    missing.append(
                        {
                            "process_group": group_code,
                            "capability_level": 1,
                            "process_attribute": "PA 1.1",
                            "process_id": proc_id,
                            "reason": (
                                f"Process {proc_id} has no base practices "
                                f"(CL1 / PA 1.1)"
                            ),
                        }
                    )

            # --- CL2–5 check: generic_practices must cover all PAs ---------
            for pa_key, (pa_id, cl) in _EXPECTED_GENERIC_PAS.items():
                total_expected += 1
                if cf is None:
                    missing.append(
                        {
                            "process_group": group_code,
                            "capability_level": cl,
                            "process_attribute": pa_id,
                            "reason": f"No criteria file found for group {group_code}",
                        }
                    )
                    continue

                gp_section = cf.get("generic_practices", {}) or {}
                pa_entry = gp_section.get(pa_key)
                if pa_entry and pa_entry.get("practices"):
                    total_found += 1
                else:
                    missing.append(
                        {
                            "process_group": group_code,
                            "capability_level": cl,
                            "process_attribute": pa_id,
                            "reason": (
                                f"Missing generic practices for {pa_id} "
                                f"(CL{cl}) in group {group_code}"
                            ),
                        }
                    )

        return CompletenessReport(
            is_complete=len(missing) == 0,
            missing_entries=missing,
            total_expected=total_expected,
            total_found=total_found,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_schema(self) -> dict[str, Any]:
        """Load and return the JSON Schema from disk."""
        with open(self._schema_path) as fh:
            return json.load(fh)

    @staticmethod
    def _load_metadata(path: pathlib.Path) -> dict[str, Any]:
        """Load and return the _metadata.yaml file."""
        with open(path) as fh:
            return yaml.safe_load(fh)
