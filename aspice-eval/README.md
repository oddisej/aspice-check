# aspice-eval

ASPICE evaluation engine — knowledge base, gap analysis evaluator, and reports.

## Library Usage

### Evaluate an SDP

```python
from aspice_eval import evaluate_sdp, ModelConfig

result = evaluate_sdp(
    "docs/sdp.md",
    ModelConfig(
        provider="bedrock",
        model_name="us.anthropic.claude-sonnet-4-20250514-v1:0",
        region="us-east-1",
    ),
    target_level=3,
    process_groups=["SWE", "SYS"],
)

print(f"Criteria assessed: {len(result.ratings)}")
print(f"Gaps found: {len([r for r in result.ratings if r.gaps])}")
print(f"Tokens used: {result.token_usage['total_tokens']}")
```

### Validate a Knowledge Base

```python
from aspice_eval import validate_kb

result = validate_kb("knowledge_base")

if not result.is_valid:
    for error in result.schema_errors:
        print(f"Schema error: {error}")
    for gap in result.completeness_gaps:
        print(f"Completeness gap: {gap}")
else:
    print("Knowledge base is valid")
```

## Extension Points

### Custom Evaluator

Subclass `GapAnalysisEvaluator` to plug in a custom LLM provider or rule-based engine:

```python
from aspice_eval import GapAnalysisEvaluator, ModelConfig, register_evaluator

class LocalLlamaEvaluator(GapAnalysisEvaluator):
    """Evaluator using a local Llama model."""

    def _call_model(self, prompt: str) -> str:
        # Call your local model and return JSON response
        ...

# Register the custom provider
register_evaluator("local-llama", LocalLlamaEvaluator)

# Use it via the standard factory
from aspice_eval import create_evaluator

evaluator = create_evaluator(ModelConfig(provider="local-llama"))
```

### Custom Knowledge Base Standards

Three levels of extensibility for non-ASPICE standards:

**Level 1 — Custom YAML files (no code required):**

Drop a new subdirectory under the KB root with YAML files conforming to the criteria schema:

```
knowledge_base/
├── aspice/          # Built-in ASPICE v4.0
└── iso26262/        # Your custom standard
    ├── _metadata.yaml
    └── functional_safety.yaml
```

```python
from aspice_eval import evaluate_sdp, ModelConfig

result = evaluate_sdp(
    "docs/sdp.md",
    ModelConfig(provider="bedrock", model_name="...", region="us-east-1"),
    standard="iso26262",
)
```

**Level 2 — In-memory construction via `from_dict`:**

```python
from aspice_eval import KnowledgeBase

kb = KnowledgeBase.from_dict({
    "processes": [
        {
            "process_id": "SWE.1",
            "process_name": "Software Requirements Analysis",
            "criteria": [...],
        }
    ]
})
criteria = kb.get_criteria(groups=["SWE"], max_level=3)
```

**Level 3 — Custom KB loader (pluggable schema):**

For standards with fundamentally different structures, subclass `KnowledgeBase` and register a loader:

```python
from aspice_eval import KnowledgeBase, register_kb_loader, CriteriaEntry

class NISTCSFKnowledgeBase(KnowledgeBase):
    """Custom loader for NIST Cybersecurity Framework."""

    def load(self, standard: str) -> None:
        # Read NIST-shaped YAML/JSON, convert to CriteriaEntry list
        ...

    def get_criteria(self, groups, max_level) -> list[CriteriaEntry]:
        # Return entries filtered by NIST "Functions" instead of ASPICE groups
        ...

register_kb_loader("nist-csf", NISTCSFKnowledgeBase)
```

### Custom Report Renderer

Subclass `ReportRenderer` to output evaluation results in formats beyond Markdown and HTML:

```python
from aspice_eval import ReportRenderer, register_renderer
from aspice_eval import EvaluationResult, CapabilityLevelResult, EvaluationConfig

class JSONReportRenderer(ReportRenderer):
    """Render evaluation results as JSON."""

    def render(self, evaluation, levels, config, kb_metadata) -> str:
        import json
        return json.dumps({
            "ratings": [
                {"criteria_id": r.criteria_id, "rating": r.rating, "gaps": r.gaps}
                for r in evaluation.ratings
            ],
        }, indent=2)

# Register and use
register_renderer("json", JSONReportRenderer)
```

## CLI Usage

### aspice-eval evaluate

```bash
# Evaluate an SDP document
aspice-eval evaluate --sdp path/to/sdp.md --target-level 2 --groups SWE,MAN

# Write report to a file
aspice-eval evaluate --sdp path/to/sdp.md --output report.md

# Use a specific AI provider
aspice-eval evaluate --sdp path/to/sdp.md --provider bedrock \
  --model us.anthropic.claude-sonnet-4-20250514-v1:0 --region us-east-1
```

### aspice-eval validate-kb

```bash
# Validate the default knowledge base
aspice-eval validate-kb

# Validate a custom knowledge base
aspice-eval validate-kb --kb-path /path/to/knowledge_base
```

## Installation

```bash
pip install aspice-eval

# With AI provider support
pip install "aspice-eval[bedrock]"     # Amazon Bedrock (Claude)
pip install "aspice-eval[openai]"      # OpenAI GPT-4o
pip install "aspice-eval[anthropic]"   # Anthropic Claude (direct API)
pip install "aspice-eval[all]"         # All providers
```

Requires Python 3.10+.

## License

MIT
