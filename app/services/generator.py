"""app/services/generator.py: Structured inference engine wrapping Groq via Instructor."""

from typing import Any

import instructor
from groq import Groq

from app.core.config import get_settings
from app.schemas.roadmap import ProjectRoadmap, RoadmapRequest
from app.services.search.hybrid_search import ScoredChunk


class RoadmapGenerator:
    """Generates schema-enforced roadmaps grounded in retrieved architecture blueprints."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        temperature: float = 0.2,
    ) -> None:
        """Initializes Instructor-patched Groq client."""
        settings = get_settings()
        resolved_key = api_key or (
            settings.GROQ_API_KEY.get_secret_value()
            if hasattr(settings.GROQ_API_KEY, "get_secret_value")
            else str(settings.GROQ_API_KEY)
        )

        if not resolved_key or resolved_key == "mock-or-valid-groq-key":
            self._raw_client = None
            self.client = None
        else:
            self._raw_client = Groq(api_key=resolved_key)
            # Switch to Mode.JSON for native Groq JSON mode support
            self.client = instructor.from_groq(self._raw_client, mode=instructor.Mode.JSON)

        self.model_name = model_name or settings.INFERENCE_MODEL
        self.temperature = temperature

        # Wire directly to settings.INFERENCE_MODEL
        self.model_name = model_name or settings.INFERENCE_MODEL
        self.temperature = temperature

    def _build_system_prompt(self) -> str:
        """Assembles the grounding prompt with explicit negative constraint rules."""
        return (
            "You are a Principal Solutions Architect. Using ONLY the architecture patterns "
            "provided in the context below, create an incremental 5-stage scaffolding plan for "
            "the user's project idea. You must output data that strictly validates against the "
            "provided JSON schema.\n\n"
            "CRITICAL ARCHITECTURAL CONSTRAINTS:\n"
            "1. You must output exactly 5 sequential milestones numbered stage 1 through 5.\n"
            "2. Each milestone must introduce concrete tools and patterns from the provided context.\n"
            "3. The 'tradeoff' field MUST document an explicit engineering drawback, bottleneck, "
            "or operational cost (e.g., latency penalty, RAM footprint, infrastructure complexity).\n"
            "4. NEVER use the words 'none', 'makes it better', 'faster', or 'easy' in the 'tradeoff' field. "
            "Doing so will fail schema validation.\n"
            "5. The 'verification_metric' must be a measurable engineering acceptance condition "
            "(e.g., target latency in ms, test coverage %, or retrieval benchmark score).\n"
            "6. BREVITY CONSTRAINT: Keep 'why_added', 'tradeoff', and 'verification_metric' concise, "
            "dense, and bounded to 1-2 punchy sentences each. Eliminate conversational preamble."
        )

    def _format_context(self, context_chunks: list[ScoredChunk]) -> str:
        """Formats the retrieved chunks into structured context blocks."""
        formatted_blocks: list[str] = []
        for i, chunk in enumerate(context_chunks, 1):
            metadata: dict[str, Any] = getattr(chunk, "metadata", {}) or {}
            header = metadata.get("header", "Architecture Pattern")
            lat = metadata.get("tradeoff_latency", "Not specified")
            mem = metadata.get("tradeoff_memory", "Not specified")
            comp = metadata.get("tradeoff_complexity", "Not specified")

            block = (
                f"### Pattern {i}: {chunk.module_name} — Section: {header}\n"
                f"Content: {chunk.content}\n"
                f"Documented Tradeoffs:\n"
                f"  - Latency: {lat}\n"
                f"  - Memory: {mem}\n"
                f"  - Complexity: {comp}"
            )
            formatted_blocks.append(block)

        return "\n\n".join(formatted_blocks)

    def _build_user_prompt(self, request: RoadmapRequest, context_chunks: list[ScoredChunk]) -> str:
        """Compiles user parameters and contextual blueprints into the prompt."""
        formatted_context = self._format_context(context_chunks)
        skills_str = ", ".join(request.current_skills)
        return (
            f"Candidate Target Role: {request.target_role}\n"
            f"Candidate Target Domain: {request.domain_interest}\n"
            f"Candidate Current Skills: {skills_str}\n\n"
            f"--- REFERENCE BLUEPRINT CONTEXT ---\n"
            f"{formatted_context}\n"
            f"--- END REFERENCE BLUEPRINT CONTEXT ---\n\n"
            f"Synthesize these reference patterns into a 5-stage scaffolding plan for this candidate. "
            f"Ensure every milestone builds incrementally on previous stages."
        )

    def generate(
        self,
        request: RoadmapRequest,
        context_chunks: list[ScoredChunk],
    ) -> ProjectRoadmap:
        """Invokes Groq with Instructor schema enforcement and up to 2 retries."""
        if not context_chunks:
            raise ValueError(
                "Context chunks cannot be empty. RAG generation requires retrieved context."
            )

        if self.client is None:
            raise RuntimeError(
                "RoadmapGenerator client is uninitialized. A valid GROQ_API_KEY is required."
            )

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(request, context_chunks)

        # Instructor handles the Pydantic validation and automatic retry loop
        roadmap: ProjectRoadmap = self.client.chat.completions.create(
            model=self.model_name,
            response_model=ProjectRoadmap,
            max_retries=2,
            temperature=self.temperature,
            max_tokens=4096,  # <--- EXPLICIT TOKEN BUDGET (Prevents IncompleteOutputException)
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        return roadmap
