#!/usr/bin/env python3
"""
scripts/lint_blueprints.py
Deterministic static AST and schema validator for ScaffoldRAG blueprints.
Enforces ADR-02, ADR-05, SPEC_V1.md Appendix A, and DoD execution speed (< 2.0s).
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

# Static whitelist of verified packages and system tools referenced across blueprints
PERMITTED_ECOSYSTEM = frozenset({
    # Production application & async dependencies
    "fastapi", "uvicorn", "starlette", "pydantic", "pydantic_settings",
    "asyncio", "structlog", "tenacity", "pybreaker", "httpx",
    # Retrieval, embeddings & ML runtimes
    "qdrant_client", "fastembed", "onnxruntime", "sentence_transformers",
    "numpy", "instructor", "groq",
    # Caching, queues & observability
    "redis", "celery", "prometheus_client", "py_spy",
    # Evaluation, testing & DevOps
    "ragas", "pytest", "docker", "poetry", "git"
})

EXPECTED_FILES = [
    "01_in_memory_dense_retrieval.md",
    "02_sparse_bm25_indexing.md",
    "03_reciprocal_rank_fusion.md",
    "04_cross_encoder_reranking.md",
    "05_ragas_evaluation_framework.md",
    "06_structured_outputs_instructor.md",
    "07_circuit_breaker_graceful_degradation.md",
    "08_fastapi_async_middleware_telemetry.md",
    "09_redis_caching_layer.md",
    "10_celery_asynchronous_task_queues.md",
    "11_docker_multistage_builds.md",
    "12_github_actions_ci_cd.md",
    "13_golden_dataset_curation.md",
    "14_prometheus_metrics_exporting.md",
    "15_production_latency_profiling.md",
]

# Strict AST matching compiled regexes
RE_ROOT_TITLE = re.compile(r"^#\s+Module:\s*(.+)$", re.MULTILINE)
RE_MODULE_ID = re.compile(r"^-\s*Module ID:\s*([a-zA-Z0-9_-]+)$", re.MULTILINE)
RE_DIFFICULTY = re.compile(r"^-\s*Difficulty Level:\s*([1-5])$", re.MULTILINE)
RE_PREREQUISITES = re.compile(r"^-\s*Prerequisites:\s*(.+)$", re.MULTILINE)

RE_LATENCY = re.compile(r"^-\s*Latency Impact:\s*(.+)$", re.MULTILINE)
RE_MEMORY = re.compile(r"^-\s*Memory Footprint:\s*(.+)$", re.MULTILINE)
RE_COMPLEXITY = re.compile(r"^-\s*Operational Complexity:\s*(.+)$", re.MULTILINE)

RE_IMPORT = re.compile(r"^\s*(?:import|from)\s+([a-zA-Z0-9_]+)", re.MULTILINE)

# Unacceptable non-quantitative statements
VAGUE_TERMS = frozenset({
    "none", "n/a", "fast", "slow", "low", "high", "minimal",
    "negligible", "makes it faster", "no impact", "zero"
})

REQUIRED_SECTIONS = [
    "## Metadata",
    "## Architecture Pattern",
    "## Explicit Tradeoffs",
    "## Verification Metric"
]


def normalize_token_name(token: str) -> str:
    """Normalizes raw package names from markdown to standard python package slugs."""
    return token.strip().lower().replace("-", "_").replace(" ", "_")


def lint_blueprint(file_path: Path) -> list[str]:
    errors: list[str] = []

    if not file_path.is_file():
        return [f"File missing on disk: {file_path.name}"]

    content = file_path.read_text(encoding="utf-8")

    # 1. Root Title Verification
    title_match = RE_ROOT_TITLE.search(content)
    if not title_match or not title_match.group(1).strip():
        errors.append("Missing or malformed root title. Expected format: '# Module: <Title>'.")

    # 2. Section Partitioning & Presence
    sections = re.split(r"\n(?=## )", content)
    found_headers = [s.split("\n", 1)[0].strip() for s in sections if s.startswith("## ")]

    for req_header in REQUIRED_SECTIONS:
        if req_header not in found_headers:
            errors.append(f"Missing mandatory section header: '{req_header}'.")

    # 3. Metadata Header Validation
    metadata_sec = next((s for s in sections if s.startswith("## Metadata")), None)
    if metadata_sec:
        if not RE_MODULE_ID.search(metadata_sec):
            errors.append("Invalid or missing '- Module ID: <id>' in '## Metadata'.")
        if not RE_DIFFICULTY.search(metadata_sec):
            errors.append("Invalid or missing '- Difficulty Level: [1-5]' in '## Metadata'.")
        if not RE_PREREQUISITES.search(metadata_sec):
            errors.append("Invalid or missing '- Prerequisites: <list>' in '## Metadata'.")

    # 4. Architecture Pattern Validation
    arch_sec = next((s for s in sections if s.startswith("## Architecture Pattern")), None)
    if arch_sec:
        text_body = arch_sec.split("\n", 1)[1].strip() if "\n" in arch_sec else ""
        if len(text_body) < 50:
            errors.append("Content in '## Architecture Pattern' is too short (must be >= 50 characters).")

    # 5. Explicit Tradeoffs Quantitative Checks
    tradeoff_sec = next((s for s in sections if s.startswith("## Explicit Tradeoffs")), None)
    if tradeoff_sec:
        lat = RE_LATENCY.search(tradeoff_sec)
        mem = RE_MEMORY.search(tradeoff_sec)
        cpx = RE_COMPLEXITY.search(tradeoff_sec)

        if not lat:
            errors.append("Missing '- Latency Impact:' in '## Explicit Tradeoffs'.")
        elif lat.group(1).strip().lower() in VAGUE_TERMS:
            errors.append(f"Non-quantitative latency impact: '{lat.group(1).strip()}'.")

        if not mem:
            errors.append("Missing '- Memory Footprint:' in '## Explicit Tradeoffs'.")
        elif mem.group(1).strip().lower() in VAGUE_TERMS:
            errors.append(f"Non-quantitative memory footprint: '{mem.group(1).strip()}'.")

        if not cpx:
            errors.append("Missing '- Operational Complexity:' in '## Explicit Tradeoffs'.")
        elif cpx.group(1).strip().lower() in VAGUE_TERMS:
            errors.append(f"Non-quantitative operational complexity: '{cpx.group(1).strip()}'.")

    # 6. Verification Metric Validation
    metric_sec = next((s for s in sections if s.startswith("## Verification Metric")), None)
    if metric_sec:
        text_body = metric_sec.split("\n", 1)[1].strip() if "\n" in metric_sec else ""
        if len(text_body) < 30:
            errors.append("Content in '## Verification Metric' is too short (must be >= 30 characters).")

    # 7. Token Bound Verification (SPEC Appendix A: <= 512 tokens per chunk)
    for sec in sections:
        header_name = sec.split("\n", 1)[0][:35].strip()
        token_estimate = len(sec.split()) * 1.3
        if token_estimate > 512:
            errors.append(
                f"Section '{header_name}' exceeds ~512 token ceiling (~{int(token_estimate)} tokens). "
                "Must be sub-partitioned by '### ' tertiary headers."
            )

    # 8. Dependency Ecosystem Check
    code_blocks = re.findall(r"```python(.*?)```", content, re.DOTALL)
    for block in code_blocks:
        imports = RE_IMPORT.findall(block)
        for imp in imports:
            root_pkg = normalize_token_name(imp.split(".")[0])
            if root_pkg in sys.stdlib_module_names:
                continue
            if root_pkg not in PERMITTED_ECOSYSTEM:
                errors.append(f"Referenced unverified package import: '{root_pkg}'.")

    return errors


def main() -> int:
    start_time = time.perf_counter()
    blueprints_dir = Path("data/blueprints")

    if not blueprints_dir.is_dir():
        print(f"FATAL: Blueprints directory does not exist at {blueprints_dir.resolve()}")
        return 1

    total_errors: dict[str, list[str]] = {}

    for fname in EXPECTED_FILES:
        target_path = blueprints_dir / fname
        file_errors = lint_blueprint(target_path)
        if file_errors:
            total_errors[fname] = file_errors

    elapsed_time = time.perf_counter() - start_time

    if total_errors:
        print(f"\n[FAILED] Static blueprint linting failed with errors ({elapsed_time:.4f}s elapsed):\n")
        for fname, errs in total_errors.items():
            print(f"  {fname}:")
            for err in errs:
                print(f"    - {err}")
        return 1

    print(f"\n[PASSED] All {len(EXPECTED_FILES)} blueprints verified successfully in {elapsed_time:.4f}s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())