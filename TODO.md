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

- [ ] **Task 2.1: Out-of-Distribution (OOD) Hard Gate**

  - Implement `app/services/search/ood_gate.py`.
  - Compute cosine similarity between the incoming user query vector and the nearest vector in Qdrant [Certain].
  - *DoD:* Unit test confirms that technical queries (e.g., "Build an async RAG API") score > 0.45, while non-computing queries (e.g., "Best sourdough bread recipe") score < 0.40 and raise an `HTTPException(status_code=422)` [Certain].
- [ ] **Task 2.2: Hybrid Search via Reciprocal Rank Fusion (RRF)**

  - Implement `app/services/search/hybrid_search.py`.
  - Execute simultaneous dense semantic search and sparse BM25 search in Qdrant [Certain].
  - Combine results using Reciprocal Rank Fusion with constant $k=60$ [Certain].
  - Return top 15 candidate document chunks.
  - *DoD:* Benchmark script confirms hybrid search retrieves relevant chunks when given queries containing exact library names as well as conceptual descriptions [Certain].
- [ ] **Task 2.3: Cross-Encoder Reranker Integration**

  - Implement `app/services/search/reranker.py`.
  - Load `cross-encoder/ms-marco-MiniLM-L-6-v2` locally using `sentence-transformers` [Certain].
  - Pass the user query and the top 15 RRF candidate chunks as pairs to the Cross-Encoder.
  - Sort by relevance score and truncate to the top 4 chunks [Certain].
  - *DoD:* Unit test confirms that Cross-Encoder execution takes $\le 300\text{ms}$ on CPU and produces a deterministic ordering where the most relevant architectural pattern is at index 0 [Certain].

---

## Phase 3: Structured Generation & Fallback Layer

*Goal: Synthesize retrieved blueprints into a strongly typed 5-stage roadmap via Groq.*

- [ ] **Task 3.1: Pydantic Schema Definitions**

  - Define `app/schemas/roadmap.py` containing:
    - `RoadmapRequest` (Target role, domain, current skills).
    - `Milestone` (Stage 1-5, name, technologies, architectural justification, tradeoff introduced, acceptance criteria).
    - `ProjectRoadmap` (Roadmap ID, title, domain, milestones list).
  - Add Pydantic field validators ensuring that `tradeoff` contains concrete architectural drawbacks (rejecting phrases like "none" or "makes it faster") [Certain].
  - *DoD:* Pydantic raises `ValidationError` when fed invalid or trivial tradeoff strings [Certain].
- [ ] **Task 3.2: Instructor + Groq Structured Inference Client**

  - Implement `app/services/generator.py`.
  - Initialize `Instructor` client patching the `groq.Groq` SDK client with `llama-3.1-8b-instant` [Certain].
  - Construct a system prompt strictly grounding the model in the retrieved context:
    > "You are a Principal Solutions Architect. Using ONLY the architecture patterns provided in the context below, create an incremental 5-stage scaffolding plan for the user's project idea. You must output data that strictly validates against the provided JSON schema."
    >
  - Configure `max_retries=2` to handle automated repair of schema violations [Certain].
  - *DoD:* Running the generation function returns an instantiated, validated `ProjectRoadmap` Python object [Certain].
- [ ] **Task 3.3: Circuit Breaker & Fallback System**

  - Implement `app/services/circuit_breaker.py` with states: `CLOSED`, `OPEN`, `HALF-OPEN` [Certain].
  - Trip breaker open if upstream Groq API throws 3 consecutive HTTP 429/500 errors [Certain].
  - When open, immediately serve pre-computed fallback roadmaps from disk (`data/fallbacks/`) without calling the external network [Certain].
  - *DoD:* Integration test simulating network outage verifies that client requests receive valid fallback roadmaps within 50ms rather than hanging or timing out [Certain].

---

## Phase 4: API Assembly, Middleware, & Interface

*Goal: Expose endpoints via FastAPI and provide an interactive testing client.*

