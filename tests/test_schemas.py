"""tests/test_schemas.py
Unit tests isolating Pydantic V2 schema validation and negative constraints.
"""

import pytest
from pydantic import ValidationError

from app.schemas.roadmap import Milestone, ProjectRoadmap, RoadmapRequest


def test_roadmap_request_validation():
    """Asserts valid and invalid RoadmapRequest payloads."""
    valid = RoadmapRequest(
        target_role="Machine Learning Engineer",
        domain_interest="Healthcare Search",
        current_skills=["Python", "PyTorch"],
    )
    assert valid.target_role == "Machine Learning Engineer"

    # Too short role
    with pytest.raises(ValidationError):
        RoadmapRequest(target_role="ML", domain_interest="Healthcare", current_skills=["Python"])

    # Empty skills list
    with pytest.raises(ValidationError):
        RoadmapRequest(target_role="MLE", domain_interest="Healthcare", current_skills=[])


@pytest.mark.parametrize(
    "banned_phrase",
    ["None.", "Makes it better", "faster retrieval", "easy to maintain", "FASTER and clean"],
)
def test_milestone_rejects_banned_tradeoff_phrases(banned_phrase: str):
    """Asserts that non-technical or trivial tradeoff statements are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Milestone(
            stage=1,
            name="Baseline Search Engine",
            tools_introduced=["FastAPI", "Qdrant"],
            why_added="Provides the foundational vector store infrastructure.",
            tradeoff=f"This step is {banned_phrase} for the pipeline.",
            verification_metric="Mean Reciprocal Rank > 0.65",
        )
    assert "Tradeoff must document an explicit engineering drawback" in str(exc_info.value)


def test_milestone_accepts_valid_technical_tradeoffs():
    """Asserts that quantifiable technical tradeoffs pass validation."""
    m = Milestone(
        stage=1,
        name="Baseline Search Engine",
        tools_introduced=["FastAPI", "Qdrant"],
        why_added="Provides the foundational vector store infrastructure.",
        tradeoff="Adds 25ms of latency and requires managing persistent container volumes.",
        verification_metric="Mean Reciprocal Rank > 0.65",
    )
    assert "25ms" in m.tradeoff


def test_project_roadmap_enforces_strictly_sequential_stages():
    """Asserts that stages must strictly equal [1, 2, 3, 4, 5]."""

    def make_milestone(stage: int) -> Milestone:
        return Milestone(
            stage=stage,
            name=f"Milestone {stage} Baseline",
            tools_introduced=["Docker"],
            why_added="Gives verifiable baseline functionality.",
            tradeoff="Increases deployment image footprint by 150MB.",
            verification_metric="Integration test suite passes 100%.",
        )

    # Valid sequential milestones
    valid = ProjectRoadmap(
        project_title="Valid Hybrid RAG Roadmap",
        domain="Information Retrieval",
        milestones=[make_milestone(i) for i in range(1, 6)],
    )
    assert len(valid.milestones) == 5

    # Out of order stages [1, 3, 2, 4, 5]
    with pytest.raises(ValidationError) as exc:
        ProjectRoadmap(
            project_title="Invalid Stage Order",
            domain="IR",
            milestones=[
                make_milestone(1),
                make_milestone(3),
                make_milestone(2),
                make_milestone(4),
                make_milestone(5),
            ],
        )
    assert "Milestones must strictly contain stages 1 through 5 in order" in str(exc.value)

    # Insufficient milestones count
    with pytest.raises(ValidationError):
        ProjectRoadmap(
            project_title="Incomplete Pipeline",
            domain="IR",
            milestones=[make_milestone(1), make_milestone(2)],
        )
