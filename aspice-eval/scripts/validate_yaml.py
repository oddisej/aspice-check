"""Validate YAML KB files against the JSON Schema."""
from __future__ import annotations

import json
import pathlib
import sys

import jsonschema
import yaml


def validate_file(yaml_path: pathlib.Path, schema: dict) -> bool:
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    try:
        jsonschema.validate(data, schema)
        print(f"Schema validation: PASSED for {yaml_path}")
    except jsonschema.ValidationError as e:
        print(f"Schema validation: FAILED for {yaml_path}")
        print(f"Error: {e.message}")
        print(f"Path: {list(e.absolute_path)}")
        return False

    processes = data.get("processes", [])
    total_bps = sum(len(p.get("base_practices", [])) for p in processes)
    gps = data.get("generic_practices", {})
    total_gps = sum(len(v.get("practices", [])) for v in gps.values()) if gps else 0

    print(f"  Processes: {len(processes)}, Base Practices: {total_bps}, Generic Practices: {total_gps}")
    for p in processes:
        bps = len(p.get("base_practices", []))
        oiis = len(p.get("output_information_items", []))
        outcomes = len(p.get("process_outcomes", []))
        print(f"    {p['process_id']}: {p['process_name']} ({outcomes} outcomes, {bps} BPs, {oiis} OIIs)")

    return True


if __name__ == "__main__":
    base = pathlib.Path("knowledge_base")
    schema_path = base / "schema" / "criteria_schema.json"

    with open(schema_path) as f:
        schema = json.load(f)

    yaml_files = sorted(
        f for f in (base / "aspice").glob("*.yaml") if not f.name.startswith("_")
    )

    if not yaml_files:
        print("No YAML criteria files found.")
        sys.exit(1)

    all_ok = True
    for yf in yaml_files:
        ok = validate_file(yf, schema)
        if not ok:
            all_ok = False
        print()

    sys.exit(0 if all_ok else 1)
