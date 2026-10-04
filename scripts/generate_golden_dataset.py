"""scripts/generate_golden_dataset.py
Generates tests/golden_dataset.json directly from the on-disk blueprint ASTs.
Guarantees 100% string and UUIDv5 alignment with Qdrant points.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.indexer import IndexerService

# Map of blueprint filenames to queries designed to retrieve them
QUERY_MAPPINGS = [
    {
        "file": "01_in_memory_dense_retrieval.md",
        "queries": [
            (
                "MLE-001",
                "How do I build a dense vector search baseline with FastEmbed and Qdrant?",
                "Machine Learning Engineer",
            ),
            (
                "MLE-008",
                "Semantic dense search using BGE Small embeddings and cosine similarity.",
                "Machine Learning Engineer",
            ),
        ],
    },
    {
        "file": "02_sparse_bm25_indexing.md",
        "queries": [
            (
                "MLE-002",
                "Implement lexical keyword matching using BM25 sparse vectors in Qdrant.",
                "Machine Learning Engineer",
            ),
            (
                "MLE-009",
                "Exact keyword matching failure modes in dense vector stores solved by BM25.",
                "Machine Learning Engineer",
            ),
        ],
    },
    {
        "file": "03_reciprocal_rank_fusion.md",
        "queries": [
            (
                "MLE-003",
                "How to merge dense vector hits and BM25 sparse rankings using Reciprocal Rank Fusion k=60?",
                "Machine Learning Engineer",
            ),
            (
                "MLE-010",
                "Combining vector similarity scores with inverted index ranks without normal distribution assumptions.",
                "Machine Learning Engineer",
            ),
        ],
    },
    {
        "file": "04_cross_encoder_reranking.md",
        "queries": [
            (
                "MLE-004",
                "Cross-Encoder re-ranking with ms-marco-MiniLM-L-6-v2 on CPU under latency SLA.",
                "Machine Learning Engineer",
            ),
            (
                "MLE-011",
                "Cross-attention transformer scoring over top 15 retrieved candidate passages.",
                "Machine Learning Engineer",
            ),
        ],
    },
    {
        "file": "05_ragas_evaluation_framework.md",
        "queries": [
            (
                "MLE-005",
                "Evaluating retrieval precision and context recall with RAGAS framework.",
                "Machine Learning Engineer",
            ),
            (
                "MLE-012",
                "Continuous integration test asserting retrieval context precision at K equals 4.",
                "Machine Learning Engineer",
            ),
        ],
    },
    {
        "file": "06_structured_outputs_instructor.md",
        "queries": [
            (
                "MLE-006",
                "Constrained JSON decoding with Instructor and Groq LPU inference.",
                "Backend AI Engineer",
            ),
            (
                "BAI-001",
                "Enforcing sequential milestone stages in Pydantic V2 models via Instructor.",
                "Backend AI Engineer",
            ),
        ],
    },
    {
        "file": "07_circuit_breaker_graceful_degradation.md",
        "queries": [
            (
                "MLE-007",
                "Circuit breaker pattern with CLOSED OPEN HALF-OPEN state machine for LLM API resilience.",
                "Backend AI Engineer",
            ),
            (
                "BAI-002",
                "Handling upstream LLM rate limits with fallback disk blueprints and fast failure.",
                "Backend AI Engineer",
            ),
        ],
    },
    {
        "file": "08_fastapi_async_middleware_telemetry.md",
        "queries": [
            (
                "DE-001",
                "FastAPI middleware injecting execution latency headers and structured JSON logs.",
                "Data Engineer",
            ),
            (
                "BAI-003",
                "Sub-millisecond latency profiling middleware for ASGI request pipelines.",
                "Backend AI Engineer",
            ),
        ],
    },
    {
        "file": "09_redis_caching_layer.md",
        "queries": [
            (
                "DE-002",
                "In-memory caching layer with Redis to bypass vector similarity lookups.",
                "Data Engineer",
            ),
            (
                "BAI-004",
                "Key-value cache invalidation strategies for vector similarity search results.",
                "Backend AI Engineer",
            ),
        ],
    },
    {
        "file": "10_celery_asynchronous_task_queues.md",
        "queries": [
            (
                "DE-003",
                "Asynchronous background ingestion workers with Celery and RabbitMQ broker.",
                "Data Engineer",
            ),
            (
                "DE-009",
                "Decoupling document embedding generation from HTTP request handlers using worker pools.",
                "Data Engineer",
            ),
        ],
    },
    {
        "file": "11_docker_multistage_builds.md",
        "queries": [
            (
                "DE-004",
                "Docker multi-stage build optimization to strip PyTorch bloat and keep image under 400MB.",
                "Data Engineer",
            ),
            (
                "DE-010",
                "Reducing Docker container size by omitting PyTorch CUDA runtimes in favor of ONNX.",
                "Data Engineer",
            ),
        ],
    },
    {
        "file": "12_github_actions_ci_cd.md",
        "queries": [
            (
                "DE-005",
                "Automated GitHub Actions CI pipeline running ruff, mypy, and ephemeral Qdrant tests.",
                "Data Engineer",
            ),
            (
                "DE-011",
                "GitHub Actions workflow setup with ephemeral service containers for integration tests.",
                "Data Engineer",
            ),
        ],
    },
    {
        "file": "13_golden_dataset_curation.md",
        "queries": [
            (
                "DE-006",
                "Curating high-signal golden benchmark datasets to prevent RAG evaluation drift.",
                "Data Engineer",
            ),
            (
                "DE-012",
                "Human-in-the-loop audit rubric for reference engineering blueprints.",
                "Data Engineer",
            ),
        ],
    },
    {
        "file": "14_prometheus_metrics_exporting.md",
        "queries": [
            (
                "DE-007",
                "Exporting Prometheus metrics for HTTP request latencies and Qdrant retrieval percentiles.",
                "Backend AI Engineer",
            ),
            (
                "BAI-005",
                "Tracking P95 query execution time and reranker latency with Prometheus counters.",
                "Backend AI Engineer",
            ),
        ],
    },
    {
        "file": "15_production_latency_profiling.md",
        "queries": [
            (
                "DE-008",
                "Profiling CPU thermal throttling and ONNX Runtime thread allocation latency in production.",
                "Backend AI Engineer",
            ),
            (
                "BAI-006",
                "Preventing thermal CPU throttling during batched cross-attention reranking.",
                "Backend AI Engineer",
            ),
        ],
    },
]


def generate_dataset() -> None:
    blueprints_dir = Path("data/blueprints")
    if not blueprints_dir.is_dir():
        raise FileNotFoundError(f"Missing blueprints directory: {blueprints_dir}")

    # Instantiate indexer with mocked models to avoid loading ONNX weights just to parse markdown
    with (
        patch("app.services.indexer.TextEmbedding"),
        patch("app.services.indexer.SparseTextEmbedding"),
    ):
        indexer = IndexerService(client=MagicMock(), collection_name="engineering_blueprints")

        golden_dataset: list[dict] = []

        for mapping in QUERY_MAPPINGS:
            file_name = mapping["file"]
            file_path = blueprints_dir / file_name

            if not file_path.is_file():
                raise FileNotFoundError(f"Blueprint file missing: {file_path}")

            # Parse markdown directly to get exact module_name and chunk_ids
            chunks = indexer.parse_markdown(file_path)
            chunk_ids = [c.chunk_id for c in chunks]
            module_name = chunks[0].module_name if chunks else ""

            for q_id, q_text, role in mapping["queries"]:
                golden_dataset.append(
                    {
                        "query_id": q_id,
                        "query": q_text,
                        "target_role": role,
                        "expected_blueprint_file": file_name,
                        "expected_module_name": module_name,
                        "expected_chunk_ids": chunk_ids,
                    }
                )

        output_path = Path("tests/golden_dataset.json")
        output_path.write_text(json.dumps(golden_dataset, indent=2), encoding="utf-8")
        print(f"Successfully generated {len(golden_dataset)} queries in {output_path}")


if __name__ == "__main__":
    generate_dataset()
