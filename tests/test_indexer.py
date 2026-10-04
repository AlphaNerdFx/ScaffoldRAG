"""tests/test_indexer.py
Unit tests isolating Subsystem 1: Blueprint Parsing, AST validation, and Qdrant upserts.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from qdrant_client.http.exceptions import UnexpectedResponse

from app.services.indexer import (
    BlueprintChunk,
    CorpusDirectoryNotFoundError,
    IndexerService,
    InvalidBlueprintStructureError,
    QdrantIngestionError,
)

SAMPLE_VALID_MARKDOWN = """# Module: In-Memory Dense Retrieval Baseline

- Difficulty Level: 1
- Prerequisites: Python 3.11, NumPy
- Latency Impact: ~5ms to 12ms retrieval latency
- Memory Footprint: ~1.54 KB per 384-dim vector
- Operational Complexity: Single container process

## Metadata
This section should be ignored by the indexer engine.

## Architecture Pattern
This section describes the dense retrieval baseline utilizing FastEmbed ONNX
runtime for vector calculation and streaming protocol buffers directly to the vector store.
It must exceed fifty characters in total length to satisfy the AST boundary check.

## Explicit Tradeoffs
Using pure dense retrieval provides high semantic recall across conceptual descriptions,
but consistently fails on exact lexical token queries or SKU identifiers.

## Verification Metric
Mean Reciprocal Rank (MRR) must exceed 0.65 across a baseline dataset of 50 technical queries.
"""

SAMPLE_INVALID_MARKDOWN = """# Module: Broken Blueprint