- [ ] **Task 4.1: FastAPI Route Handlers**

  - Implement `app/api/v1/endpoints.py`:
    - `POST /api/v1/roadmaps` (Executes OOD Gate $\rightarrow$ Hybrid Search $\rightarrow$ Reranker $\rightarrow$ Instructor Generation) [Certain].
    - `GET /api/v1/roadmaps/{id}/export?format=markdown` (Converts roadmap JSON to a Markdown GitHub checklist) [Certain].
    - `GET /health` (Verifies Qdrant connection and inference client readiness) [Certain].
  - *DoD:* Automated integration test via `httpx.AsyncClient` executes the complete flow and asserts HTTP 200 with valid schema [Certain].
- [ ] **Task 4.2: Telemetry & Latency Profiling Middleware**

  - Implement `app/middleware/timing.py`.
  - Log execution latency for each sub-component: `t_retrieval_ms`, `t_rerank_ms`, `t_generation_ms`, `t_total_ms` [Certain].
  - Inject timing headers into API response: `X-Process-Time-Ms` [Certain].
  - *DoD:* Terminal logs display a structured JSON log line for every request detailing latency per sub-system [Certain].
- [ ] **Task 4.3: Minimal Streamlit UI**

  - Create `frontend/app.py` using Streamlit.
  - Provide input forms for: Target Role, Domain Interest, and Current Skills.
  - Display the 5-stage roadmap as interactive expandable cards showing tools, justification, and tradeoffs.
  - Provide a "Download GitHub Issue Checklist (.md)" button.
  - *DoD:* Running `streamlit run frontend/app.py` provides a functional browser interface that successfully communicates with the FastAPI backend [Certain].

---

## Phase 5: Automated Testing, Quality Gates, & CI/CD

*Goal: Prove system reliability, benchmark precision, and containerize for deployment.*

- [ ] **Task 5.1: Golden Dataset Curation & Retrieval Benchmark**

  - Create `tests/golden_dataset.json` containing 30 representative student queries and their manually mapped ground-truth blueprint IDs [Certain].
  - Write `tests/benchmarks/test_retrieval_precision.py` using Ragas or custom precision scoring.
  - Calculate Context Precision@4 across the dataset [Certain].
  - *DoD:* Test suite programmatically asserts that mean `context_precision` $\ge 0.85$ [Certain].
- [ ] **Task 5.2: Unit & Integration Test Suite**

  - Implement unit tests for:
    - RRF scoring algorithm logic (`tests/test_rrf.py`).
    - Pydantic schema validation rejection rules (`tests/test_schemas.py`).
    - Circuit breaker state transitions (`tests/test_circuit_breaker.py`).
  - *DoD:* Running `pytest --cov=app tests/` reports $\ge 85\%$ code coverage with 0 test failures [Certain].
- [ ] **Task 5.3: Production Multi-Stage Containerization**

  - Write a multi-stage `Dockerfile`:
    - Stage 1: Dependency builder (installs build tools, packages wheels) [Certain].
    - Stage 2: Runtime image (non-root user, copies only necessary wheels and source files) [Certain].
  - Update `docker-compose.yml` to orchestrate both the Qdrant service and the FastAPI backend service on a shared internal network [Certain].
  - *DoD:* Container builds in under 3 minutes; total runtime image size is $\le 450\text{ MB}$ [Certain].
- [ ] **Task 5.4: Continuous Integration Pipeline (GitHub Actions)**

  - Create `.github/workflows/ci.yml`:
    - Step 1: Lint code with `ruff check .` and `ruff format --check .` [Certain].
    - Step 2: Run type checking with `mypy app/` [Certain].
    - Step 3: Spin up ephemeral Qdrant service container [Certain].
    - Step 4: Run `pytest` test suite [Certain].
  - *DoD:* Pushing code to GitHub triggers the workflow and reports a green checkmark on all steps [Certain].
