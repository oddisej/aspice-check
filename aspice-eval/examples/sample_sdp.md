# Software Development Process (SDP)

## 1. Introduction

### 1.1 Purpose

This Software Development Process (SDP) document defines the processes, roles, work products, and quality gates governing software development for the Advanced Driver Assistance Systems (ADAS) platform. It establishes a repeatable, managed framework aligned with Automotive SPICE capability level 3 objectives.

### 1.2 Scope

This SDP applies to all embedded software components within the ADAS platform, including:

- Sensor fusion algorithms
- Object detection and classification modules
- Path planning and trajectory generation
- Vehicle control interface software
- Diagnostic and monitoring services

### 1.3 References

| Document | Version | Description |
|----------|---------|-------------|
| ADAS System Requirements Specification | 2.1 | System-level requirements |
| Software Architecture Document | 1.4 | High-level and detailed design |
| Configuration Management Plan | 1.2 | CM procedures and tooling |
| Quality Assurance Plan | 1.1 | QA activities and metrics |
| Project Management Plan | 3.0 | Schedule, resources, risk management |

### 1.4 Definitions and Abbreviations

- **ADAS** — Advanced Driver Assistance Systems
- **SRS** — Software Requirements Specification
- **SAD** — Software Architecture Document
- **SDD** — Software Detailed Design Document
- **CI/CD** — Continuous Integration / Continuous Deployment
- **MISRA** — Motor Industry Software Reliability Association
- **PA** — Process Attribute
- **CL** — Capability Level

---

## 2. Project Management (MAN.3)

### 2.1 Project Planning

The project follows an iterative development lifecycle with 4-week sprint cycles. Planning activities include:

- **Work Breakdown Structure (WBS):** Maintained in Jira, decomposing the project into epics, features, and user stories linked to system requirements.
- **Schedule:** A master schedule in MS Project defines milestones, dependencies, and critical path. Sprint-level planning occurs during sprint planning ceremonies.
- **Resource Allocation:** Team members are assigned to tasks based on skill matrix and availability. Resource conflicts are escalated to the program manager.
- **Effort Estimation:** Story points and historical velocity data drive effort estimates. Estimates are reviewed during sprint planning.

### 2.2 Project Monitoring and Control

- **Sprint Reviews:** Held every 4 weeks to demonstrate completed work and gather stakeholder feedback.
- **Burndown Charts:** Updated daily in Jira to track sprint progress against planned velocity.
- **Risk Register:** Maintained in Confluence with risk identification, probability/impact assessment, mitigation strategies, and status tracking. Reviewed bi-weekly.
- **Issue Tracking:** All defects, impediments, and action items tracked in Jira with priority, assignee, and target resolution date.
- **Status Reporting:** Weekly status reports distributed to stakeholders covering progress, risks, issues, and upcoming milestones.

### 2.3 Roles and Responsibilities

| Role | Responsibility |
|------|---------------|
| Project Manager | Overall project planning, monitoring, risk management, stakeholder communication |
| Technical Lead | Architecture decisions, technical guidance, code review oversight |
| Software Engineer | Implementation, unit testing, code reviews |
| QA Engineer | Test planning, test execution, defect reporting |
| Requirements Engineer | Requirements elicitation, analysis, traceability management |
| Configuration Manager | Build management, version control, release packaging |

---

## 3. System Engineering (SYS)

### 3.1 System Requirements Analysis (SYS.1)

System requirements are elicited from stakeholders through workshops, document analysis, and prototype reviews. Requirements are documented in the System Requirements Specification (SRS) using DOORS.

- **Elicitation:** Structured interviews and workshops with OEM stakeholders, safety engineers, and end users.
- **Documentation:** Each requirement has a unique ID, description, rationale, priority, acceptance criteria, and source reference.
- **Classification:** Requirements are categorized as functional, performance, safety, or interface requirements.
- **Feasibility Analysis:** Technical feasibility is assessed for each requirement during the analysis phase.

### 3.2 System Architecture Design (SYS.2)

The system architecture decomposes the ADAS platform into subsystems:

- Perception Subsystem (sensor fusion, object detection)
- Planning Subsystem (path planning, decision making)
- Control Subsystem (vehicle interface, actuator control)
- Infrastructure Subsystem (communication, diagnostics)

Architecture decisions are documented in the System Architecture Document with rationale, alternatives considered, and traceability to system requirements.

### 3.3 System Integration and Testing (SYS.4)

System integration follows a bottom-up strategy:

1. Component-level integration within each subsystem
2. Subsystem-level integration across interfaces
3. Full system integration on the target hardware platform

