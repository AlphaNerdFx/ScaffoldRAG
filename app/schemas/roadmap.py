"""app/schemas/roadmap.py: Strongly typed data contracts for roadmap generation."""

import uuid

from pydantic import BaseModel, Field, field_validator


class RoadmapRequest(BaseModel):
    """Ingress request contract for roadmap generation."""

    target_role: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Target engineering role (e.g., Machine Learning Engineer)",
    )
    domain_interest: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Target domain or system focus (e.g., E-commerce Search & Discovery)",
    )
    current_skills: list[str] = Field(
        ...,
        min_length=1,
        max_length=15,
        description="List of current technologies or skills known by the student",
    )


class Milestone(BaseModel):
    """Individual incremental engineering stage in the roadmap."""

    stage: int = Field(
        ...,
        ge=1,
        le=5,
        description="Sequential stage index from 1 to 5",
    )
    name: str = Field(
        ...,
        min_length=5,
        max_length=100,
        description="Milestone title describing the architectural advancement",
    )
    tools_introduced: list[str] = Field(
        ...,
        min_length=1,
        description="List of concrete tools, libraries, or frameworks introduced in this stage",
    )
    why_added: str = Field(
        ...,
        min_length=20,
        description="Architectural justification for adding these specific tools",
    )
    tradeoff: str = Field(
        ...,
        min_length=15,
        description="Explicit architectural drawback or complexity introduced",
    )
    verification_metric: str = Field(
        ...,
        min_length=15,
        description="Measurable engineering condition required to consider this stage done",
    )

    @field_validator("tradeoff")
    @classmethod
    def validate_tradeoff(cls, v: str) -> str:
        """Enforces that the tradeoff documents a concrete architectural cost."""
        banned_phrases = ["none", "makes it better", "faster", "easy"]
        normalized = v.lower()
        for phrase in banned_phrases:
            if phrase in normalized:
                raise ValueError(
                    f"Tradeoff must document an explicit engineering drawback. "
                    f"Found prohibited non-technical phrase: '{phrase}'."
                )
        return v


class ProjectRoadmap(BaseModel):
    """Final 5-stage scaffolding plan generated for the student."""

    roadmap_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Deterministic or generated UUIDv4 for this roadmap",
    )
    project_title: str = Field(
        ...,
        min_length=5,
        max_length=100,
        description="Title of the architecture project",
    )
    domain: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Target computing domain",
    )
    milestones: list[Milestone] = Field(
        ...,
        min_length=5,
        max_length=5,
        description="Exactly 5 sequential engineering milestones",
    )

    @field_validator("milestones")
    @classmethod
    def validate_sequential_stages(cls, v: list[Milestone]) -> list[Milestone]:
        """Asserts that milestones form a strict sequential 1-through-5 pipeline."""
        stages = [m.stage for m in v]
        expected_stages = [1, 2, 3, 4, 5]
        if stages != expected_stages:
            raise ValueError(
                f"Milestones must strictly contain stages 1 through 5 in order. "
                f"Received stages: {stages}."
            )
        return v
