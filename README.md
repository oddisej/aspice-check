# ASPICE Evaluation Toolkit

An AI-powered tool that automatically evaluates your Software Development Process against Automotive SPICE (ASPICE) criteria and publishes the gap analysis report to Confluence.

## What it does

**aspice-eval** is a set of Python CLI tools that automate ASPICE compliance self-assessment. Point it at your SDP page in Confluence, and it will export the content (including Gliffy diagrams with AI-generated descriptions), evaluate it against a structured ASPICE v4.0 knowledge base using Amazon Bedrock, and publish a detailed gap analysis report as a child page — all in a single command. Teams can self-assess before formal audits, track compliance progress across capability levels, and get actionable remediation recommendations.

## Tools

| Tool | Purpose |
|---|---|
| `aspice-analyze` | Single command that runs the full pipeline: export → evaluate → publish |
| `aspice-eval evaluate` | Evaluate a local Markdown SDP against ASPICE criteria |
| `aspice-eval validate-kb` | Validate the ASPICE knowledge base for completeness |
| `confluence-export` | Export a Confluence page to Markdown with images and AI diagram descriptions |

## How it works

```
Confluence SDP Page
        │
        ▼
   ┌─────────────────┐
   │  Export Stage    │  Retrieves page, downloads Gliffy diagrams,
   │  (confluence-    │  generates AI descriptions of process flows
   │   exporter)      │
   └────────┬────────┘
            │  Markdown + images
            ▼
   ┌─────────────────┐
   │  Evaluate Stage  │  Loads ASPICE v4.0 knowledge base,
   │  (aspice-eval)   │  sends SDP + criteria to AI for gap analysis,
   │                   │  calculates capability levels
   └────────┬────────┘
            │  Gap analysis report
            ▼
   ┌─────────────────┐
   │  Publish Stage   │  Converts report to Confluence format,
   │  (Confluence API) │  creates/updates child page under SDP
   └────────┬────────┘
            │
            ▼
   Confluence Child Page: "ASPICE Gap Analysis L1 - Your SDP"
```

## Quick Start

```bash
# Install via HTTPS (no clone needed)
pip install "confluence-exporter[bedrock] @ git+https://github.com/oddisej/aspice-check.git#subdirectory=confluence-exporter"
pip install "aspice-eval[analyze,bedrock] @ git+https://github.com/oddisej/aspice-check.git#subdirectory=aspice-eval"
pip install "botocore[crt]"

# Or install via SSH
pip install "confluence-exporter[bedrock] @ git+ssh://git@github.com/oddisej/aspice-check.git#subdirectory=confluence-exporter"
pip install "aspice-eval[analyze,bedrock] @ git+ssh://git@github.com/oddisej/aspice-check.git#subdirectory=aspice-eval"
pip install "botocore[crt]"

# Set credentials
export CONFLUENCE_EMAIL="your.email@company.com"
export CONFLUENCE_API_TOKEN="your-token"
export AWS_DEFAULT_REGION="eu-west-1"

# Run the full pipeline
aspice-analyze \
  "https://your-instance.atlassian.net/wiki/spaces/SPACE/pages/12345/Your+SDP+Page" \
  --target-level 1 \
  --groups SWE
```

## Key Capabilities

- **ASPICE v4.0 knowledge base** with criteria for SWE, SYS, MAN, SUP process groups across capability levels 0–5
- **AI-powered evaluation** using Amazon Bedrock (Claude Sonnet), OpenAI, or Anthropic
- **Visual content understanding** — Gliffy process flow diagrams are transcribed to text so the AI can evaluate them
- **Structured reports** with executive summary, per-criteria ratings (ASPICE 4-point scale), evidence citations, gap identification, remediation roadmap, and traceability matrix
- **Confluence integration** — reads SDP from Confluence, publishes report back as a child page
- **Deterministic knowledge base** — ASPICE criteria are structured YAML, not AI-generated, ensuring consistent evaluation scope

## Repository Structure

```
aspice-check/
├── aspice-eval/          # ASPICE evaluation engine + aspice-analyze command
│   ├── src/aspice_eval/  # Source code
│   ├── knowledge_base/   # ASPICE v4.0 criteria (YAML)
│   ├── scripts/          # Utility scripts (publish, convert)
│   └── tests/            # Unit + property-based tests
├── confluence-exporter/  # Confluence page export tool
│   ├── src/confluence_exporter/
│   └── tests/
└── files/                # Reference documents
```

## Documentation

- [aspice-eval README](aspice-eval/README.md) — Full documentation for the evaluation tool and `aspice-analyze` command
- [confluence-exporter README](confluence-exporter/README.md) — Documentation for the Confluence export tool

## License

MIT
