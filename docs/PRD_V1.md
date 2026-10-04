# PRD: ScaffoldRAG — Incremental Complexity Portfolio Generator

**Document Version:** 1.0.0
**Target Release:** V1 MVP
**Status:** Approved for Implementation

---

## 1. Problem Statement & Success Metrics

### 1.1 Problem Statement

[Certain] Computing students fail technical screenings because their portfolios contain shallow, single-tier tutorial clones (e.g., standard API wrappers) that do not demonstrate production engineering tradeoffs. Existing project generators produce flat, ungrounded ideas without scaffolding incremental complexity (e.g., advancing from basic retrieval to hybrid search, reranking, evaluation, and CI/CD).

### 1.2 Target Audience

3rd- and 4th-year Data Science and Computing students seeking Machine Learning Engineer (MLE), Data Engineer (DE), or Backend AI Engineer roles.

### 1.3 Success Metrics

* [Certain] **Zero-Malformed-Output Rate:** 100% of API responses must pass Pydantic schema validation before reaching the client; 0 raw text or broken JSON payloads.
* [Likely] **P95 Latency:** Total request-to-response cycle $\le$ 3,500ms (Hybrid Retrieval $\le$ 400ms, Reranking $\le$ 600ms, LLM Generation $\le$ 2,500ms).
* [Likely] **Retrieval Precision (Ragas Context Precision):** $\ge$ 0.85 across test benchmarks.
* [Certain] **Unit Economics:** Cost per generated roadmap $\le$ $0.015 using hosted models (e.g., `openai/gpt-oss-20b` via Groq LPU), or $0.00 using local open-weight inference (e.g., Llama 3 8B via Ollama).
* [Likely] **Actionability Rate:** $\ge$ 80% of student testers successfully execute Milestone 1 within 60 minutes of generation.

---

## 2. User Stories & Acceptance Criteria

### US-1: Generate Scaffolded Roadmap

*As a* student job applicant,*I want to* submit my current skill level and target domain (e.g., "Healthcare Search"),*So that* I receive an incremental 5-stage project architecture plan grounded in verified engineering patterns.

* **Acceptance Criteria:**
  1. `POST /api/v1/roadmaps` accepts user background, target domain, and constraints.
  2. Returns exactly 5 sequential milestones (Stage 1: Baseline to Stage 5: Production/Ops).
  3. Every milestone includes: `concept_name`, `technologies`, `architectural_justification`, `tradeoff_introduced`, and `acceptance_criteria`.
  4. Response time does not exceed 4,000ms at P90.

### US-2: Review Engineering Tradeoffs

*As a* student preparing for technical interviews,*I want to* see the explicit architectural tradeoff introduced at each stage,*So that* I can explain *why* I added each tool when interviewed by engineering managers.

* **Acceptance Criteria:**
  1. Every stage explicitly lists at least one drawback (e.g., "Increases retrieval latency by ~35ms" or "Requires managing an asynchronous task queue").
  2. Generic claims (e.g., "makes it faster and better") are rejected by schema validators.

### US-3: Export Execution Checklist

*As a* developer,*I want to* export the generated roadmap as a Markdown checklist or GitHub Issue template,*So that* I can track my implementation progress inside my code repository.

* **Acceptance Criteria:**
  1. `GET /api/v1/roadmaps/{id}/export?format=markdown` returns a raw Markdown checklist with checkboxes (`- [ ]`).

---

## 3. Scope: V1 vs. Out-of-Scope

