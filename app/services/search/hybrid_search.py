"""Subsystem 2.2: Hybrid Search Engine with Client-Side Reciprocal Rank Fusion (RRF).

Combines dense semantic retrieval (bge-small-en-v1.5) with sparse lexical retrieval (bm25)
using RRF (k=60) to produce 15 high-recall candidate chunks. Compatible with Qdrant 1.9.x+.
"""

from typing import Any

from fastembed import SparseTextEmbedding, TextEmbedding
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient, models


class ScoredChunk(BaseModel):
    """Domain model representing a retrieved and scored chunk of an engineering blueprint."""

    chunk_id: str = Field(..., description="Deterministic UUIDv5 chunk identifier")
    content: str = Field(..., description="Raw text content of the blueprint section")
    module_name: str = Field(..., description="Parent blueprint module title")
    rrf_score: float = Field(..., description="Reciprocal Rank Fusion score")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata payload")


class HybridSearchEngine:
    """Executes dense + sparse retrieval and applies client-side Reciprocal Rank Fusion."""

    def __init__(
        self,
        client: QdrantClient,
        collection_name: str = "engineering_blueprints",
        dense_model_name: str = "BAAI/bge-small-en-v1.5",
        sparse_model_name: str = "Qdrant/bm25",
        rrf_k: int = 60,
    ) -> None:
        self.client = client
        self.collection_name = collection_name
        self.rrf_k = rrf_k
        self.dense_model = TextEmbedding(model_name=dense_model_name)
        self.sparse_model = SparseTextEmbedding(model_name=sparse_model_name)

    def search(
        self,
        query_text: str,
        top_k: int = 15,
        max_difficulty: int | None = None,
    ) -> list[ScoredChunk]:
        """Executes parallel-compatible dense and sparse retrieval, merging results via RRF.

        Args:
            query_text: User input query.
            top_k: Total number of fused candidates to return (Default: 15).
            max_difficulty: Optional metadata filter on difficulty_level <= max_difficulty.

        Returns:
            list[ScoredChunk]: Exactly top_k chunks sorted descending by RRF score.
        """
        if not query_text or not query_text.strip():
            return []

        # 1. Compute Dense Vector (384 dimensions)
        dense_generator = self.dense_model.query_embed(query_text)
        query_dense: list[float] = list(dense_generator)[0].tolist()

        # 2. Compute Sparse BM25 Vector (Indices + Values)
        sparse_generator = self.sparse_model.embed([query_text])
        sparse_result = list(sparse_generator)[0]

        # 3. Build Optional Difficulty Filter
        search_filter = None
        if max_difficulty is not None:
            search_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="difficulty_level",
                        range=models.Range(lte=max_difficulty),
                    )
                ]
            )

        # 4. Dense Retrieval Call (Qdrant 1.9.2 compatible)
        dense_hits = self.client.search(
            collection_name=self.collection_name,
            query_vector=models.NamedVector(
                name="dense",
                vector=query_dense,
            ),
            query_filter=search_filter,
            limit=top_k,
            with_payload=True,
            with_vectors=False,
        )

        # 5. Sparse Retrieval Call (Qdrant 1.9.2 compatible)
        sparse_hits = self.client.search(
            collection_name=self.collection_name,
            query_vector=models.NamedSparseVector(
                name="bm25",
                vector=models.SparseVector(
                    indices=sparse_result.indices.tolist(),
                    values=sparse_result.values.tolist(),
                ),
            ),
            query_filter=search_filter,
            limit=top_k,
            with_payload=True,
            with_vectors=False,
        )

        # 6. Client-Side Reciprocal Rank Fusion (k=60)
        rrf_scores: dict[str, float] = {}
        payload_map: dict[str, dict[str, Any]] = {}

        # Accumulate Dense Ranks: rank starts at 1
        for rank, hit in enumerate(dense_hits, start=1):
            point_id = str(hit.id)
            rrf_scores[point_id] = rrf_scores.get(point_id, 0.0) + (1.0 / (self.rrf_k + rank))
            if point_id not in payload_map and hit.payload:
                payload_map[point_id] = hit.payload

        # Accumulate Sparse Ranks: rank starts at 1
        for rank, hit in enumerate(sparse_hits, start=1):
            point_id = str(hit.id)
            rrf_scores[point_id] = rrf_scores.get(point_id, 0.0) + (1.0 / (self.rrf_k + rank))
            if point_id not in payload_map and hit.payload:
                payload_map[point_id] = hit.payload

        # 7. Sort by fused RRF score descending
        sorted_points = sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)
        top_points = sorted_points[:top_k]

        # 8. Transform into ScoredChunk domain entities
        results: list[ScoredChunk] = []
        for point_id, score in top_points:
            payload = payload_map.get(point_id, {})
            results.append(
                ScoredChunk(
                    chunk_id=str(payload.get("chunk_id", point_id)),
                    content=str(payload.get("content", "")),
                    module_name=str(payload.get("module_name", "Unknown Module")),
                    rrf_score=score,
                    metadata={
                        "difficulty_level": payload.get("difficulty_level"),
                        "prerequisites": payload.get("prerequisites", []),
                        "header": payload.get("header", ""),
                        "tradeoff_latency": payload.get("tradeoff_latency", ""),
                        "tradeoff_memory": payload.get("tradeoff_memory", ""),
                        "tradeoff_complexity": payload.get("tradeoff_complexity", ""),
                    },
                )
            )

        return results
