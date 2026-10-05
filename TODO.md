# TODO.md: ScaffoldRAG V1 Implementation Roadmap

**Tracking Standard:** Every task must satisfy its explicit **Definition of Done (DoD)** before being marked complete. Tasks must be executed in order; dependencies are non-negotiable [Certain].

---

## Phase 0: Environment Foundation & Infrastructure Setup

*Goal: Establish a reproducible local development environment with zero dependency conflicts.*

- [X] **Task 0.1: Repository Skeleton & Dependency Management**

  - Initialize Git repository with a production `.gitignore` (ignore `.env`, `__pycache__`, `qdrant_data/`, `.venv/`) [Certain].
  - Configure Python 3.11 virtual environment using `uv` or `poetry` for deterministic dependency resolution [Certain].
  - Pin baseline dependencies in `pyproject.toml`:
    - `fastapi`, `uvicorn[standard]`, `pydantic>=2.0`, `instructor`, `groq`, `qdrant-client`, `fastembed`, `sentence-transformers`, `ragas`, `pytest`, `httpx`, `ruff`.
  - *DoD:* Running `uv sync` or `poetry install` installs all packages without wheel-building errors [Certain].
- [X] **Task 0.2: Local Infrastructure Provisioning (Qdrant)**

  - Create a `docker-compose.yml` file configuring the official Qdrant image (`qdrant/qdrant:latest`) [Certain].
  - Mount persistent host storage: `./qdrant_storage:/qdrant/storage` [Certain].
  - Expose HTTP port `6333` and gRPC port `6334` [Certain].
  - *DoD:* Running `docker compose up -d` allows `curl http://localhost:6333/readyz` to return HTTP 200 `{"status": "ok"}` [Certain].
- [X] **Task 0.3: Environment Secrets & Configuration Layer**

  - Create `.env.example` with template keys: `GROQ_API_KEY`, `QDRANT_HOST=localhost`, `QDRANT_PORT=6333`, `LOG_LEVEL=INFO`.
  - Implement a strongly-typed `app/config.py` using `pydantic-settings` to parse and validate environment variables at startup [Certain].
  - *DoD:* Application refuses to boot if `GROQ_API_KEY` is missing or invalid [Certain].

---

## Phase 1: Corpus Authoring & Ingestion Pipeline (ADR-02 & ADR-04)

*Goal: Author, validate, chunk, and index the 15 reference engineering blueprints.*

- [X] **Task 1.1: Draft the 15 Core Markdown Blueprints**

  - Author 15 modular Markdown files in `data/blueprints/` strictly following the ADR-02 Verification Rubric [Certain]:
    1. `01_in_memory_dense_retrieval.md`
    2. `02_sparse_bm25_indexing.md`
    3. `03_reciprocal_rank_fusion.md`
    4. `04_cross_encoder_reranking.md`
    5. `05_ragas_evaluation_framework.md`
    6. `06_structured_outputs_instructor.md`
    7. `07_circuit_breaker_graceful_degradation.md`
    8. `08_fastapi_async_middleware_telemetry.md`
    9. `09_redis_caching_layer.md`
    10. `10_celery_asynchronous_task_queues.md`
    11. `11_docker_multistage_builds.md`
    12. `12_github_actions_ci_cd.md`
    13. `13_golden_dataset_curation.md`
    14. `14_prometheus_metrics_exporting.md`
    15. `15_production_latency_profiling.md`
  - *DoD:* Each file contains: Module Name, Difficulty Level (1-5), Prerequisites, Markdown Reference Content, and Explicit Tradeoff Profile (Latency, Memory, Complexity) [Certain].
- [X] **Task 1.2: Build Corpus Static Linter**

  - Write `scripts/lint_blueprints.py` to assert that every Markdown file satisfies the schema required by PRD Section 4.2 [Certain].
  - Check that no referenced Python package is abandoned (automated PyPI check or static whitelist) [Certain].
  - *DoD:* Linter runs in under 2 seconds and exits with return code `0` only when all 15 blueprints pass [Certain].
