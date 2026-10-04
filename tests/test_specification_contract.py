"""tests/test_specification_contract.py: Contract tests enforcing SPEC_V1 Section 3.2."""

import pytest
from pydantic import ValidationError

from app.schemas.roadmap import Milestone, ProjectRoadmap


def test_milestone_tradeoff_enforcement() -> None:
    """Asserts that the system rejects trivial, non-technical tradeoff strings."""
    with pytest.raises(ValueError):
        Milestone(
            stage=1,
            name="Baseline Search",
            tools_introduced=["FastAPI"],
            why_added="Initial implementation for testing purposes.",
            tradeoff="None. It makes the system better and faster.",  # MUST FAIL
            verification_metric="Latency < 50ms across 100 queries",
        )


def test_roadmap_stage_count_invariant() -> None:
    """Asserts that exactly 5 milestones are required by the schema."""
    with pytest.raises(ValueError):
        ProjectRoadmap(
            project_title="Invalid Pipeline",
            domain="E-commerce",
            milestones=[],  # Empty milestones MUST FAIL
        )


def test_valid_milestone_instantiation() -> None:
    """Asserts that a technically valid milestone passes validation."""
    m = Milestone(
        stage=1,
        name="Naive Dense Retrieval Baseline",
        tools_introduced=["FastAPI", "Qdrant", "Sentence-Transformers"],
        why_added="Establishes a baseline semantic search pipeline with low complexity.",
        tradeoff="High semantic recall, but fails on exact keyword or part-number queries.",
        verification_metric="MRR > 0.60 on a 50-query golden dataset.",
    )
    assert m.stage == 1
    assert len(m.tools_introduced) == 3


def test_sequential_stage_invariant() -> None:
    """Asserts that out-of-order or duplicate stages are rejected."""
    valid_milestone_template = {
        "tools_introduced": ["Docker", "Qdrant"],
        "why_added": "Provides persistent vector store infrastructure.",
        "tradeoff": "Increases memory consumption by 250MB permanently.",
        "verification_metric": "Docker container boots and passes healthcheck.",
    }

    # Out of order stages [1, 2, 4, 3, 5]
    milestones = [
        Milestone(stage=s, name=f"Stage {s} Implementation", **valid_milestone_template)
        for s in [1, 2, 4, 3, 5]
    ]

    with pytest.raises(ValidationError) as exc_info:
        ProjectRoadmap(
            project_title="Valid Architecture Blueprint",
            domain="Medical Search",
            milestones=milestones,
        )
    assert "Milestones must strictly contain stages 1 through 5 in order" in str(exc_info.value)


def test_banned_tradeoff_terms_isolated() -> None:
    """Asserts that all variations of banned words trigger validation failure."""
    banned_words = ["none", "makes it better", "faster", "easy"]
    for word in banned_words:
        with pytest.raises(ValidationError):
            Milestone(
                stage=2,
                name="Caching Layer Integration",
                tools_introduced=["Redis"],
                why_added="Caches repeated dense retrieval candidate vectors.",
                tradeoff=f"This tool is {word} to maintain in production.",
                verification_metric="P95 latency decreases by 30ms.",
            )
