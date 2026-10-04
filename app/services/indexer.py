"""
app/services/indexer.py
Subsystem 1: Blueprint Parsing, FastEmbed Vectorization, and Qdrant Indexing Engine.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Generator

from fastembed import SparseTextEmbedding, TextEmbedding
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

# -----------------------------------------------------------------------------
# Domain Exceptions (SPEC_V1.md Section 1.4)
# -----------------------------------------------------------------------------


class CorpusDirectoryNotFoundError(FileNotFoundError):
    """Raised if the blueprint directory does not exist on disk."""


class InvalidBlueprintStructureError(ValueError):
    """Raised if a Markdown file lacks mandatory metadata or structural headers."""


class QdrantIngestionError(RuntimeError):
    """Raised if network or database write fails during batch upsert."""


# -----------------------------------------------------------------------------
# Data Models (SPEC_V1.md Section 1.3 & ADR-05)
# -----------------------------------------------------------------------------


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

    @property
    def combined_embed_text(self) -> str:
        """SPEC Appendix A.1 Semantic Anchoring Invariant."""
        return f"Document: {self.module_name}\nSection: {self.header}\nContent: {self.content}"


# -----------------------------------------------------------------------------
# Ingestion & Indexing Engine
# -----------------------------------------------------------------------------


class IndexerService:
    RE_TITLE = re.compile(r"^#\s+Module:\s*(.+)$", re.MULTILINE)
    RE_DIFFICULTY = re.compile(r"^-\s*Difficulty Level:\s*([1-5])$", re.MULTILINE)
    RE_PREREQUISITES = re.compile(r"^-\s*Prerequisites:\s*(.+)$", re.MULTILINE)
    RE_LATENCY = re.compile(r"^-\s*Latency Impact:\s*(.+)$", re.MULTILINE)
    RE_MEMORY = re.compile(r"^-\s*Memory Footprint:\s*(.+)$", re.MULTILINE)
    RE_COMPLEXITY = re.compile(r"^-\s*Operational Complexity:\s*(.+)$", re.MULTILINE)

    def __init__(
        self,
        client: QdrantClient,
        collection_name: str = "engineering_blueprints",
    ) -> None:
        self.client = client
        self.collection_name = collection_name

        # Local ONNX runtime models (ADR-04: BAAI/bge-small-en-v1.5 and Qdrant/bm25)
        self.dense_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        self.sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")

    def create_collection_if_not_exists(self) -> None:
        """Provisions Qdrant collection with 384-dim Cosine dense vectors, BM25 sparse vectors, and payload schemas."""
        try:
            collections_response = self.client.get_collections()
            existing_names = {c.name for c in collections_response.collections}

            if self.collection_name not in existing_names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config={
                        "dense": models.VectorParams(
                            size=384,
                            distance=models.Distance.COSINE,
                        )
                    },
                    sparse_vectors_config={
                        "bm25": models.SparseVectorParams(
                            modifier=models.Modifier.IDF,
                        )
                    },
                )

            # Explicit payload indexes required for filtered HNSW graph traversal
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="difficulty_level",
                field_schema=models.PayloadSchemaType.INTEGER,
            )
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="prerequisites",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
        except Exception as exc:
            raise QdrantIngestionError(
                f"Failed to configure collection '{self.collection_name}': {exc}"
            ) from exc

    def parse_markdown(self, file_path: Path) -> list[BlueprintChunk]:
        """Reads a blueprint file, extracts metadata, and splits content by '## ' headers."""
        if not file_path.is_file():
            raise FileNotFoundError(f"Target markdown file not found: {file_path}")

        raw_text = file_path.read_text(encoding="utf-8")

        # 1. Extract Document-Level Attributes
        title_match = self.RE_TITLE.search(raw_text)
        diff_match = self.RE_DIFFICULTY.search(raw_text)
        prereq_match = self.RE_PREREQUISITES.search(raw_text)
        lat_match = self.RE_LATENCY.search(raw_text)
        mem_match = self.RE_MEMORY.search(raw_text)
        cpx_match = self.RE_COMPLEXITY.search(raw_text)

        # Replace: if not all([title_match, diff_match, prereq_match, lat_match, mem_match, cpx_match]):
        if not (
            title_match and diff_match and prereq_match and lat_match and mem_match and cpx_match
        ):
            raise InvalidBlueprintStructureError(
                f"File {file_path.name} is missing mandatory metadata headers or tradeoff fields."
            )

        module_name = title_match.group(1).strip()
        difficulty_level = int(diff_match.group(1).strip())
        prerequisites = [p.strip() for p in prereq_match.group(1).split(",") if p.strip()]
        tradeoff_latency = lat_match.group(1).strip()
        tradeoff_memory = mem_match.group(1).strip()
        tradeoff_complexity = cpx_match.group(1).strip()

        # 2. Split Structural Sections by \n(?=## )
        raw_sections = re.split(r"\n(?=## )", raw_text)
        chunks: list[BlueprintChunk] = []

        for sec in raw_sections:
            sec_clean = sec.strip()
            if not sec_clean.startswith("## "):
                continue

            lines = sec_clean.split("\n", 1)
            header = lines[0].lstrip("#").strip()
            content = lines[1].strip() if len(lines) > 1 else ""

            # Exclude Metadata summary section from retrieval index
            if header.lower() == "metadata":
                continue

            if len(content) < 50:
                continue

            # Idempotent deterministic UUIDv5 identifier
            chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{file_path.name}:{header}"))

            chunks.append(
                BlueprintChunk(
                    chunk_id=chunk_id,
                    module_name=module_name,
                    difficulty_level=difficulty_level,
                    prerequisites=prerequisites,
                    header=header,
                    content=content,
                    tradeoff_latency=tradeoff_latency,
                    tradeoff_memory=tradeoff_memory,
                    tradeoff_complexity=tradeoff_complexity,
                )
            )

        return chunks

    def _batch_iterator(self, items: list, batch_size: int) -> Generator[list, None, None]:
        for i in range(0, len(items), batch_size):
            yield items[i : i + batch_size]

    def index_all(self, directory_path: Path, batch_size: int = 32) -> int:
        """Executes full ingestion pipeline. Returns total count of indexed points."""
        if not directory_path.is_dir():
            raise CorpusDirectoryNotFoundError(f"Corpus directory does not exist: {directory_path}")

        self.create_collection_if_not_exists()

        markdown_files = sorted(directory_path.glob("*.md"))
        if not markdown_files:
            return 0

        all_chunks: list[BlueprintChunk] = []
        for file_path in markdown_files:
            chunks = self.parse_markdown(file_path)
            all_chunks.extend(chunks)

        if not all_chunks:
            return 0

        total_indexed = 0

        # Batch compute embeddings and upsert
        for batch in self._batch_iterator(all_chunks, batch_size):
            texts = [c.combined_embed_text for c in batch]

            dense_vectors = list(self.dense_model.embed(texts))
            sparse_vectors = list(self.sparse_model.embed(texts))

            points: list[models.PointStruct] = []
            for chunk, dense_vec, sparse_vec in zip(
                batch, dense_vectors, sparse_vectors, strict=True
            ):
                points.append(
                    models.PointStruct(
                        id=chunk.chunk_id,
                        vector={
                            "dense": dense_vec.tolist(),
                            "bm25": models.SparseVector(
                                indices=sparse_vec.indices.tolist(),
                                values=sparse_vec.values.tolist(),
                            ),
                        },
                        payload=chunk.model_dump(),
                    )
                )

            try:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points,
                    wait=True,
                )
                total_indexed += len(points)
            except (UnexpectedResponse, Exception) as exc:
                raise QdrantIngestionError(f"Failed to upsert points to Qdrant: {exc}") from exc

        return total_indexed
