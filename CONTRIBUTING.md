# Contributing to ScaffoldRAG

Thank you for your interest in contributing to ScaffoldRAG. To maintain production engineering rigor, all contributors must adhere strictly to the architectural standards, code quality gates, and commit protocols outlined in this document.

---

## A. Development Principles & Architectural Constraints

Before submitting code, review the core specifications:
* `docs/PRD_v1.md`: Functional requirements and Architecture Decision Records (ADRs).
* `docs/SPEC_V1.md`: Class interfaces, PEP 484 type signatures, and Big-O invariants.
* `docs/SECURITY.md`: OWASP Top 10 for LLMs and network isolation boundaries.

### Hard Architectural Invariants:
1. **CPU-First Inference:** Do NOT install GPU-enabled PyTorch or CUDA binaries. All embeddings (`FastEmbed`) and rerankers (`Sentence-Transformers`) run on CPU via the ONNX runtime [Certain].
2. **Schema Enforcement:** All LLM inputs and outputs must pass through Pydantic V2 models via `Instructor`. Freeform, unvalidated prompt strings are strictly prohibited [Certain].
3. **Twelve-Factor Configuration:** Never hardcode URLs, ports, or models. Every operational control must be dynamically parsed through `app/core/config.py` from environment variables [Certain].
4. **Database Isolation:** Qdrant must run containerized using the named volume `qdrant_data` and bind strictly to loopback interfaces (`127.0.0.1`) [Certain].

---

## B. Local Environment Setup

### Prerequisites
* Linux or WSL2 (Ubuntu 22.04+)
* Python 3.11+
* Docker Engine & Docker Compose
* Poetry (`pip install poetry`)

### Setup Instructions
1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/scaffold-rag.git
   cd scaffold-rag
   ```
2. **Decouple the Virtual Environment (CRITICAL FOR WSL2):**
To prevent OSError: [Errno 5] caused by Windows NTFS file-locking over the 9P bridge, do NOT place the virtual environment on /mnt/c/. Host it on the native Linux ext4 filesystem [Certain]:
```bash
mkdir -p ~/.virtualenvs
python3.11 -m venv ~/.virtualenvs/scaffold-rag
source ~/.virtualenvs/scaffold-rag/bin/activate
pip install --upgrade pip setuptools wheel
```
Install Dependencies in Editable Mode:
Install the lightweight CPU-only PyTorch wheel first, followed by the project in editable mode [Certain]:
```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e .
poetry install --with dev
```
Provision Local Infrastructure:
Start the persistent Qdrant vector database:
```bash
docker compose up -d qdrant
curl -i http://127.0.0.1:6333/readyz
Configure Environment Secrets:
```
cp .env.example .env
3. **Edit .env and insert your real GROQ_API_KEY (must begin with 'gsk_')**
Verify Environment Health:
```bash
python scripts/verify_phase_0.py
```
4. **Blueprint Authoring Standards (ADR-02 Compliance)**
If contributing new reference blueprints to data/blueprints/, your Markdown file must pass all four criteria of the ADR-02 Verification Rubric [Certain]:
Naming & Hierarchy:
Files must be placed in data/blueprints/ and named <sequence_number>_<module_name>.md.
Root title must match # Module: <Name>.
Structural Sections (All 4 Required):
#### Metadata: Must declare Module ID, Difficulty Level (1-5), and Prerequisites.
#### Architecture Pattern: Concrete engineering explanation of design patterns and data flows.
#### Explicit Tradeoffs: Must document quantitative tradeoffs across Latency Impact, Memory Footprint, and Operational Complexity. Trivial phrases like "none" or "makes it faster" will be rejected.
#### Verification Metric: Must declare an objective, measurable acceptance metric (e.g., latency bounds, test coverage percentage, or MRR targets).
5. **Development Workflow & Git Standards**
Branch Naming Conventions
Create a dedicated feature branch from main:
feat/<feature-name>: For new capabilities or modules.
fix/<bug-name>: For resolving defects.
docs/<doc-name>: For documentation and blueprint updates.
refactor/<target>: For restructuring existing code without behavior changes.
Conventional Commits Specification
We enforce the Conventional Commits standard. Commit messages must be structured as follows:
```text
<type>(<scope>): <short imperative summary>

[optional detailed body]
[optional issue reference]
Permitted Types:
feat: A new user-facing or subsystem capability.
fix: A bug fix.
docs: Documentation, specifications, or blueprint changes.
build: Build system, Poetry configuration, or dependency updates.
refactor: Code refactoring that neither fixes a bug nor adds a feature.
test: Adding or correcting unit/integration tests.
chore: Maintenance tasks (linters, pre-commit, .gitignore).
Imperative Mood Rule:
Write commit subjects in the imperative mood (e.g., "Add hybrid retrieval logic" instead of "Added hybrid retrieval logic").
```
6. **Automated Quality Gates**
Before opening a Pull Request, you must run the automated quality checks locally. All checks must pass with zero warnings [Certain]:
```bash
# Code Style and Linting
poetry run ruff check .

# Code Formatting Verification
poetry run ruff format --check .

# Static Type Analysis
poetry run mypy app/

# Unit & Integration Test Suite
poetry run pytest --cov=app --cov-report=term-missing tests/
```
Pull Request (PR) Submission Checklist
When opening a PR, ensure that:

- [ ] **Your code passes ruff check ., ruff format --check ., and mypy app/.**

- [ ] **New code includes unit tests in tests/.**

- [ ] **Test coverage does not drop below 85%.**

- [ ] **New blueprints in data/blueprints/ satisfy the ADR-02 rubric.**

- [ ] **CHANGELOG.md is updated under the [Unreleased] heading.**

- [ ] **Commits follow the Conventional Commits specification.**