| In-Scope (Ships in V1)                                                | Out-of-Scope (Non-Goals for V1)                                                                                                                                                                                                                |
| :-------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Curated corpus of 15 modular engineering blueprints (Markdown).       | User accounts, authentication, profile history dashboards, and external multi-tenant database servers (e.g., PostgreSQL). Ephemeral, single-file embedded storage (SQLite in WAL mode) is in-scope strictly to support roadmap exports (US-3). |
| Hybrid search: BM25 (sparse) +`BAAI/bge-small-en-v1.5` (dense).     | Automated GitHub repo static analysis / code auditing.                                                                                                                                                                                         |
| Reciprocal Rank Fusion (RRF) algorithm (k=60).                        | Automated code grading via dynamic test runners / sandboxes.                                                                                                                                                                                   |
| Cross-Encoder reranking (`cross-encoder/ms-marco-MiniLM-L-6-v2`).   | Multi-agent autonomous debate loops.                                                                                                                                                                                                           |
| Pydantic schema enforcement via`Instructor`.                        | Paid monetization or payment gateway integration.                                                                                                                                                                                              |
| Single-page UI (Streamlit or lightweight React) + REST API (FastAPI). | Real-time job board scraping or dynamic market weighting.                                                                                                                                                                                      |

* ```
  User accounts, authentication, profile history dashboards, and external multi-tenant database servers (e.g., PostgreSQL). Ephemeral, single-file embedded storage (SQLite in WAL mode) is in-scope strictly to support roadmap exports (US-3).
  ```
* 

---

## 4. Data Model Changes & Contracts

### 4.1 Input Request Schema (`RoadmapRequest`)

```json
{
  "target_role": "Machine Learning Engineer",
  "domain_interest": "E-commerce Search & Discovery",
  "current_skills": ["Python", "Pandas", "Basic PyTorch"],
  "target_cloud_or_stack": "Local-first / Open Source"
}
```

### 4.2 Blueprint Chunk Schema (Vector Store Document)

```json
{
  "chunk_id": "c1f7a8a2-...",
  "module_name": "Reciprocal Rank Fusion Hybrid Search",
  "difficulty_level": 2,
  "prerequisites": ["blueprint_01_dense_baseline", "blueprint_02_sparse_bm25"],
  "header": "Architecture Pattern",
  "content": "Execute parallel retrieval over dense vector and sparse keyword indices...",
  "tradeoff_latency": "+15ms to +30ms total retrieval latency over single-index search",
  "tradeoff_memory": "Minimal in-memory footprint (<100 KB) for candidate score dictionaries",
  "tradeoff_complexity": "RRF is a rank-based heuristic that discards the magnitude of relevance"
}
```

### 4.3 Output Roadmap Schema (ProjectRoadmap)

```json
{
  "roadmap_id": "uuid-v4",
  "project_title": "string",
  "domain": "string",
  "milestones": [
    {
      "stage": 1,
      "name": "Naive Dense Retrieval Baseline",
      "tools_introduced": ["FastAPI", "Qdrant", "Sentence-Transformers"],
      "why_added": "Establishes a baseline semantic search pipeline with low complexity.",
      "tradeoff": "High semantic recall, but fails on exact keyword/SKU queries.",
      "verification_metric": "MRR > 0.60 on a 50-query golden dataset."
    }
  ]
}
```

## 5. Edge Cases & Failure States

### 5.1 Out-of-Distribution / Malicious Inputs