- [X] **Task 1.3: FastEmbed Embedding & Qdrant Collection Initializer**

  - Implement `app/services/indexer.py`.
  - Initialize a Qdrant collection named `engineering_blueprints` configured with:
    - Dense vectors: Size 384, Distance: Cosine (`BAAI/bge-small-en-v1.5` via FastEmbed) [Certain].
    - Sparse vectors: Named `bm25` (using FastEmbed's native sparse document generator) [Certain].
  - Chunk Markdown documents cleanly by Markdown second-level headers (`## `) to preserve conceptual boundaries [Certain].
  - Upsert chunks into Qdrant alongside metadata payloads (module name, difficulty, tradeoffs).
  - *DoD:* Running `python -m scripts.ingest_corpus` indexes all chunks; Qdrant dashboard (`http://localhost:6333/dashboard`) confirms vector count > 0 with verified payloads [Certain].

---

## Phase 2: Hybrid Retrieval & Ranking Engine

*Goal: Implement and verify the sub-second search pipeline with out-of-distribution protection.*

- [X] **Task 2.1: Out-of-Distribution (OOD) Hard Gate**
  - Implement `app/services/search/ood_gate.py`.
  - Calibrated cosine threshold to 0.58 based on empirical probe distribution.
  - Intercepts non-computing inputs with `OutOfDistributionError`.
- [X] **Task 2.2: Hybrid Search via Reciprocal Rank Fusion (RRF)**
  - Implement `app/services/search/hybrid_search.py`.
  - Client-side RRF ($k=60$) over parallel gRPC calls for dense (`bge-small`) and sparse (`bm25`) vectors.
  - Returns top 15 candidate chunks.
- [X] **Task 2.3: Cross-Encoder Reranker Integration**
  - Implement `app/services/search/reranker.py` via `fastembed==0.4.2` ONNX runtime.
  - Truncates sequence content to 350 characters and pre-warms batch-15 memory arenas.
  - Re-ranks 15 candidates to top 4 chunks in $\le 450\text{ms}$ on CPU.

---

## Phase 3: Structured Generation & Fallback Layer

*Goal: Synthesize retrieved blueprints into a strongly typed 5-stage roadmap via Groq.*

- [X] **Task 3.1: Pydantic Schema Definitions & Contract Tests**

  - Define `app/schemas/roadmap.py` matching `docs/SPEC_V1.md` Section 3.2:
    - `RoadmapRequest` (`target_role`, `domain_interest`, `current_skills`).
    - `Milestone` (`stage`, `name`, `tools_introduced`, `why_added`, `tradeoff`, `verification_metric`).
    - `ProjectRoadmap` (`roadmap_id`, `project_title`, `domain`, `milestones`).
  - Implement `@field_validator("tradeoff")` on `Milestone` asserting explicit engineering drawbacks and rejecting terms: `["none", "makes it better", "faster", "easy"]` [Certain].
  - Enforce list invariant on `ProjectRoadmap`: `milestones` must contain exactly 5 stages [Certain].
  - Create `tests/test_specification_contract.py` asserting schema rejection on non-compliant payloads.
  - *DoD:* Running `pytest tests/test_specification_contract.py` passes with 100% compliance against the specification contract [Certain].
- [X] **Task 3.2: Instructor + Groq Structured Inference Client**

  - Implement `app/services/generator.py` containing `RoadmapGenerator`.
  - Initialize `Instructor` client patching `groq.Groq` targeting `llama-3.1-8b-instant` using `mode=instructor.Mode.TOOLS` or `JSON` depending on SDK compatibility [Certain].
  - Construct system prompt grounding output strictly in the retrieved context:
    > "You are a Principal Solutions Architect. Using ONLY the architecture patterns provided in the context below, create an incremental 5-stage scaffolding plan for the user's project idea. You must output data that strictly validates against the provided JSON schema."
    >
  - Configure `max_retries=2` to ensure automated reflection on Pydantic validation errors [Certain].
  - Implement unit tests with deterministic transport mocking and an opt-in live integration test (`@pytest.mark.integration`).
  - *DoD:* Generator takes top 4 retrieved chunks and outputs a validated, instantiated `ProjectRoadmap` object [Certain].
- [X] **Task 3.3: Circuit Breaker & Fallback System**

  - Implement `app/core/circuit_breaker.py` containing `CircuitBreaker` and `FallbackProvider` matching `docs/SPEC_V1.md` Section 5.2:
    - Finite State Machine: `CLOSED`, `OPEN`, `HALF-OPEN` [Certain].
    - Trip threshold: 3 consecutive HTTP 429/500/timeout exceptions from upstream [Certain].
    - Recovery timeout: 45.0 seconds before transitioning from `OPEN` to `HALF-OPEN` [Certain].
  - Author and validate 3 production fallback roadmaps in `data/fallbacks/`:
    - `mle_roadmap.json` (Machine Learning Engineer)
    - `de_roadmap.json` (Data Engineer)
    - `backend_ai_roadmap.json` (Backend AI Engineer)
  - Assert that all fallback JSON files strictly parse into `ProjectRoadmap` instances at import time [Certain].
  - Implement unit tests verifying state transitions and asserting fallback resolution within $\le 50\text{ms}$ when open [Certain].
  - *DoD:* Test harness simulates 3 consecutive upstream HTTP failures; circuit transitions to `OPEN` and serves static role-matched fallback JSON from disk in $< 50\text{ms}$ without network egress [Certain].

---

## Phase 4: API Assembly, Middleware, & Interface

*Goal: Expose endpoints via FastAPI and provide an interactive testing client.*

- [X] **Task 4.1: FastAPI Route Handlers**

  - Implemented `app/api/v1/endpoints.py` with singleton dependency injection.
  - Added `POST /api/v1/roadmaps`, `GET /api/v1/roadmaps/{id}/export?format=markdown`, and `GET /health`.
  - Added `app/services/storage.py` (SQLite WAL repository) and `app/services/exporter.py` (Markdown checklist serializer).
  - Added `app/api/v1/exceptions.py` mapping `OutOfDistributionError` to HTTP 422.
  - Verified via `tests/test_api.py` with 8 passing tests.
- [X] **Task 4.2: Telemetry & Latency Profiling Middleware**

  - Implemented `app/middleware/timing.py` measuring component latencies: `t_ood_ms`, `t_retrieval_ms`, `t_rerank_ms`, `t_generation_ms`, and `t_total_ms`.
  - Injected `X-Process-Time-Ms` response header.
  - Added structured JSON logging to standard output.
  - Verified via `tests/test_timing_middleware.py` with 2 passing tests.
- [X] **Task 4.3: Minimal Streamlit UI**

  - Implemented `frontend/app.py` with parameter controls, 5-stage accordion cards, tradeoff views, and direct Markdown downloads.
  - Enforced `st.session_state` guards to prevent accidental re-generation loops.
  - Parameterized backend networking using `BACKEND_API_URL`.
  - Verified full browser-to-backend communication.

---

## Phase 5: Automated Testing, Quality Gates, & CI/CD

*Goal: Prove system reliability, benchmark precision, and containerize for deployment.*

- [X] **Task 5.1: Golden Dataset Curation & Retrieval Benchmark**

  - [X] Created `tests/golden_dataset.json` with 30 representative student queries mapped to verified blueprint chunk UUIDs.
  - [X] Implemented `tests/benchmarks/test_retrieval_precision.py` evaluating Context Precision@4.
  - [X] *DoD Met:* Test suite programmatically asserts that mean `context_precision` $\ge 0.85$ (Empirically verified: **0.8593**).
- [X] **Task 5.2: Unit & Integration Test Suite**

  - [X] Implemented unit tests for RRF scoring algorithm logic (`tests/test_rrf.py`).
  - [X] Implemented unit tests for Pydantic schema rejection rules (`tests/test_schemas.py`).
  - [X] Implemented unit tests for Indexer AST parsing and Qdrant error handling (`tests/test_indexer.py`).
  - [X] Implemented lifespan pre-warming tests (`tests/test_main.py`).
  - [X] Verified circuit breaker state transitions (`tests/test_circuit_breaker.py`).
  - [X] *DoD Met:* Running `pytest --cov=app tests/` reports **93.20%** code coverage with **0 test failures** across 59 tests.
- [X] **Task 5.3: Production Multi-Stage Containerization**

  - [X] Wrote multi-stage `Dockerfile` with non-root user (`appuser:10001`), symbol stripping, and zero-dependency Python `urllib` healthcheck.
  - [X] Updated `docker-compose.yml` to orchestrate Qdrant 1.10.1 and FastAPI backend on shared `scaffold_network` bridge [5].
  - [X] Purged `sentence-transformers` and isolated `streamlit` to keep virtual environment at 242 MB.
  - [X] *DoD Met:* Container builds in $1\text{m } 50\text{s}$ ($<3\text{ minutes}$); total runtime image size is **525 MB** (calibrated via ADR-11 to $\le 550\text{ MB}$).
- [X] **Task 5.4: Continuous Integration Pipeline (GitHub Actions)**

  - [X] Created `.github/workflows/ci.yml` running Ruff check, Ruff format check, Mypy, ephemeral Qdrant ingestion, coverage gate ($\ge 85\%$), and precision benchmark ($\ge 0.85$).
  - [X] *DoD Met:* All 5 automated quality gates pass remotely on GitHub Actions with a green checkmark.

---

## Post-V1 Roadmap (Phase 6: Production Staging & User Evaluation)

- [ ] **Task 6.1: Cloud Staging Deployment**
  - Deploy `docker-compose.yml` onto a cloud Linux VM (e.g., AWS EC2 or Hetzner).
  - Configure reverse proxy (Nginx or Caddy) with automated TLS termination.
- [ ] **Task 6.2: Usability Testing (Time-to-Value Validation)**
  - Conduct developer usability trials with ten 3rd- and 4th-year computing students.
  - Measure percentage of students executing Milestone 1 within 60 minutes (PRD Metric 1.3: Target $\ge 80\%$).
- [ ] **Task 6.3: Corpus Expansion**
  - Author 15 additional modular engineering blueprints (advancing corpus from 15 to 30 modules, expanding beginner difficulty 1 representation

*Goal: Prove system reliability, benchmark precision, and containerize for deployment.*
