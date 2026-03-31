"""
Paper Scout Hub — Streamlit Dashboard
CSNL 연구실 논문 추천 파이프라인 UI
"""

import streamlit as st
import json
import os
import glob
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# --- Paths ---
REPO_DIR = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_DIR / "pipeline"
DATA_DIR = REPO_DIR / "data"
OUTPUT_DIR = REPO_DIR / "runs"
LOG_DIR = REPO_DIR / "runs"
CONTEXT_BUNDLE = DATA_DIR / "context-bundle.json"

# --- Load context ---
@st.cache_data
def load_context():
    with open(CONTEXT_BUNDLE) as f:
        return json.load(f)

ctx = load_context()

# --- Page config ---
st.set_page_config(
    page_title="Paper Scout Hub",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Sidebar ---
st.sidebar.title("Paper Scout Hub")
st.sidebar.caption("CSNL 논문 추천 파이프라인")

page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Pipeline", "Outputs", "Members", "Settings"],
    index=0,
)

st.sidebar.divider()
st.sidebar.markdown(f"**Lab:** {ctx['lab_identity']['name']}")
st.sidebar.markdown(f"**Scan window:** {ctx['scan_window']['days']} days")
st.sidebar.markdown(f"**Score threshold:** {ctx['scoring']['threshold']}")

# --- Helper: list output files ---
def list_outputs(pattern="paper-scout-*"):
    files = sorted(OUTPUT_DIR.glob(pattern), key=os.path.getmtime, reverse=True)
    return files

def list_logs():
    files = sorted(LOG_DIR.glob("*.log"), key=os.path.getmtime, reverse=True)
    return files

def run_claude_command(skill_trigger: str):
    """Generate a claude command string for a pipeline phase."""
    return f'claude -p "paper scout {skill_trigger}"'

def get_today():
    return datetime.now().strftime("%Y-%m-%d")

# --- Dashboard ---
if page == "Dashboard":
    st.title("Paper Scout Dashboard")

    col1, col2, col3, col4 = st.columns(4)

    # Stats
    candidates = list(OUTPUT_DIR.glob("paper-scout-candidates-*.md"))
    scores = list(OUTPUT_DIR.glob("paper-scout-scores-*.md"))
    drafts = list(OUTPUT_DIR.glob("paper-scout-draft-*.md"))
    posted = list(OUTPUT_DIR.glob("paper-scout-log-*.md"))

    col1.metric("Scan Results", len(candidates))
    col2.metric("Scored Batches", len(scores))
    col3.metric("Drafts Ready", len(drafts))
    col4.metric("Posted", len(posted))

    st.divider()

    # Recent activity
    st.subheader("Recent Outputs")
    all_outputs = list_outputs()
    if all_outputs:
        for f in all_outputs[:10]:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            phase = "unknown"
            if "candidates" in f.name:
                phase = "Scan"
            elif "scores" in f.name:
                phase = "Score"
            elif "draft" in f.name:
                phase = "Draft/Team"
            elif "review" in f.name:
                phase = "Review"
            elif "log" in f.name:
                phase = "Post"

            with st.expander(f"[{phase}] {f.name} — {mtime.strftime('%Y-%m-%d %H:%M')}"):
                content = f.read_text()
                st.markdown(content[:3000])
                if len(content) > 3000:
                    st.caption(f"... ({len(content)} chars total)")
    else:
        st.info("아직 출력 파일이 없습니다. Pipeline 탭에서 첫 스캔을 실행하세요.")

    # Quick actions
    st.divider()
    st.subheader("Quick Actions")

    qcol1, qcol2 = st.columns(2)
    with qcol1:
        if st.button("Open in Claude Code", use_container_width=True):
            st.code(f"cd {REPO_DIR} && claude", language="bash")
            st.caption("터미널에서 위 명령을 실행하세요")

    with qcol2:
        if st.button("Open Source Repo", use_container_width=True):
            st.code(f"cd {REPO_DIR / 'source' / '..'} && code .", language="bash")

