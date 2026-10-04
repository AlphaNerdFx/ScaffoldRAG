"""tests/test_generator.py: Unit tests for RoadmapGenerator with mocked transport."""

from unittest.mock import MagicMock

import pytest

from app.schemas.roadmap import Milestone, ProjectRoadmap, RoadmapRequest
from app.services.generator import RoadmapGenerator
from app.services.search.hybrid_search import ScoredChunk


@pytest.fixture
def sample_chunks() -> list[ScoredChunk]:
    """Provides representative ScoredChunk objects."""
    return [
        ScoredChunk(
            chunk_id="chunk-1",
            content="Use BAAI/bge-small-en-v1.5 dense vector embeddings to establish a baseline.",
            module_name="In-Memory Dense Retrieval",
            rrf_score=0.033,
            metadata={
                "header": "Architecture Pattern",
                "tradeoff_latency": "+10ms to +25ms per vector search",
                "tradeoff_memory": "Requires 1.54 KB per 384-dim vector",
                "tradeoff_complexity": "Fails on exact alphanumeric keyword queries",
            },
        ),
        ScoredChunk(
            chunk_id="chunk-2",
            content="Implement sparse BM25 indexing in parallel with dense vector embeddings.",
            module_name="Sparse BM25 Indexing",
            rrf_score=0.031,
            metadata={
                "header": "Architecture Pattern",
                "tradeoff_latency": "+5ms inverted index traversal",
                "tradeoff_memory": "Sparse index memory overhead scales with vocabulary",
                "tradeoff_complexity": "Requires managing dual storage spaces",
            },
        ),
    ]


@pytest.fixture
def sample_request() -> RoadmapRequest:
    return RoadmapRequest(
        target_role="Machine Learning Engineer",
        domain_interest="E-commerce Hybrid Search",
        current_skills=["Python", "FastAPI"],
    )


def test_generator_rejects_empty_context(sample_request: RoadmapRequest) -> None:
    """Asserts generator throws ValueError when context list is empty."""
    generator = RoadmapGenerator(api_key="gsk_mock_test_key")
    with pytest.raises(ValueError, match="Context chunks cannot be empty"):
        generator.generate(request=sample_request, context_chunks=[])


def test_generator_prompt_assembly(
    sample_request: RoadmapRequest, sample_chunks: list[ScoredChunk]
) -> None:
    """Asserts that system and user prompts contain essential grounding and negative constraints."""
    generator = RoadmapGenerator(api_key="gsk_mock_test_key")
    system_prompt = generator._build_system_prompt()
    user_prompt = generator._build_user_prompt(sample_request, sample_chunks)

    # Assert negative constraint injection
    assert "CRITICAL ARCHITECTURAL CONSTRAINTS" in system_prompt
    assert "NEVER use the words 'none'" in system_prompt

    # Assert user context injection
    assert "Machine Learning Engineer" in user_prompt
    assert "E-commerce Hybrid Search" in user_prompt
    assert "In-Memory Dense Retrieval" in user_prompt
    assert "Sparse BM25 Indexing" in user_prompt


def test_generator_successful_mocked_invocation(
    sample_request: RoadmapRequest, sample_chunks: list[ScoredChunk]
) -> None:
    """Asserts generator forwards arguments and returns validated ProjectRoadmap."""
    generator = RoadmapGenerator(api_key="gsk_mock_test_key")

    mock_roadmap = ProjectRoadmap(
        project_title="E-commerce Search Scaffolding Plan",
        domain="E-commerce Hybrid Search",
        milestones=[
            Milestone(
                stage=i,
                name=f"Milestone Stage {i}",
                tools_introduced=["FastAPI", "Qdrant"],
                why_added="Required for stage baseline architecture.",
                tradeoff="Increases P95 retrieval latency by 15ms.",
                verification_metric="Latency bounded under 50ms across 100 queries.",
            )
            for i in range(1, 6)
        ],
    )

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_roadmap
    generator.client = mock_client

    result = generator.generate(sample_request, sample_chunks)

    assert result.project_title == "E-commerce Search Scaffolding Plan"
    assert len(result.milestones) == 5
    assert mock_client.chat.completions.create.called
    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["response_model"] == ProjectRoadmap
    assert kwargs["max_retries"] == 2
