# Technical Specification (SPEC_V1): ScaffoldRAG Subsystems

**Document Version:** 1.0.0
**Target Release:** V1 MVP
**Status:** Approved for Implementation
**Standard:** PEP 484 Type Hints | Strict Pydantic V2 | Hexagonal Subsystem Boundaries

---

## Subsystem Overview & Dependency Topology

```text
+-----------------------------------------------------------------------------+
|                            SUBSYSTEM ARCHITECTURE                           |
+-----------------------------------------------------------------------------+
|                                                                             |
|  [ Ingress Request ]                                                        |
|         |                                                                   |
|         v                                                                   |
|  +-----------------------------------------------------------------------+  |
|  | Subsystem 4: API & Middleware Layer (FastAPI, TimingMiddleware)       |  |
|  +-----------------------------------------------------------------------+  |
|         |                                                                   |
|         +---> [ Subsystem 2.1: OOD Gate ] (bge-small Cosine Check)          |
|                     |                                                       |
|                     v (Pass: Cosine >= 0.58)                                |
|         +---> [ Subsystem 2.2: Hybrid Search ] (Client-Side RRF, k=60)      |
|                     |  - Parallel gRPC: Dense ('dense') + Sparse ('bm25')   |
|                     v (Top 15 Chunks via Reciprocal Rank Fusion)            |
|         +---> [ Subsystem 2.3: Cross-Encoder Reranker ] (ONNX MiniLM-L-6-v2)|
|                     |  - Content bounded to 350 chars; P95 <= 600ms         |
|                     v (Top 4 Highest-Scoring Chunks)                        |
|  +-----------------------------------------------------------------------+  |
|  | Subsystem 3: Generation Layer (Instructor + Groq Llama-3.1-8B)        |  |
|  | * Protected by Subsystem 5: Circuit Breaker & Offline Fallbacks      |  |
|  +-----------------------------------------------------------------------+  |
```

---

## Subsystem 1: Ingestion & Indexing Engine (app/services/indexer.py)

### 1.1 Purpose & Architectural Responsibility

