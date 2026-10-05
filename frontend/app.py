import os
from urllib.parse import urlparse

import requests
import streamlit as st


st.set_page_config(
    page_title="ClaimCheck AI",
    page_icon="🛡️",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(180deg, #f5f8ff 0%, #ffffff 42%);
    }
    .block-container {
        max-width: 1120px;
        padding-top: 2.5rem;
        padding-bottom: 4rem;
    }
    .eyebrow {
        color: #5267d8;
        font-size: 0.78rem;
        font-weight: 750;
        letter-spacing: 0.14em;
        text-transform: uppercase;
    }
    .hero-title {
        color: #17203b;
        font-size: clamp(2.4rem, 5vw, 4rem);
        font-weight: 780;
        letter-spacing: -0.055em;
        line-height: 1.05;
        margin: 0.4rem 0 0.8rem;
    }
    .hero-copy {
        color: #58627a;
        font-size: 1.08rem;
        max-width: 670px;
        line-height: 1.7;
    }
    .small-label {
        color: #75809a;
        font-size: 0.84rem;
        font-weight: 650;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }
    div.stButton > button[kind="primary"] {
        border-radius: 10px;
        font-weight: 700;
        min-height: 3rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def is_youtube_url(value: str) -> bool:
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return False
    hostname = (parsed.hostname or "").lower()
    return parsed.scheme in {"http", "https"} and (
        hostname == "youtu.be"
        or hostname.endswith(".youtu.be")
        or hostname == "youtube.com"
        or hostname.endswith(".youtube.com")
    )


def submit_audit(api_url: str, video_url: str) -> dict:
    response = requests.post(
        f"{api_url.rstrip('/')}/audit",
        json={"video_url": video_url},
        timeout=(10, 1800),
    )
    if not response.ok:
        try:
            error_response = response.json()
        except ValueError:
            error_response = {}
        details = (
            error_response.get("detail", response.text)
            if isinstance(error_response, dict)
            else response.text
        )
        raise requests.HTTPError(
            f"Backend returned HTTP {response.status_code}: {details}",
            response=response,
        )

    try:
        result = response.json()
    except ValueError as error:
        raise ValueError("The backend returned an invalid JSON response.") from error

    required_fields = {
        "session_id",
        "video_id",
        "status",
        "final_report",
        "compliance_results",
    }
    if not isinstance(result, dict) or not required_fields.issubset(result):
        raise ValueError("The backend response is missing required audit fields.")
    return result


st.markdown('<div class="eyebrow">Video compliance, made clear</div>', unsafe_allow_html=True)
st.markdown('<h1 class="hero-title">Know what your video is saying.</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="hero-copy">Check a YouTube video against your brand and advertising rules. '
    'ClaimCheck AI reviews its transcript and on-screen text, then returns a clear audit report.</p>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### Connection")
    api_url = st.text_input(
        "Backend API URL",
        value=os.getenv("CLAIMCHECK_API_URL", "http://localhost:8000"),
        help="The base URL of the ClaimCheck API. Set CLAIMCHECK_API_URL to change the default.",
    ).strip()
    if api_url:
        try:
            health = requests.get(f"{api_url.rstrip('/')}/health", timeout=3)
            if health.ok:
                st.success("Backend connected")
            else:
                st.warning(f"Backend returned HTTP {health.status_code}")
        except requests.RequestException:
            st.warning("Backend unavailable")
    st.caption("Audits can take several minutes while the video is indexed.")

st.write("")
with st.container(border=True):
    st.markdown("#### Start an audit")
    st.markdown(
        '<span class="small-label">Paste a public YouTube video link</span>',
        unsafe_allow_html=True,
    )
    with st.form("audit_form"):
        video_url = st.text_input(
            "YouTube URL",
            placeholder="https://www.youtube.com/watch?v=...",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button(
            "Run compliance check",
            type="primary",
            use_container_width=True,
        )

if submitted:
    st.session_state.pop("audit_result", None)
    st.session_state.pop("audited_url", None)
    video_url = video_url.strip()
    if not api_url:
        st.error("Enter a backend API URL in the sidebar.")
    elif not is_youtube_url(video_url):
        st.error("Enter a valid YouTube link using https://youtube.com or https://youtu.be.")
    else:
        try:
            with st.spinner("Reviewing the video. This may take several minutes..."):
                st.session_state["audit_result"] = submit_audit(api_url, video_url)
                st.session_state["audited_url"] = video_url
        except requests.Timeout:
            st.error("The audit timed out. Check the backend and try again.")
        except requests.ConnectionError:
            st.error("Could not connect to the backend. Check its URL and make sure it is running.")
        except requests.RequestException as error:
            st.error(f"Audit request failed: {error}")
        except ValueError as error:
            st.error(str(error))

result = st.session_state.get("audit_result")
if result:
    st.write("")
    st.divider()
    st.markdown("## Audit results")

    status = str(result["status"]).upper()
    if status == "PASS":
        st.success("No violations found — this video passed the compliance check.")
    elif status == "FAIL":
        st.error("Potential compliance issues found — review the findings below.")
    else:
        st.warning(f"Audit status: {status}")

    details_col, link_col = st.columns([2, 1])
    with details_col:
        st.markdown("### Summary")
        st.markdown(str(result["final_report"]))
    with link_col:
        st.markdown("### Audit details")
        st.caption(f"**Video ID**  \n{result['video_id']}")
        st.caption(f"**Session ID**  \n{result['session_id']}")
        st.markdown(f"[Open the YouTube video]({st.session_state['audited_url']})")

    issues = result["compliance_results"]
    if not isinstance(issues, list):
        st.error("The backend returned an invalid compliance findings list.")
    elif issues:
        st.markdown("### Findings")
        for index, issue in enumerate(issues, start=1):
            if not isinstance(issue, dict):
                st.warning(f"Finding {index} could not be displayed because its format was invalid.")
                continue
            severity = str(issue.get("severity", "Unspecified")).upper()
            category = issue.get("category", "Compliance finding")
            description = issue.get("description", "No description provided.")
            with st.expander(f"{severity} · {category}", expanded=index == 1):
                st.write(description)
    else:
        st.info("The audit completed without any compliance findings.")

    report = (
        f"# ClaimCheck AI audit\n\n"
        f"- **Status:** {status}\n"
        f"- **Video ID:** {result['video_id']}\n"
        f"- **Session ID:** {result['session_id']}\n"
        f"- **Video:** {st.session_state['audited_url']}\n\n"
        f"## Summary\n\n{result['final_report']}\n\n"
        f"## Findings\n"
    )
    for issue in issues if isinstance(issues, list) else []:
        if isinstance(issue, dict):
            report += (
                f"\n### {issue.get('severity', 'Unspecified')} · "
                f"{issue.get('category', 'Compliance finding')}\n\n"
                f"{issue.get('description', 'No description provided.')}\n"
            )
    st.download_button(
        "Download audit report",
        data=report,
        file_name=f"claimcheck-{result['video_id']}.md",
        mime="text/markdown",
    )
