# Requirements Document — ASPICE Knowledge Base & Agent Workflow

## Introduction

This spec defines a **structured ASPICE criteria knowledge base** paired with an **agentic AI workflow** that evaluates Software Development Process (SDP) documents against Automotive SPICE (ASPICE) compliance criteria. Rather than building a deterministic rule-based parser, the system leverages a comprehensive, machine-readable knowledge base as context for an AI agent that performs qualitative gap analysis on natural-language SDP documents.

### Motivation

- ASPICE compliance assessment is currently a manual, expert-driven activity
- SDP documents are natural-language artifacts with varying structure, making deterministic parsing brittle and low-value
- An AI agent with structured ASPICE criteria context can perform qualitative judgment that closely mirrors human assessor reasoning
- A well-structured knowledge base delivers 80% of the value of a full deterministic tool with significantly less development effort
- The knowledge base is independently valuable as a reference artifact and can be extended to other standards (CMMI, ISO 26262, IEC 62304)
- Designed for potential open-source distribution

### Key Input Documents

- `files/aspice_compliance_reference.md` — ASPICE capability levels, process attributes, and process groups
- `files/PS_SE_Software_Development_Process.md` — Current SDP (baseline for evaluation)

## Glossary

- **Knowledge_Base**: A structured, machine-readable collection of ASPICE criteria organized by capability level, process attribute, and process group, stored in a format suitable for AI agent consumption (YAML, JSON, or Markdown)
- **Agent**: An AI-powered workflow component that consumes the Knowledge_Base and an SDP document to produce a compliance evaluation
- **SDP_Document**: A Software Development Process document in Markdown format describing process steps, roles, work products, metrics, quality gates, and traceability chains
- **Gap_Analysis_Report**: The structured output of an Agent evaluation, identifying satisfied, partially satisfied, and missing ASPICE criteria for a given SDP_Document
- **Capability_Level**: One of six ASPICE maturity levels (0–5) that describe the degree to which a process is implemented, managed, established, predictable, or optimizing
- **Process_Attribute**: A measurable characteristic of process capability (PA 1.1 through PA 5.2) used to determine the Capability_Level achieved
- **Process_Group**: A category of related processes in ASPICE (SWE, SYS, MAN, SUP, HWE, MLE, VAL, ACQ)
- **Information_Item**: An ASPICE 4.0 term replacing "Work Product" — any artifact that provides evidence of process execution (documents, records, code, test results)
- **Criteria_Entry**: A single evaluable criterion within the Knowledge_Base, containing the process attribute, expected evidence, and rating guidance
- **Rating_Scale**: The ASPICE four-point scale for process attribute achievement: Not achieved (0–15%), Partially achieved (16–50%), Largely achieved (51–85%), Fully achieved (86–100%)

## Requirements

### Requirement 1: Knowledge Base Structure

**User Story:** As a process engineer, I want a structured ASPICE criteria knowledge base, so that I have a comprehensive, machine-readable reference for all ASPICE evaluation criteria.

#### Acceptance Criteria

1. THE Knowledge_Base SHALL organize Criteria_Entry records hierarchically by Process_Group, Capability_Level, and Process_Attribute.
2. WHEN a Criteria_Entry is defined, THE Knowledge_Base SHALL include the following fields for each entry: process group code, process attribute identifier, capability level, expected Information_Item types, evaluation guidance text, and example evidence descriptions.
3. THE Knowledge_Base SHALL cover all six Capability_Levels (0 through 5) and all Process_Attributes from PA 1.1 through PA 5.2.
4. THE Knowledge_Base SHALL cover the following Process_Groups at minimum: SWE (Software Engineering), SYS (System Engineering), MAN (Project Management), and SUP (Support Processes).
5. THE Knowledge_Base SHALL use a structured, machine-readable format (YAML, JSON, or structured Markdown) that can be parsed programmatically and consumed as AI agent context.
6. WHEN a Criteria_Entry references expected evidence, THE Knowledge_Base SHALL describe the evidence in terms of Information_Items consistent with ASPICE 4.0 terminology.

### Requirement 2: Knowledge Base Extensibility

**User Story:** As a process engineer, I want the knowledge base to support additional compliance standards, so that the system can grow beyond ASPICE to cover CMMI, ISO 26262, and IEC 62304.

#### Acceptance Criteria

1. THE Knowledge_Base SHALL use a schema that separates standard-specific criteria from the common evaluation structure, allowing new standards to be added without modifying the base schema.
2. WHEN a new compliance standard is added, THE Knowledge_Base SHALL support it by adding new Criteria_Entry records that follow the same schema as existing ASPICE entries.
3. THE Knowledge_Base SHALL include a metadata section identifying the standard name, version, and source reference for each set of criteria.

### Requirement 3: SDP Document Ingestion

**User Story:** As a user, I want to provide an SDP document as input, so that the agent can evaluate it against ASPICE criteria.

#### Acceptance Criteria

1. WHEN an SDP_Document in Markdown format is provided, THE Agent SHALL accept the document as input for evaluation.
2. WHEN an SDP_Document is provided, THE Agent SHALL identify and extract key structural elements including: process steps, roles and responsibilities, work products or Information_Items, metrics, quality gates, review procedures, and traceability references.
3. IF an SDP_Document is provided in an unsupported format, THEN THE Agent SHALL return a descriptive error message identifying the expected format.

