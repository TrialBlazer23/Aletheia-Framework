# Aletheia Framework Glossary

This document maps the specialized terminology of the Aletheia Framework to standard industry terms to facilitate understanding for enterprise architects, developers, and stakeholders.

## Core Concepts

| Aletheia Term | Industry Equivalent | Description |
| :--- | :--- | :--- |
| **Aletheia Framework** | **Neuro-Symbolic Multi-Agent System** | The overarching architecture for transparent, auditable AI combining neural networks with symbolic reasoning and structured orchestration. |
| **Glass Box AI** | **Transparent/Explainable AI** | An architectural approach where all decisions are traceable, logged, and auditable—in contrast to "Black Box" AI. |
| **The Family** | **Agent Federation / Microservices** | The collection of specialized agents that collectively form the AI system. |

## Agent Roles

| Aletheia Term | Industry Equivalent | Description |
| :--- | :--- | :--- |
| **Nexus-Mind** | **Orchestrator / Control Plane** | The central agent responsible for task decomposition, resource allocation, and decision-making. All orchestration decisions are logged. |
| **The Philosopher** | **Constitutional AI / Safety Kernel** | Dedicated safety validation agent with veto power. Enforces Prime Directives and logs all ethical checks. |
| **The Archivist** | **Knowledge Graph / Memory System** | Agent responsible for data acquisition, validation, and knowledge management with complete source attribution. |
| **The Diagnostician** | **Observability & Self-Healing** | System monitor responsible for anomaly detection, telemetry collection, and triggering supervised improvement cycles. |
| **The Narrator** | **Presentation Layer / User Interface** | Agent that synthesizes outputs for human consumption. All outputs must pass Philosopher validation. |
| **The Visionary** | **Simulation / Prediction Engine** | Agent that handles predictive modeling and scenario simulation (optional component). |

## Communication & Workflow

| Aletheia Term | Industry Equivalent | Description |
| :--- | :--- | :--- |
| **Synapse Protocol** | **Inter-Agent Communication Protocol** | The standardized message format (JSON schema) used for communication between agents. All messages logged for audit. |
| **Synapse Interface Layer (SIL)** | **Agent API / Sidecar Proxy** | The interface that standardizes how different models connect to the central message bus. |
| **Domino Cascade** | **Event-Driven Workflow / Event Bus** | A chain of reactive, logged events where the output of one agent triggers the input of another. Creates complete audit trail. |
| **Cascade Pathway** | **Workflow Definition / DAG** | The predefined route or Directed Acyclic Graph that a specific task follows through the system. |
| **EVENT Message** | **Event Notification** | Broadcast message announcing completed work with results. |
| **TRIGGER Message** | **Command / Invocation** | Direct command to an agent to perform a specific action. |
| **STATE_CHANGE Message** | **State Notification** | Notification of internal agent state updates. |

## Transparency & Auditability

| Aletheia Term | Industry Equivalent | Description |
| :--- | :--- | :--- |
| **Event Log / Audit Trail** | **Immutable Log / Audit Log** | Complete record of all agent decisions, actions, and validations. Cannot be altered retroactively. |
| **Source Attribution** | **Data Provenance / Lineage** | Tracking of original sources for all facts and data used in decision-making. |
| **Confidence Scoring** | **Uncertainty Quantification** | Explicit scoring of confidence in outputs, logged with reasoning. |
| **Validation Record** | **Approval Log / Attestation** | Log of all safety checks performed by The Philosopher with reasoning. |
| **Decision Lineage** | **Trace / Causality Chain** | Complete path from user input to system output, showing all intermediate steps and reasoning. |


## Learning & Safety

| Aletheia Term | Industry Equivalent | Description |
| :--- | :--- | :--- |
| **Resonance Cycle** | **Supervised Learning Loop** | The supervised process of evaluating system performance and updating policies with mandatory human approval. |
| **Prime Directives** | **System Constitution / Guardrails** | The core, hard-coded rules that govern the system's behavior. Enforced by The Philosopher. Cannot be bypassed. |
| **Constitutional AI** | **Value Alignment / Safety Enforcement** | AI design where ethical principles are architecturally enforced, not just trained. |
| **Human Gavel** | **Human-in-the-Loop (HITL)** | The requirement for human approval before significant behavioral changes are executed. |
| **Policy Update** | **Configuration Change / Rule Modification** | Changes to agent behavior that must be validated and human-approved before integration. |
| **Verification Simulation** | **Safety Testing / Validation** | The Philosopher's process of testing proposed changes against Prime Directives before human review. |

## Infrastructure & Deployment

| Aletheia Term | Industry Equivalent | Description |
| :--- | :--- | :--- |
| **Digital Sandbox** | **Isolated Execution Environment** | A containerized environment where agents run, isolated from external systems for safety. |
| **Message Bus** | **Event Bus / Message Queue** | Central communication infrastructure (e.g., RabbitMQ, Kafka) that routes messages between agents. |
| **Knowledge Graph** | **Graph Database / Semantic Network** | Structured representation of knowledge with relationships, used by The Archivist. |
| **Vector Database** | **Embedding Store / Similarity Search** | Storage for semantic embeddings used in knowledge retrieval. |
| **Telemetry** | **Metrics / Observability Data** | Performance and health data collected by The Diagnostician. |
| **Distributed Tracing** | **Request Tracing / Observability** | Technology for tracking requests across multiple agents (e.g., OpenTelemetry). |

## High-Stakes Use Cases

| Aletheia Term | Industry Equivalent | Description |
| :--- | :--- | :--- |
| **Hallucination Prevention** | **Factual Grounding / Source Verification** | Using deterministic parsing and source attribution to prevent fabricated information. |
| **Regulatory Compliance** | **Audit Readiness / Governance** | Ability to provide complete decision trails for regulatory review. |
| **Bias Detection** | **Fairness Validation / Ethical Check** | The Philosopher's validation against fairness principles. |
| **Rollback Capability** | **Version Control / Recovery** | Ability to revert policy changes if issues are detected. |
| **Escalation** | **Human Review / Exception Handling** | Process where ambiguous cases are sent to human administrators for decision. |

---

## Quick Reference: Black Box vs Glass Box

| Feature | Black Box AI | Glass Box AI (Aletheia) |
| :--- | :--- | :--- |
| **Decision Transparency** | Opaque | Complete audit trail |
| **Safety Enforcement** | Post-hoc alignment | Architectural (The Philosopher) |
| **Source Attribution** | None or limited | Complete provenance |
| **Auditability** | Difficult/impossible | Built-in logging |
| **Human Control** | Pre-deployment only | Continuous (Human Gavel) |
| **Explainability** | Attempted retroactively | Inherent in architecture |
| **Regulatory Compliance** | Challenging | Designed for it |