- Difficulty Level: 1
- Prerequisites: None
## Missing tradeoffs and metadata
This document is missing required ADR-02 bulleted attributes.
"""


@pytest.fixture
def mock_qdrant_client():
    client = MagicMock()
    # Simulate get_collections returning an empty collection list
    mock_collections = MagicMock()
    mock_collections.collections = []
    client.get_collections.return_value = mock_collections
    return client


@pytest.fixture
def indexer_service(mock_qdrant_client):
    with (
        patch("app.services.indexer.TextEmbedding"),
        patch("app.services.indexer.SparseTextEmbedding"),
    ):
        service = IndexerService(client=mock_qdrant_client, collection_name="test_blueprints")

        # Mock dense embedding to return a vector per input text in the batch
        mock_dense_vec = MagicMock()
        mock_dense_vec.tolist.return_value = [0.1] * 384
        service.dense_model.embed.side_effect = lambda texts: [mock_dense_vec] * len(texts)

        # Mock sparse embedding to return a sparse vector per input text in the batch
        mock_sparse_vec = MagicMock()
        mock_sparse_vec.indices.tolist.return_value = [10, 20]
        mock_sparse_vec.values.tolist.return_value = [0.5, 0.8]
        service.sparse_model.embed.side_effect = lambda texts: [mock_sparse_vec] * len(texts)

        return service


def test_blueprint_chunk_combined_embed_text():
    """Asserts the semantic anchoring invariant format."""
    chunk = BlueprintChunk(
        chunk_id="test-uuid",
        module_name="Test Module",
        difficulty_level=2,
        prerequisites=["Module 1"],
        header="Architecture Pattern",
        content="Detailed technical pattern description exceeding fifty characters in total length.",
        tradeoff_latency="+10ms",
        tradeoff_memory="10MB",
        tradeoff_complexity="Low",
    )
    expected = (
        "Document: Test Module\n"
        "Section: Architecture Pattern\n"
        "Content: Detailed technical pattern description exceeding fifty characters in total length."
    )
    assert chunk.combined_embed_text == expected


def test_parse_markdown_valid_file(indexer_service, tmp_path: Path):
    """Asserts valid markdown parsing into three distinct blueprint chunks."""
    file_path = tmp_path / "01_test_module.md"
    file_path.write_text(SAMPLE_VALID_MARKDOWN, encoding="utf-8")

    chunks = indexer_service.parse_markdown(file_path)
    assert len(chunks) == 3

    headers = [c.header for c in chunks]
    assert "Architecture Pattern" in headers
    assert "Explicit Tradeoffs" in headers
    assert "Verification Metric" in headers
    assert "Metadata" not in headers  # Excluded

    chunk = chunks[0]
    assert chunk.module_name == "In-Memory Dense Retrieval Baseline"
    assert chunk.difficulty_level == 1
    assert chunk.prerequisites == ["Python 3.11", "NumPy"]
    assert chunk.tradeoff_latency == "~5ms to 12ms retrieval latency"
    assert len(chunk.chunk_id) == 36  # Valid UUID string format


def test_parse_markdown_missing_file_raises(indexer_service, tmp_path: Path):
    """Asserts FileNotFoundError on missing file."""
    non_existent = tmp_path / "does_not_exist.md"
    with pytest.raises(FileNotFoundError):
        indexer_service.parse_markdown(non_existent)


def test_parse_markdown_invalid_structure_raises(indexer_service, tmp_path: Path):
    """Asserts InvalidBlueprintStructureError when metadata bullets are omitted."""
    file_path = tmp_path / "broken.md"
    file_path.write_text(SAMPLE_INVALID_MARKDOWN, encoding="utf-8")

    with pytest.raises(InvalidBlueprintStructureError):
        indexer_service.parse_markdown(file_path)


def test_parse_markdown_skips_short_sections(indexer_service, tmp_path: Path):
    """Asserts that sections shorter than 50 characters are dropped."""
    content = SAMPLE_VALID_MARKDOWN + "\n## Short Section\nToo short.\n"
    file_path = tmp_path / "short_section.md"
    file_path.write_text(content, encoding="utf-8")

    chunks = indexer_service.parse_markdown(file_path)
    assert len(chunks) == 3
    assert "Short Section" not in [c.header for c in chunks]


def test_create_collection_provisions_dense_and_sparse(indexer_service, mock_qdrant_client):
    """Asserts collection provisioning and payload index creation."""
    indexer_service.create_collection_if_not_exists()

    mock_qdrant_client.create_collection.assert_called_once()
    assert mock_qdrant_client.create_payload_index.call_count == 2


def test_create_collection_handles_qdrant_error(indexer_service, mock_qdrant_client):
    """Asserts QdrantIngestionError when collection provisioning fails."""
    mock_qdrant_client.get_collections.side_effect = RuntimeError("Socket closed")

    with pytest.raises(QdrantIngestionError):
        indexer_service.create_collection_if_not_exists()


def test_index_all_nonexistent_directory_raises(indexer_service, tmp_path: Path):
    """Asserts CorpusDirectoryNotFoundError when blueprint directory is missing."""
    invalid_dir = tmp_path / "non_existent_dir"
    with pytest.raises(CorpusDirectoryNotFoundError):
        indexer_service.index_all(invalid_dir)


def test_index_all_empty_directory_returns_zero(indexer_service, tmp_path: Path):
    """Asserts zero points indexed if directory has no markdown files."""
    empty_dir = tmp_path / "empty_corpus"
    empty_dir.mkdir()

    indexed_count = indexer_service.index_all(empty_dir)
    assert indexed_count == 0


def test_index_all_successful_batch_upsert(indexer_service, mock_qdrant_client, tmp_path: Path):
    """Asserts full ingestion workflow across batch chunks."""
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    (corpus_dir / "01_test.md").write_text(SAMPLE_VALID_MARKDOWN, encoding="utf-8")

    indexed_count = indexer_service.index_all(corpus_dir, batch_size=2)
    assert indexed_count == 3
    assert mock_qdrant_client.upsert.called


def test_index_all_upsert_failure_raises_ingestion_error(
    indexer_service, mock_qdrant_client, tmp_path: Path
):
    """Asserts QdrantIngestionError when batch upsert fails."""
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    (corpus_dir / "01_test.md").write_text(SAMPLE_VALID_MARKDOWN, encoding="utf-8")

    mock_qdrant_client.upsert.side_effect = UnexpectedResponse(
        500, "Internal Server Error", b"", None
    )

    with pytest.raises(QdrantIngestionError):
        indexer_service.index_all(corpus_dir)