# --- Pipeline ---
elif page == "Pipeline":
    st.title("Pipeline Control")
    st.caption("각 단계를 순서대로 실행하세요. Claude Code 터미널에서 명령을 복사하여 실행합니다.")

    today = get_today()

    # Phase 1: Scan
    st.subheader("Phase 1: Scan (RAG-Anchored Journal Scanning)")
    with st.container(border=True):
        scan_window = st.slider("Scan window (days)", 30, 180, ctx["scan_window"]["days"])
        st.markdown(f"**대상 기간:** {(datetime.now() - timedelta(days=scan_window)).strftime('%Y-%m-%d')} ~ {today}")

        scan_cmd = f"""cd {REPO_DIR} && claude -p "Paper Scout Scan: {scan_window}일 윈도우로 저널 스캔 실행. \\
context-bundle.json의 anchor 기반으로 semantic search. \\
결과를 outputs/paper-scout-candidates-{today}.md에 저장."
"""
        if st.button("Generate Scan Command", key="scan"):
            st.code(scan_cmd, language="bash")
            st.caption("터미널에 붙여넣기하여 실행")

    st.divider()

    # Phase 2: Score
    st.subheader("Phase 2: Score (Value Dimension Scoring)")
    with st.container(border=True):
        candidate_files = sorted(OUTPUT_DIR.glob("paper-scout-candidates-*.md"), reverse=True)
        if candidate_files:
            selected_candidates = st.selectbox(
                "Candidates file",
                candidate_files,
                format_func=lambda x: x.name
            )
            score_cmd = f"""cd {REPO_DIR} && claude -p "Paper Scout Score: \\
{selected_candidates} 파일의 후보 논문들을 5차원(D1-D5)으로 스코어링. \\
멤버별 점수 산출. 결과를 outputs/paper-scout-scores-{today}.md에 저장."
"""
            if st.button("Generate Score Command", key="score"):
                st.code(score_cmd, language="bash")
        else:
            st.warning("먼저 Scan을 실행하세요.")

    st.divider()

    # Phase 3: Team (Draft)
    st.subheader("Phase 3: Team (Multi-Agent Drafting)")
    with st.container(border=True):
        score_files = sorted(OUTPUT_DIR.glob("paper-scout-scores-*.md"), reverse=True)
        if score_files:
            selected_scores = st.selectbox(
                "Scores file",
                score_files,
                format_func=lambda x: x.name
            )
            team_cmd = f"""cd {REPO_DIR} && claude -p "Paper Scout Team: \\
{selected_scores} 기반으로 6-agent 팀 드래프팅 실행. \\
Drafter → Hook/Visual/Accuracy/Member Advocate → Final Editor. \\
결과를 outputs/paper-scout-draft-{today}.md에 저장."
"""
            if st.button("Generate Team Command", key="team"):
                st.code(team_cmd, language="bash")
        else:
            st.warning("먼저 Score를 실행하세요.")

    st.divider()

    # Phase 4: Review (Optional)
    st.subheader("Phase 4: Review (Optional Peer Review)")
    with st.container(border=True):
        draft_files = sorted(OUTPUT_DIR.glob("paper-scout-draft-*.md"), reverse=True)
        if draft_files:
            selected_draft = st.selectbox(
                "Draft file",
                draft_files,
                format_func=lambda x: x.name
            )
            review_cmd = f"""cd {REPO_DIR} && claude -p "Paper Scout Review: \\
{selected_draft}의 드래프트를 Group A/B/C 관점에서 피어 리뷰. \\
결과를 outputs/paper-scout-review-{today}.md에 저장."
"""
            if st.button("Generate Review Command", key="review"):
                st.code(review_cmd, language="bash")
        else:
            st.warning("먼저 Team/Draft를 실행하세요.")

    st.divider()

    # Phase 5: Post
    st.subheader("Phase 5: Post to Slack")
    with st.container(border=True):
        st.markdown(f"**Channel:** #{ctx['slack']['channel']}")

        post_source_files = sorted(
            list(OUTPUT_DIR.glob("paper-scout-draft-*.md")) +
            list(OUTPUT_DIR.glob("paper-scout-review-*.md")),
            key=os.path.getmtime, reverse=True
        )

        if post_source_files:
            selected_post = st.selectbox(
                "Post source",
                post_source_files,
                format_func=lambda x: x.name
            )

            # Preview
            if st.checkbox("Preview content"):
                content = selected_post.read_text()
                st.markdown(content[:5000])

            post_cmd = f"""cd {REPO_DIR} && claude -p "Paper Scout Post: \\
{selected_post}의 최종 포스트를 paper-reading-study 채널에 게시. \\
게시 전 반드시 내 확인을 받을 것. 로그를 outputs/paper-scout-log-{today}.md에 저장."
"""
            if st.button("Generate Post Command", type="primary", key="post"):
                st.code(post_cmd, language="bash")
                st.warning("Slack 게시는 Claude Code에서 확인 후 진행됩니다.")
        else:
            st.warning("먼저 Draft/Review를 실행하세요.")