Parses modular Markdown engineering blueprints from disk, validates their metadata against ADR-02, splits them into semantic chunks by secondary headers (##), generates 384-dimensional dense vectors and sparse token weights via FastEmbed, and upserts them idempotently into Qdrant [Certain].

### 1.2 Mathematical Invariants & Algorithmic Complexity

- **Vector Dimensionality:** Exactly 384 `Float32` dimensions (BAAI/bge-small-en-v1.5) [Certain].
- **Distance Metric:** Cosine Similarity (

  ```
  u . v / (||u|| x ||v||)
  ```

  ) [Certain].
- **Chunking Complexity:**

  $$
  O(N)
  $$

  where N is document character length (linear single-pass scan) [Certain].
- **Space Complexity:**

  $$
  O(C×D)
  $$

  where C is chunk count and D=384 floats (1.54 KB per vector payload) [Certain].

### 1.3 Interface Contract & Method Signatures

```python
from pathlib import Path
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient

class BlueprintChunk(BaseModel):
    chunk_id: str = Field(..., description="Deterministic UUIDv5 generated from filepath + header")
    module_name: str = Field(..., min_length=3, max_length=100)
    difficulty_level: int = Field(..., ge=1, le=5)
    prerequisites: list[str] = Field(default_factory=list)
    header: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=50)
    tradeoff_latency: str = Field(...)
    tradeoff_memory: str = Field(...)
    tradeoff_complexity: str = Field(...)

class IndexerService:
    def __init__(self, client: QdrantClient, collection_name: str = "engineering_blueprints") -> None:
        """Initializes FastEmbed models and ensures Qdrant collection exists with dense + sparse schemas."""
        ...

    def parse_markdown(self, file_path: Path) -> list[BlueprintChunk]:
        """Reads a blueprint file, extracts metadata, and splits content by '## ' headers."""
        ...

    def create_collection_if_not_exists(self) -> None:
        """Provisions Qdrant collection with 384-dim Cosine vector param and sparse index param."""
        ...

    def index_all(self, directory_path: Path) -> int:
        """Executes full ingestion pipeline. Returns total count of indexed points."""
        ...
```

### 1.4 Error States & Exception Hierarchy

- CorpusDirectoryNotFoundError: Raised if directory_path does not exist on disk [Certain].
- InvalidBlueprintStructureError: Raised if a Markdown file lacks mandatory metadata headers [Certain].
- QdrantIngestionError: Raised if network or disk write fails during batch upsert [Certain].

---

## Subsystem 2: Search & Ranking Pipeline (app/services/search/)

### 2.1 Sub-Component: Out-Of-Distribution (OOD) Gate (`ood_gate.py`)

- **Purpose:** Computes the cosine similarity of the user's input query against the nearest vector in Qdrant [Certain]. Rejects non-computing, culinary, or spam queries before invoking downstream models [Certain].
- **Mathematical Invariant:** Query accepted **if and only if**:

  $$
  \max_i\left(\cos(\vec q,\vec v_i)\right) \ge 0.58
  $$

- **Transport Boundary:** Raises domain-level `OutOfDistributionError`. Must not import or reference FastAPI HTTP exceptions.
- **Protocol:** Dispatches `client.search` over the named vector `"dense"` using `prefer_grpc=True`.

```python
class OODGate:
    def __init__(
        self,
        client: QdrantClient,
        collection_name: str = "engineering_blueprints",
        model_name: str = "BAAI/bge-small-en-v1.5",
        threshold: float = 0.58,
    ) -> None: ...

    def evaluate_query(self, query_text: str) -> tuple[bool, float]:
        """Embeds query_text via FastEmbed query_embed. Returns (is_valid, max_similarity)."""
        ...

    def validate_query(self, query_text: str) -> float:
        """Validates query; raises OutOfDistributionError if below threshold."""
        ...
```

### 2.2 Sub-Component: Hybrid Search & Reciprocal Rank Fusion (hybrid_search.py)

- **Purpose:** Queries Qdrant over gRPC for dense vectors (bge-small-en-v1.5) and sparse vectors (Qdrant/bm25), fusing candidate ranks in application memory via Reciprocal Rank Fusion (k=60) [Certain].
- **Mathematical Formulation:**

  ```math
  RRF(d)=1/(60+rankdense(d))+1/(60+ranksparse(d))
  ```
- **Candidate Pool Output:** Exactly 15 candidate chunks [Certain].

```python
class ScoredChunk(BaseModel):
    chunk_id: str
    content: str
    module_name: str
    rrf_score: float
    metadata: dict[str, Any]

class HybridSearchEngine:
    def __init__(
        self,
        client: QdrantClient,
        collection_name: str = "engineering_blueprints",
        dense_model_name: str = "BAAI/bge-small-en-v1.5",
        sparse_model_name: str = "Qdrant/bm25",
        rrf_k: int = 60,
    ) -> None: ...

    def search(
        self,
        query_text: str,
        top_k: int = 15,
        max_difficulty: int | None = None,
    ) -> list[ScoredChunk]:
        """Executes dual retrieval and applies client-side RRF scoring."""
        ...
```

### 2.3 Sub-Component: Cross-Encoder Reranker (`app/services/search/reranker.py`)

- **Purpose:** Re-scores the top 15 RRF candidates using full cross-attention over (query, document) pairs, returning the top 4 ground-truth chunks [Certain].
- **Model:** `Xenova/ms-marco-MiniLM-L-6-v2` via `fastembed.rerank.cross_encoder.TextCrossEncoder` [Certain].
- **Passage Bounding:** Inputs are formatted compactly (f"{module_name} ({header}): {content[:350]}") to conform to MS MARCO passage lengths and eliminate quadratic attention bloat [Certain].
- **Model Engine**: Xenova/ms-marco-MiniLM-L-6-v2 executed via fastembed.rerank.cross_encoder.TextCrossEncoder (pure ONNX Runtime) [Certain].
- **Time Complexity:** $O(K \times (L_q + L_d)^2)$ where $K=15$ candidate pairs, $(L_q + L_d) \le 120$ tokens [Certain].
- **Execution Bound:** Maximum execution time ≤600ms on CPU across 15 candidate pairs (P95) [Certain].
- **Purpose:** Re-scores the top 15 RRF candidates using full self-attention over (query, document) pairs, returning the top 4 ground-truth chunks [Certain].
- **Model:** cross-encoder/ms-marco-MiniLM-L-6-v2 [Certain].
- **Time Complexity:**

  $$
  O(K×(Lq+Ld)2)
  $$

  where K=15 candidate pairs, L is sequence length [Certain].
- **Execution Bound:** Maximum execution time ≤300ms on CPU [Certain].

```python
class CrossEncoderReranker:
    def __init__(
        self,
        model_name: str = "Xenova/ms-marco-MiniLM-L-6-v2",
        threads: int = 4,
        max_content_chars: int = 350,
    ) -> None: ...

    def rerank(
        self,
        query_text: str,
        candidates: list[ScoredChunk],
        top_n: int = 4,
    ) -> list[ScoredChunk]:
        """Calculates cross-attention logit scores and returns top_n ordered documents."""
        ...
```

---

## Subsystem 3: Generation & Schema Enforcement (app/services/generator.py)

### 3.1 Purpose & Contract

Takes the top 4 reranked architecture chunks and user constraints, compiles a grounded system prompt with negative constraints, and invokes `openai/gpt-oss-20b` via Groq wrapped with Instructor in `Mode.JSON` [Certain]. Guarantees 100% valid Pydantic output using automated 2-retry reflection loops and explicit `max_tokens=4096` completion bounds [Certain].

### 3.2 Data Models & Field Invariants (app/schemas/roadmap.py)

```python
from pydantic import BaseModel, Field, field_validator
import uuid

class RoadmapRequest(BaseModel):
    target_role: str = Field(..., min_length=3, max_length=50)
    domain_interest: str = Field(..., min_length=3, max_length=100)
    current_skills: list[str] = Field(..., min_length=1, max_length=15)

class Milestone(BaseModel):
    stage: int = Field(..., ge=1, le=5)
    name: str = Field(..., min_length=5, max_length=100)
    tools_introduced: list[str] = Field(..., min_length=1)
    why_added: str = Field(..., min_length=20)
    tradeoff: str = Field(..., min_length=15)
    verification_metric: str = Field(..., min_length=15)

    @field_validator("tradeoff")
    @classmethod
    def validate_tradeoff(cls, v: str) -> str:
        banned = ["none", "makes it better", "faster", "easy"]
        if any(term in v.lower() for term in banned):
            raise ValueError("Tradeoff must document an explicit engineering drawback.")
        return v

class ProjectRoadmap(BaseModel):
    roadmap_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_title: str = Field(..., min_length=5, max_length=100)
    domain: str = Field(..., min_length=3, max_length=100)
    milestones: list[Milestone] = Field(..., min_length=5, max_length=5)

    @field_validator("milestones")
    @classmethod
    def validate_sequential_stages(cls, v: list[Milestone]) -> list[Milestone]:
        stages = [m.stage for m in v]
        if stages != [1, 2, 3, 4, 5]:
            raise ValueError(f"Milestones must strictly contain stages 1 through 5 in order. Received: {stages}")
        return v
```

### 3.3 Interface & Method Signature

```python
from app.schemas.roadmap import RoadmapRequest, ProjectRoadmap
from app.services.search.hybrid_search import ScoredChunk

class RoadmapGenerator:
    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        temperature: float = 0.2,
    ) -> None:
        """Initializes Groq client patched with Instructor in Mode.JSON for schema validation."""
        ...

    def generate(self, request: RoadmapRequest, context_chunks: list[ScoredChunk]) -> ProjectRoadmap:
        """Invokes LLM with system prompt + context, enforcing max_tokens=4096 and retrying up to 2 times on validation errors."""
        ...
```

---

## Subsystem 4: API & Telemetry Middleware Layer (app/api/)

### 4.1 Route Declarations & HTTP Contracts (app/api/v1/endpoints.py)

| HTTP Method | Route Path | Request Body | Response Body | Status Codes | Response Headers Contract |
| :--- | :--- | :--- | :--- | :--- | :--- |
| POST | `/api/v1/roadmaps` | RoadmapRequest (JSON) | ProjectRoadmap (JSON) | 200, 422, 502, 503 | `X-Process-Time-Ms`, `X-Fallback-Applied`, `X-Fallback-Reason` (optional) |
| GET | `/api/v1/roadmaps/{id}/export?format=markdown` | None | Raw Text (`text/markdown`) | 200, 404, 422 | `Content-Type: text/markdown`, `X-Process-Time-Ms` |
| GET | `/health` | None | `{"status": "healthy", "qdrant": bool}` | 200, 503 | `X-Process-Time-Ms` |

### 4.2 Latency Profiling Middleware (app/middleware/timing.py)

- Injects `X-Process-Time-Ms` HTTP response header representing total request execution time in milliseconds.
- Emits one structured JSON log line per request to standard output (`stdout`) via `LatencyProfilingMiddleware`:
```json
{
  "timestamp": "2026-10-04T03:40:34.419870+00:00",
  "method": "POST",
  "path": "/api/v1/roadmaps",
  "status_code": 200,
  "client_ip": "127.0.0.1",
  "t_ood_ms": 12.5,
  "t_retrieval_ms": 45.2,
  "t_rerank_ms": 380.1,
  "t_generation_ms": 2480.0,
  "t_total_ms": 2917.8
}
```

### 4.3 Subsystem 4.3: Local Storage Repository (`app/services/storage.py`)

- **Purpose:** Stores and retrieves generated roadmaps by their UUID so they can be exported without setting up an external database server.
- **Engine:** Python's built-in `sqlite3` using Write-Ahead Logging (`PRAGMA journal_mode = WAL;`) and normal synchronization (`PRAGMA synchronous = NORMAL;`).
- **File Location:** `data/roadmaps.db`.

```python
class RoadmapRepository(Protocol):
    def save(self, roadmap: ProjectRoadmap) -> None: ...
    def get_by_id(self, roadmap_id: str) -> ProjectRoadmap | None: ...

class SQLiteRoadmapRepository:
    def __init__(self, db_path: Path | str = "data/roadmaps.db") -> None: ...
    def save(self, roadmap: ProjectRoadmap) -> None: ...
    def get_by_id(self, roadmap_id: str) -> ProjectRoadmap | None: ...
```

### 4.4 Subsystem 4.4: Markdown Checklist Serializer (app/services/exporter.py)
Purpose: Converts a validated ProjectRoadmap object into a GitHub-ready Markdown checklist.
Formatting Rules:
* Root title formatted as # {project_title} with metadata block.
* Each milestone formatted as ## Stage {stage}: {name}.
* Acceptance criteria formatted with unchecked interactive boxes:  - [ ] **Verification Metric:** {verification_metric}.
* Explicit tradeoffs and technical justifications included beneath each stage.

---

## Subsystem 5: Fault Tolerance & Circuit Breaker (app/core/circuit_breaker.py)

### 5.1 State Machine Specification

The Circuit Breaker wraps calls to the external Groq inference engine to prevent cascading connection starvation [Certain].

```
				+-------------------+
                |      CLOSED       | <---+ (Reset on Successful Probe)
                |  (Normal Traffic) |     |
                +-------------------+     |
                          |               |
               (Consecutive Fails >= 3)   |
                          v               |
                +-------------------+     |
      +-------> |       OPEN        |     |
      |         |  (Serve Fallback) |     |
      |         +-------------------+     |
 (Probe Fails)            |               |
      |          (Timeout > 45 sec)       |
      |                   v               |
      |         +-------------------+     |
      +-------- |     HALF-OPEN     | ----+
                |   (Test 1 Call)   |
                +-------------------+
```

### 5.2 Interface & Method Signatures

```python
class FallbackProvider:
    def __init__(self, fallback_dir: Path | None = None) -> None:
        """Loads and caches verified static JSON blueprints from disk at boot time."""
        ...

    def get_static_roadmap(self, role: str) -> ProjectRoadmap:
        """Resolves target role to a matching in-memory static fallback blueprint."""
        ...

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_timeout_sec: float = 45.0) -> None:
        ...

    def execute(
        self,
        func: Callable[..., T],
        fallback_func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Executes func if CLOSED/HALF-OPEN. If OPEN or on error, executes fallback_func in <= 50ms."""
        ...
```

---

## Complete Verification & Integration Test Harness

An implementation is considered compliant with SPEC_V1 if and only if the following contract test passes without modification [Certain]:

```python
# tests/test_specification_contract.py
import pytest
from app.schemas.roadmap import RoadmapRequest, ProjectRoadmap, Milestone

def test_milestone_tradeoff_enforcement():
    """Asserts that the system rejects trivial, non-technical tradeoff strings."""
    with pytest.raises(ValueError):
        Milestone(
            stage=1,
            name="Baseline Search",
            tools_introduced=["FastAPI"],
            why_added="Initial implementation for testing.",
            tradeoff="None. It makes the system better and faster.", # MUST FAIL
            verification_metric="Latency < 50ms"
        )

def test_roadmap_stage_count_invariant():
    """Asserts that exactly 5 milestones are required by the schema."""
    with pytest.raises(ValueError):
        ProjectRoadmap(
            project_title="Invalid Pipeline",
            domain="E-commerce",
            milestones=[] # Empty milestones MUST FAIL
        )
```

---

Appendix A: Chunking Methodology & Semantic Boundary Specification
------------------------------------------------------------------

A.1 Chunking Invariant & Delimiter Strategy

- Splitting Mechanism: Pure structural header splitting matching regular expression `\n(?=## )`. Arbitrary character or token-length sliding window chunking is strictly prohibited [Certain].
- Semantic Anchoring Invariant: Every generated chunk must prepend the root document title (`# `) to preserve parent domain context in the vector embedding space (`combined_embed_text = "Document: {root_title}\nSection: {header}\nContent: {content}"`) [Certain].
- Token Ceiling: Maximum allowable tokens per chunk is 512 tokens (bounded by the context limit of BAAI/bge-small-en-v1.5). Any section exceeding 512 tokens must be sub-partitioned by tertiary headers (`### `) [Certain].

A.1.1 Document AST Parsing Grammar & Token Mappings
All 15 blueprints adhere strictly to the following top-level header and bullet mapping:

- Root Title: `^# Module:\s*(.+)$` -> `module_name`
- Difficulty: `^-\s*Difficulty Level:\s*([1-5])$` -> `difficulty_level`
- Prerequisites: `^-\s*Prerequisites:\s*(.+)$` -> `prerequisites` (split by `,`)
- Latency: `^-\s*Latency Impact:\s*(.+)$` -> `tradeoff_latency`
- Memory: `^-\s*Memory Footprint:\s*(.+)$` -> `tradeoff_memory`
- Complexity: `^-\s*Operational Complexity:\s*(.+)$` -> `tradeoff_complexity`

A.2 Engineering Justification

- Vector Embedding Dilution: Fixed-size token windows (e.g., 512 tokens with 50-token overlap) span across multiple unrelated architectural ideas, flattening vector magnitude across competing semantic dimensions [Certain]. Header-delimited chunking guarantees that each vector represents an isolated, single-concept engineering unit.
- Lexical Integrity for Sparse Search: Arbitrary chunk slicing splits named entities and code tokens across chunk boundaries (e.g., splitting `FastAPI` into two tokens), breaking BM25 sparse inverted index matching [Certain].

---

Appendix B: Reliability Boundaries: Evaluation Harness vs. Circuit Breaker
--------------------------------------------------------------------------

B.1 Separation of Concerns Matrix

| Dimension             | Circuit Breaker (Subsystem 5)          | Evaluation Harness (Task 5.1)       |
| :-------------------- | :------------------------------------- | :---------------------------------- |
| Lifecycle Phase       | Runtime / Production Traffic           | Offline / CI/CD (GitHub Actions)    |
| Monitored Metric      | HTTP error codes, network timeouts     | Context Precision@K, Faithfulness   |
| Action on Breach      | Trips to OPEN; serves cached disk JSON | Blocks Pull Request; exits code 1   |
| Operational Objective | System Availability & Fault Tolerance  | Algorithmic Correctness & Precision |

B.2 System Boundary Rules

- Rule 1: The Circuit Breaker MUST NOT execute semantic assertions, metric grading, or quality evaluations during live client requests [Certain]. Its sole function is measuring failure rates against external APIs to prevent thread starvation [Certain].
- Rule 2: The Evaluation Harness MUST NOT run on live production traffic [Certain]. It executes exclusively against a fixed Golden Dataset (`tests/golden_dataset.json`) to detect regression in retrieval ranking or model faithfulness prior to deployment [Certain].

---

Appendix C: Knowledge Substrate Strategy: Curated Synthetic vs. Scraped Web Data
--------------------------------------------------------------------------------

C.1 Corpus Mandate

- Ingestion Scope: The V1 knowledge base is restricted to the 15 curated, schema-compliant Markdown blueprints authored in `data/blueprints/` [Certain].
- Dynamic Scraping Prohibition: Ingesting raw HTML, third-party blogs, or dynamic online documentation via scrapers is strictly prohibited in V1 [Certain].

C.2 Engineering Justification

- Signal-to-Noise Ratio (SNR): Raw web documentation contains residual navigation tokens, boilerplate headers, and marketing copy that pull dense embeddings away from target technical concepts [Certain].
- Schema Enforcement: The downstream generation schema requires explicit, balanced tradeoffs (latency, memory, complexity) and verifiable metrics. Public web tutorials rarely document drawbacks uniformly; uncurated data forces downstream LLMs to hallucinate missing fields [Certain].
- Deterministic Evaluation: Benchmarking retrieval precision via Ragas requires immutable document chunk IDs in the Golden Dataset. Scraped online resources introduce temporal decay, URL drift, and silent content mutations that invalidate evaluation baselines [Certain].
