# Module: Structured JSON Extraction with Instructor and Pydantic

## Metadata
- Module ID: blueprint_06_structured_outputs
- Difficulty Level: 2
- Prerequisites: blueprint_01_dense_baseline, Instructor, Pydantic V2, Groq Client

## Architecture Pattern
Wrap the Groq API generation client with the Instructor library to enforce deterministic JSON outputs validated by Pydantic V2 models. Ingress student inputs and retrieved blueprint chunks are processed into a constrained schema. Instructor patches the client to pass the target Pydantic schema as a tool definition or strict response format. If the model outputs malformed JSON or violates field constraints, Instructor captures the validation exception, appends the Pydantic error trace to the message history, and triggers an automated re-ask cycle up to a strict retry limit.

## Explicit Tradeoffs
- Latency Impact: Adds +200ms to +500ms when validation passes on the first attempt; failed schemas trigger re-generation round trips adding +300ms to +600ms per corrective retry.
- Memory Footprint: Minimal resident memory overhead (<5 MB) to host Pydantic model schemas and validation logic within the worker process.
- Operational Complexity: Overly restrictive validation constraints or complex nested models can trigger recursive retry loops, exhausting token budgets and breaching timeout ceilings if the LLM cannot satisfy all rules.

## Verification Metric
Achieves 0% schema validation errors across 50 consecutive test queries; malformed initial responses recover valid Pydantic models within a maximum of 2 retry attempts.
