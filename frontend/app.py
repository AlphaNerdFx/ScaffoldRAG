"""frontend/app.py: Streamlit user interface for ScaffoldRAG."""

import os

import httpx
import streamlit as st

# 1. Environment-Aware Configuration
API_BASE_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")

# 2. Page Configuration
st.set_page_config(
    page_title="ScaffoldRAG | Incremental Portfolio Generator",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 3. Session State Initialization
if "current_roadmap" not in st.session_state:
    st.session_state["current_roadmap"] = None
if "export_markdown" not in st.session_state:
    st.session_state["export_markdown"] = None
if "latency_ms" not in st.session_state:
    st.session_state["latency_ms"] = None
if "is_fallback" not in st.session_state:
    st.session_state["is_fallback"] = False


def reset_state() -> None:
    """Clears cached results when a user starts a new query."""
    st.session_state["current_roadmap"] = None
    st.session_state["export_markdown"] = None
    st.session_state["latency_ms"] = None
    st.session_state["is_fallback"] = False


# 4. Sidebar: User Ingress Parameters
with st.sidebar:
    st.title("⚙️ Parameters")
    st.markdown("Ground your portfolio in production engineering patterns.")

    role_options = [
        "Machine Learning Engineer",
        "Data Engineer",
        "Backend AI Engineer",
    ]
    target_role = st.selectbox("Target Role", options=role_options, index=0)

    domain_interest = st.text_input(
        "Domain Interest",
        value="E-commerce Search & Discovery",
        help="Specify the technical problem domain (e.g., Log Analytics, Financial RAG, Fraud Detection).",
    )

    skills_input = st.text_area(
        "Current Skills (comma-separated)",
        value="Python, FastAPI, SQL, Basic PyTorch",
        help="List technologies you already know so the engine can scaffold missing architectural layers.",
    )

    generate_btn = st.button(
        "🚀 Generate Production Roadmap", type="primary", use_container_width=True
    )

    st.divider()
    st.markdown("### System Telemetry")
    if st.session_state["latency_ms"] is not None:
        st.metric(label="Server Latency", value=f"{st.session_state['latency_ms']:.1f} ms")
    else:
        st.info("Awaiting generation request.")


# 5. Core Execution Engine
if generate_btn:
    reset_state()
    skills_list = [s.strip() for s in skills_input.split(",") if s.strip()]

    if not domain_interest.strip():
        st.error("Domain Interest cannot be empty.")
    elif not skills_list:
        st.error("Please provide at least one current technical skill.")
    else:
        payload = {
            "target_role": target_role,
            "domain_interest": domain_interest,
            "current_skills": skills_list,
        }

        with st.spinner("Synthesizing grounded architecture blueprint..."):
            try:
                # 60s timeout accommodates cold model initialization or retries
                with httpx.Client(base_url=API_BASE_URL, timeout=60.0) as client:
                    resp = client.post("/api/v1/roadmaps", json=payload)

                    if resp.status_code == 200:
                        roadmap_data = resp.json()
                        st.session_state["current_roadmap"] = roadmap_data
                        st.session_state["is_fallback"] = (
                            resp.headers.get("X-Fallback-Applied") == "true"
                        )
                        st.session_state["latency_ms"] = float(
                            resp.headers.get("X-Process-Time-Ms", 0.0)
                        )

                        # Immediately pre-fetch markdown checklist buffer
                        roadmap_id = roadmap_data["roadmap_id"]
                        export_resp = client.get(
                            f"/api/v1/roadmaps/{roadmap_id}/export?format=markdown"
                        )
                        if export_resp.status_code == 200:
                            st.session_state["export_markdown"] = export_resp.text
                        else:
                            st.warning(
                                "Roadmap generated, but failed to compile markdown checklist."
                            )

                    elif resp.status_code == 422:
                        error_detail = resp.json()
                        score = error_detail.get("score", "N/A")
                        st.error(
                            f"❌ **Out of Distribution Query Rejected (Score: {score})**\n\n"
                            f"{error_detail.get('detail', 'Query outside supported computing domains.')}\n\n"
                            f"*Please input technical computing, RAG, or data systems domains.*"
                        )
                    elif resp.status_code == 502:
                        st.error(
                            "⚠️ Upstream inference provider failed schema compliance. Circuit breaker active."
                        )
                    elif resp.status_code == 503:
                        st.error("🚨 Vector database or backend service unavailable.")
                    else:
                        st.error(f"Unexpected error: HTTP {resp.status_code}")

            except httpx.ConnectError:
                st.error(
                    f"🚨 Cannot connect to backend API at `{API_BASE_URL}`. Ensure FastAPI is running."
                )
            except httpx.TimeoutException:
                st.error(
                    "⏱️ Request timed out. Upstream LLM or retrieval took longer than 60 seconds."
                )


# 6. Main Canvas: Rendering Scaffolding Plan
st.header("🏗️ ScaffoldRAG: Architectural Portfolio Plan")

if st.session_state["is_fallback"]:
    st.warning(
        "⚠️ **Notice:** Upstream LLM rate limit or connection failure detected. "
        "The system has served a pre-verified static fallback blueprint via Circuit Breaker."
    )

if st.session_state["current_roadmap"]:
    roadmap = st.session_state["current_roadmap"]

    st.subheader(f"Project: {roadmap['project_title']}")
    st.caption(f"Target Domain: {roadmap['domain']} | Roadmap ID: `{roadmap['roadmap_id']}`")

    # Action Toolbar
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.session_state["export_markdown"]:
            st.download_button(
                label="📥 Download GitHub Checklist (.md)",
                data=st.session_state["export_markdown"],
                file_name=f"roadmap_{roadmap['roadmap_id'][:8]}.md",
                mime="text/markdown",
                use_container_width=True,
            )

    st.divider()

    # 7. Rendering 5 Sequential Stages
    for m in roadmap["milestones"]:
        with st.expander(f"**Stage {m['stage']}: {m['name']}**", expanded=(m["stage"] == 1)):
            st.markdown(f"**💡 Architectural Justification:** {m['why_added']}")

            # Tool Badges
            tools_html = " ".join(
                [
                    f"<span style='background-color:#2e3440;color:#88c0d0;padding:3px 8px;border-radius:4px;font-size:12px;margin-right:5px;'>{t}</span>"
                    for t in m["tools_introduced"]
                ]
            )
            st.markdown(f"**🛠️ Technologies Introduced:** {tools_html}", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

            col_a, col_b = st.columns(2)
            with col_a:
                st.error(f"**⚠️ Explicit Tradeoff:**\n{m['tradeoff']}")
            with col_b:
                st.success(f"**✅ Acceptance Criteria:**\n{m['verification_metric']}")

else:
    if not generate_btn:
        st.info(
            "👈 Configure your engineering profile in the sidebar and click **Generate Production Roadmap** to start."
        )
