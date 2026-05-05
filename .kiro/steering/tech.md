# Tech Stack

## Language & Runtime

- **Python 3.10+** — uses `from __future__ import annotations` for modern type hints
- Type hints use `str | None` union syntax (PEP 604)

## Build System

- **setuptools** (≥68.0) with `pyproject.toml` — no `setup.py` or `setup.cfg`
- Both packages use `[tool.setuptools.packages.find]` with `where = ["src"]` (src layout)
- CLI entry points defined in `[project.scripts]`

## Key Dependencies

| Dependency | Purpose |
|---|---|
| click | CLI framework for all commands |
| pyyaml | YAML parsing for knowledge base files |
| jsonschema | Schema validation for KB criteria |
| atlassian-python-api | Confluence Cloud REST API client |
| requests | HTTP client |
| boto3 (optional) | Amazon Bedrock AI provider |
| openai (optional) | OpenAI AI provider |
| anthropic (optional) | Anthropic AI provider |

## Testing

- **pytest** — test runner, configured in `pyproject.toml` under `[tool.pytest.ini_options]`
- **hypothesis** — property-based testing framework, used extensively
  - CI profile: 100 examples per property
  - Dev profile: 50 examples per property
  - Configured in `tests/conftest.py`
- Tests are organized into `unit/`, `property/`, and `integration/` directories

## Common Commands

```bash
# Install aspice-eval in dev mode (from aspice-eval/ directory)
pip install -e ".[dev,all]"

# Install confluence-exporter in dev mode (from confluence-exporter/ directory)
pip install -e ".[dev,all]"

# Run all tests for aspice-eval
pytest                                    # from aspice-eval/
pytest tests/unit/                        # unit tests only
pytest tests/property/                    # property-based tests only
pytest tests/integration/                 # integration tests only

# Run all tests for confluence-exporter
pytest                                    # from confluence-exporter/

# Run a specific property test
pytest tests/property/test_prop01_criteria_filtering.py -v

# Run with dev hypothesis profile (faster, 50 examples)
pytest --hypothesis-profile=dev

# Validate the ASPICE knowledge base
aspice-eval validate-kb --kb-path knowledge_base

# Validate KB YAML files against schema (script)
python scripts/validate_yaml.py
```

## Optional Dependency Groups

Both packages use extras for optional AI providers:
- `[dev]` — pytest, hypothesis, pytest-mock
- `[bedrock]` — boto3
- `[openai]` — openai
- `[anthropic]` — anthropic
- `[all]` — all providers
- `[analyze]` — (aspice-eval only) adds confluence-exporter dependency
