"""Subsystem 2.1: Out-of-Distribution (OOD) Hard Gate.

Computes maximum cosine similarity between incoming query vectors and
the indexed corpus in Qdrant to reject irrelevant or malicious inputs.
"""

from typing import Any
from fastembed import TextEmbedding
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse
import grpc

from app.core.exceptions import (
    OutOfDistributionError,
    CollectionNotFoundError,
    CorpusEmptyError,
)


class OODGate:
    """Evaluates query relevance against the engineering blueprint corpus."""

    def __init__(
        self,
        client: QdrantClient,
        collection_name: str = "engineering_blueprints",
        model_name: str = "BAAI/bge-small-en-v1.5",
        threshold: float = 0.58,  # Calibrated empirically from probe data
) -> None:
        """Initializes the OOD gate with a Qdrant client and FastEmbed model."""
        self.client = client
        self.collection_name = collection_name
        self.threshold = threshold
        self.dense_model = TextEmbedding(model_name=model_name)

    def evaluate_query(self, query_text: str) -> tuple[bool, float]:
        """Embeds query_text and computes cosine similarity against the nearest point.

        Uses the universally supported `search` RPC to prevent UNIMPLEMENTED errors
        on Qdrant containers < v1.10.0.
        """
        if not query_text or not query_text.strip():
            return False, 0.0

        # FastEmbed's query_embed automatically prepends the BGE search instruction
        dense_generator = self.dense_model.query_embed(query_text)
        query_vector: list[float] = list(dense_generator)[0].tolist()

        try:
            # Universal gRPC Search over named 'dense' vector
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=models.NamedVector(
                    name="dense",
                    vector=query_vector,
                ),
                limit=1,
                with_payload=False,
                with_vectors=False,
            )
        except UnexpectedResponse as exc:
            if exc.status_code == 404:
                raise CollectionNotFoundError(
                    f"Collection '{self.collection_name}' does not exist in Qdrant."
                ) from exc
            raise
        except grpc.RpcError as exc:
            if exc.code() == grpc.StatusCode.NOT_FOUND:
                raise CollectionNotFoundError(
                    f"Collection '{self.collection_name}' does not exist in Qdrant."
                ) from exc
            raise

        if not results:
            raise CorpusEmptyError(
                f"Collection '{self.collection_name}' has no indexed points to evaluate."
            )

        max_similarity: float = float(results[0].score)
        is_valid: bool = max_similarity >= self.threshold

        return is_valid, max_similarity

    def validate_query(self, query_text: str) -> float:
        """Validates query and raises OutOfDistributionError if below threshold."""
        is_valid, max_similarity = self.evaluate_query(query_text)
        if not is_valid:
            raise OutOfDistributionError(
                query=query_text,
                score=max_similarity,
                threshold=self.threshold,
                metadata={"collection": self.collection_name},
            )
        return max_similarity