Integration test cases are derived from interface specifications and system requirements. Test results are recorded in the test management tool (TestRail) with pass/fail status and defect links.

### 3.4 System Qualification Testing (SYS.5)

System qualification testing verifies that the integrated system meets all system requirements:

- **Test Strategy:** Risk-based test selection prioritizing safety-critical and high-impact requirements.
- **Test Environment:** Hardware-in-the-loop (HiL) simulation and vehicle-level testing.
- **Acceptance Criteria:** All critical and high-priority requirements must pass. Medium-priority requirements require 95% pass rate.
- **Test Reporting:** Qualification test report includes coverage analysis, defect summary, and release recommendation.

---

## 4. Software Requirements Analysis (SWE.1)

### 4.1 Requirements Elicitation

Software requirements are derived from system requirements through allocation and decomposition. The requirements engineer conducts:

- Analysis of allocated system requirements
- Interface analysis with adjacent software components
- Identification of derived software requirements (not directly traceable to system requirements)
- Stakeholder review sessions for requirements validation

### 4.2 Requirements Documentation

Software requirements are documented in the Software Requirements Specification (SRS) with the following attributes:

| Attribute | Description |
|-----------|-------------|
| Requirement ID | Unique identifier (e.g., SWE-REQ-001) |
| Description | Clear, testable statement of the requirement |
| Rationale | Why the requirement exists |
| Priority | Critical / High / Medium / Low |
| Source | Traceability to system requirement or stakeholder need |
| Acceptance Criteria | Measurable conditions for verification |
| Status | Draft / Reviewed / Approved / Implemented / Verified |

### 4.3 Requirements Verification

- **Peer Review:** All requirements undergo peer review using a structured checklist covering completeness, consistency, testability, and traceability.
- **Traceability:** Bidirectional traceability maintained between system requirements and software requirements in DOORS.
- **Baseline Management:** Requirements baselines are established at each milestone and changes are managed through the change control process.

---

## 5. Software Architecture and Design (SWE.2 / SWE.3)

### 5.1 Architecture Design (SWE.2)

The software architecture defines the high-level structure of each software component:

- **Component Decomposition:** Software is decomposed into modules with defined interfaces, responsibilities, and dependencies.
- **Design Patterns:** Observer pattern for sensor data distribution, State Machine pattern for mode management, Strategy pattern for algorithm selection.
- **Interface Specification:** All inter-module interfaces are formally specified with data types, protocols, pre/post conditions, and error handling.
- **Resource Budgets:** Memory, CPU, and communication bandwidth budgets are allocated per component.

Architecture decisions are documented in the Software Architecture Document (SAD) with traceability to software requirements.

### 5.2 Detailed Design (SWE.3)

Detailed design specifies the internal structure of each software module:

- **Data Structures:** Defined with types, ranges, and invariants.
- **Algorithms:** Described with pseudocode or flowcharts, including complexity analysis.
- **Error Handling:** Each module defines error detection, reporting, and recovery strategies.
- **Coding Standards:** MISRA C:2012 compliance required for all safety-critical modules. Static analysis enforced in CI pipeline.

Detailed design documents are reviewed by the technical lead and a peer reviewer before implementation begins.

---

## 6. Software Construction and Unit Testing (SWE.4)

### 6.1 Coding Standards

- MISRA C:2012 for C code (safety-critical modules)
- AUTOSAR C++14 guidelines for C++ code
- All code must pass static analysis (Polyspace, PC-lint) with zero critical findings
- Code complexity: cyclomatic complexity ≤ 15 per function

### 6.2 Unit Testing

- **Framework:** Google Test (C++), Unity (C)
- **Coverage Target:** Statement coverage ≥ 90%, branch coverage ≥ 80% for safety-critical modules
- **Test Strategy:** Each function has at least one positive test, one negative test, and boundary value tests
- **Automation:** Unit tests run automatically in the CI pipeline on every commit

### 6.3 Code Review

All code changes require peer review before merge:

- Reviewer checklist covers correctness, standards compliance, error handling, and testability
- Review comments tracked in the version control system (Git/Gerrit)
- Critical findings must be resolved before merge approval

---

## 7. Software Integration and Testing (SWE.5)

### 7.1 Integration Strategy

Software integration follows an incremental approach:

1. Module-level integration within each component
2. Component-level integration across defined interfaces
3. Full software integration on the target platform

### 7.2 Integration Testing

- **Test Basis:** Integration test cases derived from interface specifications and software architecture
- **Test Environment:** Software-in-the-loop (SiL) simulation and target hardware
- **Defect Management:** Integration defects logged in Jira with severity, root cause analysis, and fix verification
- **Regression Testing:** Automated regression suite executed after each integration build

