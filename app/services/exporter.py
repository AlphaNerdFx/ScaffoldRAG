"""app/services/exporter.py: Serializes ProjectRoadmap instances to Markdown."""

from app.schemas.roadmap import ProjectRoadmap


def roadmap_to_markdown(roadmap: ProjectRoadmap) -> str:
    """Converts a ProjectRoadmap into an actionable GitHub Markdown checklist."""
    lines: list[str] = [
        f"# {roadmap.project_title}",
        f"> **Domain:** {roadmap.domain}  ",
        f"> **Roadmap ID:** `{roadmap.roadmap_id}`",
        "",
        "---",
        "",
    ]

    for m in roadmap.milestones:
        tools = ", ".join(f"`{t}`" for t in m.tools_introduced)
        lines.extend([
            f"## Stage {m.stage}: {m.name}",
            f"- [ ] **Verification Metric:** {m.verification_metric}",
            f"- **Architectural Rationale:** {m.why_added}",
            f"- **Technologies Introduced:** {tools}",
            f"- **Documented Tradeoff:** {m.tradeoff}",
            "",
        ])

    return "\n".join(lines)