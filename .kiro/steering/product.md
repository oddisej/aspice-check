# Product Overview

ASPICE Evaluation Toolkit — an AI-powered CLI toolset that automates Automotive SPICE (ASPICE) v4.0 compliance self-assessment.

## What It Does

The toolkit exports a Software Development Plan (SDP) from Confluence, evaluates it against a structured ASPICE v4.0 knowledge base using an AI model, and publishes a gap analysis report back to Confluence as a child page.

## Core Tools

| CLI Command | Package | Purpose |
|---|---|---|
| `aspice-analyze` | aspice-eval | Full pipeline: export → evaluate → publish (single command) |
| `aspice-eval evaluate` | aspice-eval | Evaluate a local Markdown SDP against ASPICE criteria |
| `aspice-eval validate-kb` | aspice-eval | Validate the ASPICE knowledge base for completeness |
| `confluence-export` | confluence-exporter | Export a Confluence page to Markdown with images and AI diagram descriptions |

## Key Concepts

- **Knowledge Base (KB)**: Structured YAML files containing ASPICE v4.0 criteria for process groups (SWE, SYS, MAN, SUP) across capability levels 0–5. Deterministic, not AI-generated.
- **Gap Analysis**: AI evaluates the SDP against KB criteria, producing per-criteria ratings on the ASPICE 4-point scale (Fully/Largely/Partially/Not achieved).
- **Capability Levels**: Calculated from individual criteria ratings per process group, with blocking attribute detection.
- **Gliffy Diagrams**: Process flow diagrams from Confluence are exported as images and transcribed to text via AI so they can be evaluated.

## AI Providers

Both packages support multiple AI providers via a factory pattern with lazy imports:
- **Amazon Bedrock** (default) — Claude Sonnet via AWS credential chain
- **OpenAI** — GPT-4o
- **Anthropic** — Claude Sonnet via API key