Scenario: User inputs non-computing queries (e.g., culinary recipes, creative writing) or prompt injection attacks.
System Handling: System computes maximum cosine similarity score against corpus using `BAAI/bge-small-en-v1.5`. If max score < 0.58, retrieval is aborted immediately. The domain layer raises `OutOfDistributionError`, which the API transport layer translates into an HTTP 422: "Query outside supported computing architecture domains." [Certain

Scenario: User inputs nonsense (e.g., "recipe for apple pie") or prompt injection attacks.
System Handling: System computes maximum cosine similarity score against corpus. If max score < 0.40, abort LLM generation immediately. Return HTTP 422: "Query outside supported computing architecture domains." [Certain].

### 5.2 Reranker Latency Timeout

Scenario: Reranker process exceeds 800ms due to CPU resource contention.
System Handling: System drops the Cross-Encoder step via a timeout wrapper and falls back directly to the top 4 documents selected by Reciprocal Rank Fusion [Likely]. Log a WARNING: reranker_fallback_triggered.

### 5.3 Downstream LLM Provider Outage or Rate Limit (HTTP 429/500)

Scenario: Commercial LLM API fails or rate-limits the backend.
System Handling: Circuit breaker pattern triggers after 3 consecutive failures. When open or degraded, the system returns a pre-computed, verified static blueprint template from disk matching the target role. The API returns an HTTP 200 status code with explicit response headers: 'X-Fallback-Applied: true' and 'X-Fallback-Reason: upstream_failure_or_load'.

### 5.4 Schema Validation Failure & Token Exhaustion

Scenario: LLM produces invalid JSON, skips required fields, or experiences token truncation.
System Handling: The generation request explicitly provisions `max_tokens=4096` to prevent `IncompleteOutputException`. Instructor retries the model up to 2 times, feeding back specific Pydantic `ValidationError` messages. If validation fails after 2 retries, the domain layer raises an exception, which the Circuit Breaker intercepts to serve a static fallback or the API layer maps to HTTP 502: "Generation validation failed. Upstream model output non-compliant." [Certain].

## 6. Architecture Decisions & Technical Resolutions (ADR Log)

### ADR-01: Hybrid Inference Topology (Local Vector Store + Remote LPU API)

* **Status:** Resolved / Implemented / Calibrated
* **Decision:** Decouple document retrieval from generative inference. The vector store (Qdrant) and the embedding/reranker pipelines will run locally, while LLM text generation is offloaded to a high-speed external inference provider (Groq running `openai/gpt-oss-20b`) [Certain].
* **Justification:** An 8 GB VRAM budget on a mobile RTX 4060 cannot concurrently host an 8B/20B instruction model, an embedding model, a Cross-Encoder reranker, and operating system overhead without triggering CUDA Out-Of-Memory exceptions or system RAM offloading (which degrades generation latency to over 15 seconds) [Certain]. Offloading to Groq ensures sub-second generation times at $0.00 cost under free-tier limits [Certain].

---

### ADR-02: Corpus Authoring & Verification Rubric

* **Status:** Resolved / Implemented
* **Decision:** The initial 15 modular engineering blueprints will be generated via technical architecture templates and subjected to a mandatory human engineering audit prior to indexing [Certain].
* **Justification:** To avoid cold-start delays while preventing AI hallucinations (e.g., deprecated libraries, imaginary syntax) from polluting the vector store [Certain].
* **Verification Rubric (All 4 Required to Pass):**
  1. **Dependency Audit:** Every referenced package/tool must be actively maintained (GitHub commit within the last 6 months) [Certain].
  2. **Quantifiable Metrics:** Every milestone must contain a measurable verification condition (e.g., latency bounds, test coverage percentage, or retrieval accuracy targets; no vague statements like "runs quickly") [Certain].
  3. **Explicit Tradeoff Profile:** Must identify at least one architectural drawback per stage (e.g., operational complexity, memory footprint, or query latency) [Certain].
  4. **Structure Integrity:** Must adhere strictly to the `Blueprint Chunk Schema` defined in Section 4.2 of this PRD [Certain].

---

### ADR-03: Primary Search Engine Selection (Qdrant)

* **Status:** Resolved / Implemented
* **Decision:** Deploy **Qdrant** as the primary storage and retrieval engine via Docker, rejecting PostgreSQL with `pgvector` for V1 [Certain].
* **Justification:** Qdrant provides native support for hybrid queries—simultaneously handling dense vectors and sparse keywords in a single call—and supports payload metadata filtering out of the box [Certain]. Using `pgvector` for this specific architecture would require writing and maintaining custom raw SQL to blend full-text search (`tsvector`) with vector cosine distances, adding unnecessary development overhead to the MVP [Certain].
* **System Constraints:**
  * Qdrant must run as an isolated container via Docker Compose (`qdrant/qdrant:latest`) exposing port `6333` with disk-backed storage volumes [Certain].
  * In-memory indexing is strictly prohibited to ensure database persistence between application restarts [Certain].

---

## ADR-04: Selection of `BAAI/bge-small-en-v1.5` as the Primary Embedding Model

* **Status:** Approved / Enforced
* **Context:** The system requires an embedding model to vectorize user input queries and match them against the reference architecture corpus. We evaluated five models: `all-MiniLM-L6-v2`, `BAAI/bge-small-en-v1.5`, `BAAI/bge-large-en-v1.5`, `nomic-embed-text-v1.5`, and OpenAI `text-embedding-3-small` [Certain].

#### Evaluation Matrix

| Evaluation Vector                      | `all-MiniLM-L6-v2` | `BAAI/bge-small-en-v1.5` | `BAAI/bge-large-en-v1.5` | `text-embedding-3-small` |
| :------------------------------------- | :------------------- | :------------------------- | :------------------------- | :------------------------- |
| **Output Dimensions**            | 384                  | **384**              | 1,024                      | 1,536                      |
| **Parameters**                   | 22.7M                | **33.5M**            | 335M                       | Closed                     |
| **MTEB Retrieval (NDCG@10)**     | 41.95                | **51.68**            | 54.29                      | 51.10                      |
| **Inference Runtime**            | Local (ONNX/CPU)     | **Local (ONNX/CPU)** | Local (Requires GPU)       | Remote HTTP API            |
| **CPU Latency per Chunk**        | ~8ms                 | **~12ms**            | ~110ms                     | ~250ms (Network dependent) |
| **Storage per Vector (Float32)** | 1.54 KB              | **1.54 KB**          | 4.10 KB                    | 6.14 KB                    |
| **Unit Ingestion Cost**          | $0.00                | **$0.00**            | $0.00                      | $0.02 / 1M tokens          |

#### Decision & Engineering Justification

Deploy `BAAI/bge-small-en-v1.5` using the **FastEmbed** runtime (ONNX engine) [Certain].

1. **Memory Economics in Vector Indexing:**
   * Storage cost scales linearly with dimension: $\text{Bytes} = \text{Dimensions} \times 4\text{ bytes}$ (Float32) [Certain].
   * At 384 dimensions, each vector occupies $1.54\text{ KB}$, compared to $6.14\text{ KB}$ for OpenAI's 1,536 dimensions.
   * Qdrant's in-memory HNSW connectivity graph requires an additional $1.5\times$ to $2.0\times$ memory overhead [Certain]. Keeping vectors at 384 dimensions guarantees that our entire index and graph fit comfortably in small RAM allocations without disk swapping [Certain].
2. **Diminishing Returns on Model Scale:**
   * Upgrading from `bge-small` to `bge-large` yields a marginal $+2.61$ increase in NDCG@10 at the cost of a $10\times$ parameter expansion ($33.5\text{M} \rightarrow 335\text{M}$) and a $9\times$ CPU inference latency penalty [Certain].
   * Because our pipeline runs a secondary Cross-Encoder reranker downstream, fine-grained semantic adjustments are handled at the reranking stage, rendering large bi-encoder embeddings redundant [Likely].
3. **Elimination of Remote API Failure Modes:**
   * Running locally via ONNX eliminates external API rate limits, authentication credentials, network latency, and billing dependencies [Certain].
4. **Container Optimization:**
   * Executing through FastEmbed removes the multi-gigabyte PyTorch dependency (`torch`), reducing our production Docker container footprint from $\approx 3.5\text{ GB}$ to under $400\text{ MB}$ [Certain].

---

### ADR-05: Blueprint AST Standardization and Flat Payload Contract

* **Context:** Synthesized blueprint markdown files introduced bulleted metadata labels (`- Latency Impact:`, `- Memory Footprint:`, `- Operational Complexity:`) and flat tradeoff fields, conflicting with PRD 4.2's initial nested `tradeoff_profile`.
* **Decision:** Standardize vector payload metadata into flat string keys matching `BlueprintChunk` in `SPEC_V1.md`. Enforce deterministic UUIDv5 generation derived from `file_path + header` to guarantee ingestion idempotency.
* **Consequences:** Eliminates schema nesting in Qdrant payloads, enables single-pass regex extraction in the static linter, and prevents chunk duplication on re-indexing runs.

---

## ADR-06: Cross-Encoder ONNX Runtime Migration & Latency SLA Calibration

* **Status:** Resolved / Enforced
* **Decision:** Replace PyTorch `sentence-transformers` with FastEmbed's native ONNX cross-encoder runtime (`TextCrossEncoder` running `Xenova/ms-marco-MiniLM-L-6-v2`) locked at `fastembed==0.4.2`. Bound passage input lengths to 350 characters and enforce a P95 CPU latency ceiling of $\le 600\text{ms}$ on 15 candidate pairs (steady-state: $\approx 420\text{ms}$).
* **Justification:** PyTorch CPU execution over un-quantized Float32 matrices required $949\text{ms}$, breaching the production budget. Dynamic INT8 PyTorch quantization improved latency to $517\text{ms}$ but triggered deprecated runtime warnings and retained a 1.2 GB container footprint. FastEmbed's fused C++ ONNX engine executes the exact same cross-attention weights in $350\text{ms}$–$420\text{ms}$ without PyTorch dependencies, preserving the $<400\text{MB}$ container SLA.
* **SLA Reconciliation:** Aligns Section 1.3 metrics:
  * Hybrid Retrieval: $\le 150\text{ms}$
  * Cross-Encoder Reranking: $\le 600\text{ms}$ (Steady-state P95: $\approx 420\text{ms}$)
  * Downstream Generation: $\le 2,500\text{ms}$
  * Overall Request P95: $\le 3,500\text{ms}$

---

### ADR-07: Client-Side Reciprocal Rank Fusion & Qdrant Version Decoupling

* **Status:** Resolved / Enforced
* **Decision:** Implement Reciprocal Rank Fusion ($k=60$) in application memory (`app/services/search/hybrid_search.py`) over parallel gRPC calls (`client.search`), rejecting Qdrant server-side RRF (`models.FusionQuery`).
* **Justification:** Qdrant's server-side Universal Query API (`query_points` with RRF) requires Qdrant $\ge 1.10.0$. Running against active container version 1.9.2 throws `grpc.StatusCode.UNIMPLEMENTED`. Furthermore, server-side RRF overwrites raw cosine distances with rank fractions ($1/(60+\text{rank})$), forcing an expensive secondary dense traversal just to evaluate the OOD gate. Client-side RRF executes in $<2\text{ms}$ in Python, works across all Qdrant versions, and preserves unpolluted scores for telemetry.

---

### ADR-08: Constrained JSON Decoding over Tool Calling for Groq Inference

* **Status:** Resolved / Enforced
* **Decision:** Configure Instructor to use `mode=instructor.Mode.JSON` (native constrained decoding via `response_format={"type": "json_object"}`) rather than `mode=instructor.Mode.TOOLS` when dispatching requests to Groq running `openai/gpt-oss-20b` [Certain].
* **Justification:** Groq's API gateway enforces `tool_choice="required"` on function-calling models. When using `openai/gpt-oss-20b`, the model does not emit function-calling tokens, causing Groq's gateway to abort with HTTP 400 `tool_use_failed`. Switching to `Mode.JSON` injects the Pydantic JSON schema directly into prompt instructions and leverages Groq's native JSON constrained decoding, allowing reliable schema enforcement without gateway rejection [Certain].
* **Consequences:** Eliminates upstream 400 gateway errors, requires explicit `max_tokens=4096` provisioning to avoid output truncation, and mandates negative prompt constraints to enforce field-level Pydantic validators [Certain].

---

### ADR-09: Embedded SQLite for Ephemeral Roadmap Export Persistence

* **Status:** Resolved / Enforced
* **Decision:** Implement an embedded SQLite database running in Write-Ahead Logging (WAL) mode (`data/roadmaps.db`) to store generated roadmaps, rejecting external database servers (like PostgreSQL) and pure in-memory dictionaries.
* **Justification:** US-3 requires retrieving a generated roadmap by its unique ID to export it as a Markdown file. Storing roadmaps in Python application memory causes memory leaks and loses data whenever the server restarts. Deploying PostgreSQL requires adding another background service and complex setup tools, breaking our rule to keep the container under 400 MB. SQLite is built directly into Python, adds zero installation weight, and handles concurrent reads and writes safely.

---

### ADR-10: Persistent Singleton Injection for Machine Learning Engines

* **Status:** Resolved / Enforced
* **Decision:** Instantiate AI and search components (`OODGate`, `HybridSearchEngine`, `CrossEncoderReranker`, `RoadmapGenerator`, and `QdrantClient`) once as long-lived singletons injected via FastAPI dependencies (`Depends`), strictly prohibiting creating new instances inside route functions.
* **Justification:** Creating these classes inside the route handler caused Python to reload model files from disk, re-create neural network sessions, and spawn new CPU worker threads on every single request. This slowed down response times to over 8,000ms–12,000ms, severely breaking the PRD latency limit of 3,500ms. Reusing a single shared instance throughout the application lifecycle dropped component setup overhead to zero, keeping total request latency within the 3,500ms target.

---

## ADR-11: Container Footprint SLA Calibration (Debian glibc vs. Alpine musl)

* **Status:** Resolved / Enforced
* **Decision:** Calibrate the production Docker runtime image size budget to $\le 550\text{ MB}$ (actual: 525 MB), retaining `python:3.11-slim` and rejecting Alpine Linux (`musl`).
* **Justification:** FastEmbed's ONNX Runtime relies on pre-compiled C++ CPython wheels requiring `glibc >= 2.31`. Running ONNX on Alpine Linux introduces runtime memory segmentation faults or requires multi-hour C++ source compilation. The application and isolated virtual environment have been aggressively optimized to 242 MB (down from 1.27 GB) by stripping PyTorch CUDA binaries and pruning debug symbols. The remaining 283 MB represents the immutable Debian Bookworm base OS and Python standard library runtime.
* **SLA Reconciliation:**
  * Build Duration: $\le 3\text{ minutes}$ (Actual: $1\text{m } 50\text{s}$ - Pass)
  * Production Image Size: $\le 550\text{ MB}$ (Actual: $525\text{ MB}$ - Pass)

---

## ADR-12: Decoupling Frontend UI Dependencies from REST API Microservice

* **Status:** Resolved / Enforced
* **Decision:** Move `streamlit` out of core runtime dependencies into an isolated Poetry group (`[tool.poetry.group.frontend.dependencies]`), excluding it from the production API container.
* **Justification:** `frontend/app.py` is a client interface. Installing `streamlit` inside the backend API container pulled 363 MB of transitive analytical libraries (`pyarrow` at 156 MB, `sympy` at 80 MB, `pandas` at 75 MB, `pydeck` at 23 MB) that are never imported by FastAPI or Uvicorn. Decoupling Streamlit dropped API virtual environment size from 763 MB to 242 MB, preventing an unneeded 1.27 GB container footprint.

---

## Appendix A: Metric Threshold Calibration & Validation Methodology

### A.1 Mathematical Foundation of the 85% Retrieval Precision Metric

* **Formal Definition:** In this system, "Retrieval Precision" strictly refers to **Context Precision** as formulated in the Ragas evaluation framework, rather than simple binary information retrieval precision [Certain]. Context Precision evaluates whether ground-truth relevant context chunks are ranked higher than irrelevant chunks in the retrieval list $K$ [Certain]:

$$
\text{Context Precision@K} = \frac{\sum_{k=1}^K (\text{Precision@}k \times v_k)}{\text{Total Relevant Chunks in Top } K}
$$

Where:

* $K = 4$ (the maximum number of chunks forwarded to the generator LLM) [Certain].
* $v_k \in \{0, 1\}$ represents whether the chunk at rank $k$ is semantically relevant to the architectural milestone [Certain].
* $\text{Precision@}k = \frac{\text{Relevant Chunks in Top } k}{k}$ [Certain].
* **Calibration Rationale (Why 85%?):**

  * If Context Precision drops below $0.70$, the downstream LLM suffers from **Context Poisoning**—it attempts to synthesize irrelevant architectural concepts into the user's roadmap, producing contradictory or unviable patterns [Likely].
  * Demanding $\ge 0.95$ precision on arbitrary student inputs requires continuous domain-specific fine-tuning of the embedding model, which is an unnecessary overhead for an MVP [Certain].
  * $0.85$ represents the empirical threshold where the top two retrieved slots are guaranteed to contain ground-truth context, leaving adequate margin for open-ended queries while preventing generation hallucinations [Likely].
* **Verification Pipeline:** Evaluated against an internal "Golden Dataset" of 30 curated student queries with human-verified blueprint mappings. CI tests will assert that the test suite's mean context precision score remains $\ge 0.85$ across automated test runs [Certain].

---

### A.2 Cognitive Justification & Measurement of the 60-Minute Execution Target

* **Formal Definition:** The 60-Minute Execution Target defines the system's **Time-to-Value (TTV)**: the maximum elapsed time from a student receiving their Stage 1 specification to executing their first working HTTP request on a local machine [Certain].
* **Cognitive Drop-Off Rationale (Why 60 Minutes?):**
  * Developer engagement decays exponentially when setup friction exceeds initial capability [Certain]. If a student encounters build failures, environment conflicts, or multi-service dependency issues in Stage 1, drop-off exceeds $70\%$ before reaching Stage 2 [Likely].
  * Stage 1 must deliver an immediate baseline win (e.g., spinning up a vector database and running a single query script) to build momentum for later complex stages (such as Reranking, Evaluation, and CI/CD) [Certain].
* **Operational Measurement & Enforcement:**
  * **Static Complexity Audit:** Generated Stage 1 milestones are bounded by strict complexity limits:
    * Total terminal setup commands $\le 3$ [Certain].
    * Total lines of executable Python starter code $\le 75$ lines [Certain].
    * External infrastructure dependencies $\le 1$ isolated Docker service or standard pip install [Certain].
  * **Empirical Validation:** Measured during developer usability testing by tracking the elapsed time required for a 3rd-year computing student to achieve an HTTP 200 response on their local machine without external debugging assistance [Certain].

---

### A.3 Geometric Grounding of the 0.58 Out-Of-Distribution (OOD) Gate

* **Formal Definition:** The minimum acceptable cosine similarity score between the user query embedding $\vec{u}$ and the nearest document embedding $\vec{v}$ in Qdrant:

$$
\text{Cosine Similarity}(\vec{u}, \vec{v}) = \frac{\vec{u} \cdot \vec{v}}{\|\vec{u}\|_2 \|\vec{v}\|_2}
$$

* **Vector Space Anisotropy & Query Prefix Dynamics (Why 0.58 instead of 0.40?):**
  * Transformer embeddings are anisotropic: directional vectors cluster in a narrow cone rather than distributing uniformly across the hypersphere [Certain].
  * FastEmbed's `dense_model.query_embed()` prepends BGE's asymmetric retrieval instruction: `"Represent this sentence for searching relevant passages: "`. This 8-token prefix introduces a common directional vector that raises the baseline cosine floor for all queries by $+0.08$ to $+0.12$ [Certain].
  * **Empirical Measurements (`BAAI/bge-small-en-v1.5` against 45-chunk corpus):**
    * Core Systems Architecture (`"Build an async RAG API with FastAPI"`): **$0.7585$** (Pass) [Certain].
    * Hybrid Retrieval (`"Implement Reciprocal Rank Fusion with BM25..."`): **$0.7974$** (Pass) [Certain].
    * Borderline Computing (`"React frontend state management using Redux..."`): **$0.6055$** (Pass) [Certain].
    * Out-of-Domain Culinary (`"Best sourdough bread recipe with wild yeast..."`): **$0.5362$** (Rejected) [Certain].
    * Out-of-Domain Noise (`"The quick brown fox jumps over the lazy dog"`): **$0.4103$** (Rejected) [Certain].
* **System Action:** The theoretical $0.40$ threshold failed because culinary noise scored $0.5362$. The decision boundary is permanently calibrated to **$0.58$**, cleanly separating technical computing topics from non-computing noise with a $+0.069$ margin [Certain].

---