---

## 8. Software Qualification Testing (SWE.6)

### 8.1 Qualification Test Planning

- Test cases derived from software requirements with full traceability
- Risk-based prioritization of test execution
- Test environment mirrors production configuration

### 8.2 Qualification Test Execution

- All critical requirements must have passing qualification tests
- Test results recorded in TestRail with evidence artifacts (logs, screenshots, data recordings)
- Defects found during qualification are triaged and resolved before release

### 8.3 Release Criteria

| Criterion | Threshold |
|-----------|-----------|
| Critical defects | 0 open |
| High defects | ≤ 2 open (with approved waivers) |
| Requirements coverage | 100% of critical, ≥ 95% of high |
| Code coverage | ≥ 90% statement, ≥ 80% branch |

---

## 9. Support Processes

### 9.1 Quality Assurance (SUP.1)

- **QA Plan:** Defines quality objectives, metrics, audit schedule, and process compliance checks.
- **Process Audits:** Quarterly audits verify adherence to defined processes. Findings tracked to closure.
- **Quality Metrics:** Defect density, review effectiveness, test coverage, and process compliance rates reported monthly.
- **Continuous Improvement:** Lessons learned captured at each milestone and fed into process improvement backlog.

### 9.2 Configuration Management (SUP.8)

- **Version Control:** Git with Gerrit for code review. Branching strategy: GitFlow with feature, develop, release, and hotfix branches.
- **Baseline Management:** Baselines established at each milestone (requirements baseline, design baseline, code baseline, test baseline).
- **Change Control:** All changes to baselined artifacts require a change request approved by the Change Control Board (CCB).
- **Build Management:** Automated builds via Jenkins CI pipeline. Build artifacts stored in Artifactory with traceability to source commits.

### 9.3 Problem Resolution (SUP.9)

- **Defect Lifecycle:** New → Assigned → In Progress → Resolved → Verified → Closed
- **Root Cause Analysis:** Required for all critical and high-severity defects. Uses 5-Why or Ishikawa methods.
- **Escalation:** Defects not resolved within SLA are escalated to the project manager and technical lead.
- **Metrics:** Mean time to resolution (MTTR), defect aging, and reopen rate tracked and reported weekly.

### 9.4 Change Request Management (SUP.10)

- **Change Request Process:** All changes to approved baselines follow a formal change request process.
- **Impact Analysis:** Each change request includes impact analysis covering schedule, cost, quality, and technical risk.
- **CCB Review:** The Change Control Board reviews and approves/rejects change requests weekly.
- **Traceability:** Approved changes are traced to affected requirements, design elements, code, and test cases.

---

## 10. Metrics and Measurement

### 10.1 Process Metrics

| Metric | Target | Collection Frequency |
|--------|--------|---------------------|
| Requirements stability index | ≤ 10% change per sprint | Per sprint |
| Defect density | ≤ 5 defects per KLOC | Per release |
| Code review coverage | 100% of changes | Continuous |
| Test case pass rate | ≥ 95% | Per build |
| Schedule variance | ≤ ±10% | Weekly |

### 10.2 Quality Gates

| Gate | Entry Criteria | Exit Criteria |
|------|---------------|---------------|
| Requirements Review | All requirements documented | Peer review complete, traceability verified |
| Design Review | Architecture and detailed design complete | Review approved, no open critical findings |
| Code Complete | All planned features implemented | Unit tests pass, static analysis clean |
| Integration Test | All components integrated | Integration tests pass, no critical defects |
| Release | Qualification testing complete | Release criteria met, stakeholder sign-off |

---

## 11. Traceability

### 11.1 Traceability Chain

The following traceability relationships are maintained:

```
Stakeholder Needs
    ↓
System Requirements (DOORS)
    ↓
Software Requirements (DOORS)
    ↓
Software Architecture (SAD)
    ↓
Detailed Design (SDD)
    ↓
Source Code (Git)
    ↓
Test Cases (TestRail)
    ↓
Test Results (TestRail)
```

### 11.2 Traceability Coverage

- System requirements → Software requirements: 100% coverage required
- Software requirements → Design elements: 100% coverage required
- Software requirements → Test cases: 100% coverage for critical, ≥ 95% for high priority
- Bidirectional traceability verified at each milestone review

---

## 12. Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024-06-01 | J. Smith | Initial release |
| 1.1 | 2024-09-15 | A. Chen | Added metrics section, updated quality gates |
| 2.0 | 2025-01-10 | J. Smith | Major revision for ASPICE CL3 alignment |