# --- Outputs ---
elif page == "Outputs":
    st.title("Output Files")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Candidates", "Scores", "Drafts", "Reviews", "Post Logs"])

    def show_files(pattern, tab):
        with tab:
            files = sorted(OUTPUT_DIR.glob(pattern), key=os.path.getmtime, reverse=True)
            if files:
                for f in files:
                    mtime = datetime.fromtimestamp(f.stat().st_mtime)
                    with st.expander(f"{f.name} — {mtime.strftime('%Y-%m-%d %H:%M')}"):
                        content = f.read_text()
                        st.markdown(content)

                        col1, col2 = st.columns([1, 4])
                        with col1:
                            if st.button("Delete", key=f"del_{f.name}"):
                                f.unlink()
                                st.rerun()
            else:
                st.info("파일 없음")

    show_files("paper-scout-candidates-*.md", tab1)
    show_files("paper-scout-scores-*.md", tab2)
    show_files("paper-scout-draft-*.md", tab3)
    show_files("paper-scout-review-*.md", tab4)
    show_files("paper-scout-log-*.md", tab5)

# --- Members ---
elif page == "Members":
    st.title("Lab Members")

    for group_key, group_data in ctx["member_groups"].items():
        st.subheader(group_key.replace("_", " ").title())
        st.caption(group_data["focus"])

        for member in group_data["members"]:
            slack_id = ctx["slack"]["member_ids"].get(member, "N/A")
            with st.expander(f"{member} (Slack: {slack_id})"):
                projects = group_data["projects"].get(member, {})
                for proj_name, proj_desc in projects.items():
                    st.markdown(f"**{proj_name}:** {proj_desc}")

        st.divider()

    st.subheader("Slack Channel")
    st.json(ctx["slack"])

# --- Settings ---
elif page == "Settings":
    st.title("Settings")

    st.subheader("Environment")
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    key_status = "Set" if api_key else "Not set"
    st.markdown(f"**OPENROUTER_API_KEY:** {key_status}")
    if not api_key:
        st.warning("OPENROUTER_API_KEY가 설정되지 않았습니다. ~/.zshrc에 추가하세요:")
        st.code('export OPENROUTER_API_KEY="your_key_here"', language="bash")

    st.divider()

    st.subheader("Paths")
    st.json({
        "hub_dir": str(REPO_DIR),
        "source_dir": str(SOURCE_DIR),
        "data_dir": str(DATA_DIR),
        "output_dir": str(OUTPUT_DIR),
        "context_bundle": str(CONTEXT_BUNDLE),
    })

    st.divider()

    st.subheader("Context Bundle")
    if st.checkbox("Show full context-bundle.json"):
        st.json(ctx)

    st.divider()

    st.subheader("Scoring Config")
    st.json(ctx["scoring"])

    st.subheader("Embedding Config")
    st.json(ctx["embedding"])

    st.subheader("Target Journals")
    for j in ctx["target_journals"]:
        st.markdown(f"- {j}")

    st.divider()

    st.subheader("Cron Schedule")
    cron_status_file = REPO_DIR / "logs" / "cron-status.json"
    if cron_status_file.exists():
        with open(cron_status_file) as f:
            cron_data = json.load(f)
        st.json(cron_data)
    else:
        st.info("자동 스케줄 미설정. Settings에서 launchd 설정을 확인하세요.")

    st.markdown("---")
    st.caption(f"Paper Scout Hub v1.0 | {get_today()}")