### Requirement 4: Agent-Driven Gap Analysis

**User Story:** As a process engineer, I want the agent to evaluate my SDP against ASPICE criteria, so that I can identify compliance gaps before a formal audit.

#### Acceptance Criteria

1. WHEN an SDP_Document and a target Capability_Level are provided, THE Agent SHALL evaluate the SDP_Document against all Criteria_Entry records in the Knowledge_Base up to and including the target Capability_Level.
2. WHEN evaluating a Criteria_Entry, THE Agent SHALL classify the SDP_Document's compliance using the Rating_Scale: Fully achieved, Largely achieved, Partially achieved, or Not achieved.
3. WHEN a Criteria_Entry is rated as Partially achieved or Not achieved, THE Agent SHALL provide a specific textual explanation identifying what evidence is missing or insufficient in the SDP_Document.
4. WHEN evaluating the SDP_Document, THE Agent SHALL assess each applicable Process_Group independently, producing per-group compliance ratings.
5. THE Agent SHALL use the Knowledge_Base as its primary reference context for all evaluation decisions, ensuring assessments are grounded in the structured criteria rather than general knowledge alone.

### Requirement 5: Capability Level Determination

**User Story:** As a process engineer, I want to know the highest ASPICE capability level my SDP achieves for each process group, so that I can understand our current maturity.

#### Acceptance Criteria

1. WHEN a gap analysis is complete, THE Agent SHALL determine the highest Capability_Level achieved for each evaluated Process_Group based on the ASPICE level achievement rules.
2. WHEN determining the achieved Capability_Level, THE Agent SHALL apply the ASPICE rule that a level is achieved only when all Process_Attributes at that level are rated Largely achieved or Fully achieved, and all lower levels are also achieved.
3. WHEN a Process_Group achieves a Capability_Level below the target, THE Agent SHALL identify the specific Process_Attributes that prevented achievement of the next level.

### Requirement 6: Gap Analysis Report Generation

**User Story:** As a process engineer, I want a structured compliance report, so that I can share findings with stakeholders and plan remediation.

#### Acceptance Criteria

1. WHEN a gap analysis is complete, THE Agent SHALL produce a Gap_Analysis_Report in structured Markdown format.
2. THE Gap_Analysis_Report SHALL include the following sections: executive summary, per-Process_Group capability level achieved, per-Process_Attribute detailed ratings with evidence citations, identified gaps with specific remediation recommendations, and an overall compliance summary.
3. WHEN a gap is identified, THE Gap_Analysis_Report SHALL include an actionable recommendation describing what the SDP_Document should add or change to address the gap.
4. THE Gap_Analysis_Report SHALL include a traceability section mapping each Criteria_Entry evaluated to the specific section(s) of the SDP_Document that were assessed as evidence.
5. THE Gap_Analysis_Report SHALL include metadata identifying the SDP_Document evaluated, the target Capability_Level, the Knowledge_Base version used, and the evaluation timestamp.

### Requirement 7: Agent Workflow Configuration

**User Story:** As a user, I want to configure the agent workflow for different evaluation scenarios, so that I can focus on specific process groups or capability levels.

#### Acceptance Criteria

1. WHEN invoking the Agent, THE Agent SHALL accept configuration parameters specifying: target Capability_Level (1 through 5), Process_Groups to evaluate (one or more of SWE, SYS, MAN, SUP), and output format preferences.
2. WHERE a subset of Process_Groups is specified, THE Agent SHALL evaluate only the specified groups and omit others from the Gap_Analysis_Report.
3. WHERE no target Capability_Level is specified, THE Agent SHALL default to evaluating against Capability_Level 3 (Established), as this is the industry standard for supplier qualification.

### Requirement 8: Knowledge Base Validation

**User Story:** As a maintainer, I want to validate the knowledge base for completeness and correctness, so that I can trust the evaluation results.

#### Acceptance Criteria

1. THE Knowledge_Base SHALL include a validation mechanism that checks for completeness: every Process_Attribute for every covered Process_Group at every Capability_Level has at least one Criteria_Entry.
2. WHEN a validation check is run, THE validation mechanism SHALL report any missing Criteria_Entry records as gaps in the Knowledge_Base.
3. THE Knowledge_Base SHALL include version metadata that is incremented when criteria are added, modified, or removed.

### Requirement 9: Open-Source Distribution Readiness

**User Story:** As a project maintainer, I want the knowledge base and agent workflow to be distributable as open source, so that the community can benefit from and contribute to the ASPICE evaluation tooling.

#### Acceptance Criteria

1. THE Knowledge_Base SHALL contain only criteria descriptions derived from publicly available ASPICE standard summaries and SHALL NOT include proprietary content requiring licensing.
2. THE Knowledge_Base SHALL include attribution references to source materials for each set of criteria.
3. THE Agent workflow SHALL be documented with clear setup instructions, usage examples, and contribution guidelines suitable for open-source distribution.
4. THE Agent workflow SHALL have no dependencies on proprietary services or tools beyond the AI model provider.
