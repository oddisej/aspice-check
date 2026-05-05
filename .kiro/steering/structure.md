# Project Structure

## Monorepo Layout

This is a Python monorepo with two independent packages that share no code at the source level. `aspice-eval` depends on `confluence-exporter` at runtime (via the `[analyze]` extra) for the `aspice-analyze` pipeline command.

```
aspice-check/                         # Repository root
├── aspice-eval/                      # ASPICE evaluation engine + aspice-analyze command
│   ├── src/aspice_eval/              # Source (src layout)
│   │   ├── cli.py                    # Click CLI: evaluate, validate-kb, version
│   │   ├── analyze.py                # aspice-analyze pipeline command (export → evaluate → publish)
│   │   ├── models.py                 # Core dataclasses (CriteriaEntry, CriteriaRating, EvaluationConfig, etc.)
│   │   ├── exceptions.py             # Structured exception hierarchy
│   │   ├── knowledge_base.py         # KB loader, criteria filtering, validation
│   │   ├── kb_validator.py           # Schema + completeness validation
│   │   ├── evaluator.py              # Base evaluator + MockEvaluator
│   │   ├── level_calculator.py       # Capability level calculation from ratings
│   │   ├── report_generator.py       # Markdown/HTML report generation
│   │   ├── sdp_ingester.py           # SDP document ingestion (Markdown only)
│   │   └── providers/                # AI provider implementations (factory pattern)
│   │       ├── __init__.py           # create_evaluator() factory with lazy imports
│   │       ├── bedrock.py            # Amazon Bedrock evaluator
│   │       ├── openai_provider.py    # OpenAI evaluator
│   │       └── anthropic_provider.py # Anthropic evaluator
│   ├── knowledge_base/               # ASPICE v4.0 criteria (YAML, deterministic)
│   │   ├── aspice/                   # Standard-specific criteria files
│   │   │   ├── _metadata.yaml        # Standard metadata, process groups, capability levels
│   │   │   ├── swe.yaml              # Software Engineering process group
│   │   │   ├── sys.yaml              # System Engineering process group
│   │   │   ├── man.yaml              # Management process group
│   │   │   └── sup.yaml              # Support process group
│   │   └── schema/
│   │       └── criteria_schema.json  # JSON Schema for criteria YAML validation
│   ├── tests/
│   │   ├── conftest.py               # Hypothesis profiles (ci=100, dev=50)
│   │   ├── unit/                     # Unit tests
│   │   ├── property/                 # Property-based tests (test_propNN_*.py naming)
│   │   └── integration/              # Integration tests
│   ├── scripts/                      # Utility scripts (extraction, publishing, validation)
│   └── pyproject.toml
│
├── confluence-exporter/              # Confluence page export tool
│   ├── src/confluence_exporter/      # Source (src layout)
│   │   ├── cli.py                    # Click CLI: confluence-export command
│   │   ├── models.py                 # IR content nodes, API models, config models
│   │   ├── exceptions.py             # Exporter exception hierarchy
│   │   ├── client.py                 # Confluence REST API client
│   │   ├── parser.py                 # XHTML storage format → IR nodes
│   │   ├── downloader.py             # Asset (image/Gliffy) downloader
│   │   ├── describer.py              # ImageDescriber base class
│   │   ├── renderer.py               # IR nodes → Markdown renderer
│   │   └── providers/                # AI image description providers (factory pattern)
│   │       ├── __init__.py           # create_describer() factory with lazy imports
│   │       ├── anthropic_describer.py
│   │       ├── openai_describer.py
│   │       └── bedrock_describer.py
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── unit/
│   │   ├── property/
│   │   └── integration/
│   └── pyproject.toml
│
└── .kiro/specs/                      # Kiro spec files for features
```

## Architecture Patterns

- **src layout**: All source code lives under `src/<package_name>/`, configured via `[tool.setuptools.packages.find] where = ["src"]`
- **Factory + lazy imports**: Both packages use a provider factory (`create_evaluator`, `create_describer`) with a registry dict mapping provider names to fully-qualified class paths. Dependencies are imported only when the provider is selected.
- **Dataclasses everywhere**: Models are plain `@dataclass` classes — no Pydantic, no attrs.
- **Click CLI**: All CLI commands use Click decorators. Entry points are registered in `pyproject.toml` `[project.scripts]`.
- **Structured exceptions**: Custom exception classes carry context fields (file paths, parameter names, actual/expected values) for actionable error messages.
- **Docstrings**: Modules and public functions use Google/NumPy-style docstrings. Module docstrings include `Requirements:` references linking to spec requirements.

## Test Naming Conventions

- Property tests: `test_propNN_<description>.py` (e.g., `test_prop01_criteria_filtering.py`)
- Unit tests: `test_<module>.py` (e.g., `test_models.py`, `test_analyze.py`)
- Integration tests: `test_cli_<command>.py`
