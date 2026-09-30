# Module: Synthetic and Empirical Golden Dataset Curation

## Metadata
- Module ID: blueprint_13_golden_dataset_curation
- Difficulty Level: 3
- Prerequisites: blueprint_05_ragas_evaluation, Pydantic V2, JSON Schema

## Architecture Pattern
Establish a versioned engineering methodology to curate and maintain an evaluation Golden Dataset containing 30 representative student technical profiles and queries. Each dataset record pairs an input query with prerequisite student skills, ground-truth retrieved blueprint IDs, expected architectural stages, and reference outputs. Persist the dataset as an immutable JSON document governed by a strict Pydantic V2 schema. Implement automated dataset validation scripts to ensure that all referenced blueprint IDs exist on disk and correspond to actual indexed chunks.

## Explicit Tradeoffs
- Latency Impact: Zero impact on production runtime; executed during offline evaluation suites or automated CI benchmarking runs.
- Memory Footprint: Minimal disk footprint (<100 KB) to store the 30-query JSON document and its corresponding structural validation model.
- Operational Complexity: Requires manual domain maintenance whenever blueprint architectures or system capabilities are updated; prevents evaluation data drift across project versions.

## Verification Metric
100% of dataset records validate against the Pydantic schema; 100% of referenced blueprint IDs resolve deterministically to active markdown files in `data/blueprints/`.
