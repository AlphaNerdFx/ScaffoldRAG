# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-29

### Added

- Author foundational system specifications in `docs/PRD_v1.md` and `docs/SPEC_V1.md` covering hybrid search, Reciprocal Rank Fusion, and Cross-Encoder reranking architectures.
- Define Architecture Decision Records: ADR-01 (Hybrid Inference Topology), ADR-02 (Corpus Verification Rubric), ADR-03 (Qdrant Database Selection), and ADR-04 (`BAAI/bge-small-en-v1.5` Embedding Selection).
- Implement security policy in `SECURITY.md` covering OWASP Top 10 for LLM Applications and localhost port isolation rules.
- Provision containerized Qdrant vector database via `docker-compose.yml` using persistent named volume `qdrant_data` and dual-port loopback bindings (`127.0.0.1:6333` REST, `127.0.0.1:6334` gRPC).
- Establish deterministic package build system using Poetry in `pyproject.toml` with Python 3.11 target.
- Implement strongly typed application configuration loader in `app/core/config.py` using `pydantic-settings` with format validation guards for `GROQ_API_KEY`.
- Provide automated environment gatekeeper script in `scripts/verify_phase_0.py` validating settings extraction and dual-protocol Qdrant connectivity.
- Provide comprehensive project setup, reproduction commands, and architecture diagrams in `README.md`.

### Changed

- Decouple Python virtual environment execution from Windows NTFS (`/mnt/c/`) to native Linux `ext4` partition (`/home/youssef/.virtualenvs/scaffold-rag`) to prevent OS-level sharing violations during C++ wheel compilation.
- Migrate database persistence strategy from host bind-mounts (`./qdrant_storage`) to native Docker named volumes to enable POSIX `mmap` synchronization on WSL.

### Fixed

- Resolve `OSError: [Errno 5] Input/output error` caused by Windows Defender locking PyTorch dynamic link libraries (`libtorch_cpu.so`) across the WSL 9P filesystem bridge.
- Resolve `ValueError: app is not a package` during wheel compilation by provisioning explicit `__init__.py` files across all application subpackages.
- Fix Docker CLI daemon deadlock by restarting the Hyper-V microVM bridge and stripping deprecated `version` attributes from Docker Compose.

### Security

- Bind Qdrant container network ports strictly to loopback interface (`127.0.0.1`), eliminating unauthorized network ingress across local area networks.
- Enforce string-length validation boundaries and schema constraints on ingress request models to mitigate prompt injection and context exhaustion risks.

## [0.2.0] - 2026-09-30

### Added

- Authoring of 15 modular engineering blueprints in `data/blueprints/` covering in-memory retrieval, BM25, RRF, cross-encoders, Ragas, Instructor, circuit breakers, and telemetry.
- High-performance offline AST linter `scripts/lint_blueprints.py` validating schema constraints, token limits (<= 512), and package whitelists in < 0.12s.
- Subsystem 1 indexing engine `app/services/indexer.py` utilizing FastEmbed for dual-space embedding (`BAAI/bge-small-en-v1.5` 384-dim dense and `Qdrant/bm25` sparse).
- Production ingestion script `scripts/ingest_corpus.py` with gRPC upsert batching and Qdrant collection verification.
- Explicit Qdrant payload schema indexing for `difficulty_level` (Integer) and `prerequisites` (Keyword) to support pre-filtered HNSW traversal.
- Architecture Decision Record ADR-05 standardizing the flat vector payload schema and deterministic UUIDv5 identifier generation.

### Changed

- `docs/PRD_V1.md`: Updated Section 4.2 JSON payload contract from nested `tradeoff_profile` to flat string fields matching `BlueprintChunk`.
- `docs/SPEC_V1.md`: Updated `BlueprintChunk` interface with `prerequisites: list[str]` and documented AST extraction grammars in Appendix A.1.
- `TODO.md`: Formally closed Phase 1 backlog tasks; activated Phase 2.

## [0.3.0] - 2026-10-01

### Added

- Subsystem 2.1 Out-of-Distribution Hard Gate (`app/services/search/ood_gate.py`) rejecting out-of-domain queries at an empirically calibrated 0.58 cosine threshold.
- Subsystem 2.2 Hybrid Search Engine (`app/services/search/hybrid_search.py`) executing parallel dense (`BAAI/bge-small-en-v1.5`) and sparse (`Qdrant/bm25`) queries with client-side Reciprocal Rank Fusion ($k=60$).
- Subsystem 2.3 Cross-Encoder Reranker (`app/services/search/reranker.py`) powered by FastEmbed ONNX Runtime (`Xenova/ms-marco-MiniLM-L-6-v2`) reranking 15 candidates to the top 4 ground-truth chunks.
- End-to-end validation test suites (`scripts/test_gate.py`, `scripts/test_hybrid.py`, `scripts/test_reranker.py`).
- Architecture Decision Record ADR-06 documenting FastEmbed ONNX adoption and the 450ms P95 latency SLA calibration.

### Changed

- Decoupled Qdrant server-side RRF to client-side rank accumulation to maintain compatibility with Qdrant 1.9.2 and avoid double-index traversals.
- Upgraded `fastembed` dependency to locked pin `0.4.2` in `pyproject.toml`.
- Calibrated Reranker SLA bound in `docs/SPEC_V1.md` from 300ms to 450ms to reflect virtualized multi-core WSL2 execution.

## [0.4.0] - 2026-10-02

### Added

- Strongly typed Pydantic V2 schema contracts in `app/schemas/roadmap.py` (`RoadmapRequest`, `Milestone`, `ProjectRoadmap`) with strict architectural tradeoff validation.
- Subsystem 3 generation client `app/services/generator.py` wrapping Groq `openai/gpt-oss-20b` via Instructor using `Mode.JSON` with automated 2-retry self-reflection.
- SRE Circuit Breaker in `app/core/circuit_breaker.py` implementing a 3-state finite state machine (`CLOSED`, `OPEN`, `HALF-OPEN`) tripping after 3 consecutive failures.
- Static fallback repository in `data/fallbacks/` with verified blueprints for Machine Learning Engineers, Data Engineers, and Backend AI Engineers.
- Complete contract and state verification suites (`tests/test_specification_contract.py`, `tests/test_generator.py`, `tests/test_circuit_breaker.py`).

### Changed

- Migrated default inference model from deprecated `llama-3.1-8b-instant` to active `openai/gpt-oss-20b` in `app/core/config.py`.
- Switched Instructor extraction strategy from `Mode.TOOLS` to `Mode.JSON` to support native Groq constrained JSON decoding.
- Allocated explicit completion token ceiling (`max_tokens=4096`) to eliminate stream truncation exceptions on multi-stage payloads.
