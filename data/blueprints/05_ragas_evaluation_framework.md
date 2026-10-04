
# Module: Automated Ragas Evaluation Pipeline

## Metadata

- Module ID: blueprint_05_ragas_evaluation
- Difficulty Level: 3
- Prerequisites: blueprint_04_cross_encoder_reranking, Ragas, Pytest

## Architecture Pattern

Construct an offline automated quality assurance test suite using the Ragas framework. Curate an immutable Golden Dataset of 30 representative user queries paired with verified ground-truth chunk IDs and reference answers. Execute the retrieval and generation pipeline across the dataset within an isolated test harness. Compute statistical metrics: Context Precision (rank-weighted relevance of retrieved chunks), Context Recall (fraction of ground-truth facts retrieved), and Faithfulness (absence of hallucinated claims in the final answer). Integrate the harness into CI/CD to block merges if quality degrades.

## Explicit Tradeoffs

- Latency Impact: Zero impact on production runtime (runs strictly offline or in CI/CD). Evaluation runs require 30 to 60 seconds across the 30-query benchmark.
- Memory Footprint: Negligible disk footprint; requires temporary test runner memory to hold batch evaluation results and metric matrices.
- Operational Complexity: Requires managing a separate LLM-as-a-Judge API budget (e.g., using GPT-4o or Claude 3.5 Sonnet to score answers); ground-truth datasets require manual maintenance when documentation changes.

## Verification Metric

CI pipeline automatically fails with exit code 1 if mean Context Precision drops below 0.85 or Faithfulness drops below 0.90 across the 30-query evaluation set.
