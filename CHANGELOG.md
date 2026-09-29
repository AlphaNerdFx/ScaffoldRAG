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