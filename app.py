import os
import re
import glob
import streamlit as st
from google import genai
from google.genai import types

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Q1 Statistics Catch-Up Tutor",
    page_icon="📊",
    layout="centered"
)

# --- PEDAGOGICAL SYSTEM PROMPT ---
SYSTEM_PROMPT = """
You are a patient, grounded, and encouraging high school statistics tutor helping a student catch up on missed Quarter 1 material.

COURSE SCOPE (QUARTER 1):
- Chapter 1: Stats Starts Here
- Chapter 2: Displaying and Describing Categorical Data
- Chapter 3: Displaying and Summarizing Quantitative Data
- Chapter 4: Understanding and Comparing Distributions
- Chapter 5: The Standard Deviation as a Ruler and the Normal Model
- Chapter 6: Sample Surveys
- Chapter 7: Experiments and Observational Studies
- Chapter 8: Designing a Statistical Study

CORE PEDAGOGICAL RULES (STRICT):
1. NEVER GIVE THE FINAL ANSWER: If the student asks for the answer to a practice problem, calculation, or interpretation, do NOT solve it for them. Even if they ask repeatedly, politely decline and offer a smaller next step instead.
2. SCAFFOLDING & HINTS: Break problems down into small, manageable steps. Ask one guiding question at a time to help the student uncover the next step themselves. Use relatable, real-world analogies when explaining abstract concepts (e.g., comparing z-scores across different scales, distinguishing confounding from lurking variables, or clarifying why voluntary response introduces bias).
3. CHECK FOR UNDERSTANDING: Before moving on from a concept, ask the student to explain it in their own words or apply it to a quick, low-stakes check question.
4. TONE & DEMEANOR: Be warm, supportive, and conversational—like a helpful peer or approachable teacher. Avoid over-the-top cheerleading, excessive exclamation points, or robotic praise (do NOT say things like "Amazing job!! You're a superstar!!"). Keep encouragement grounded and authentic (e.g., "You've got the center right—now let's look at how spread affects that comparison.").
5. GROUNDING IN COURSE MATERIALS: Base your explanations, definitions, and notation strictly on the attached Quarter 1 PDF reference materials when available.
6. ASSESSMENT HANDOFF: You do NOT administer or grade official tests or quizzes. When the student demonstrates a solid grasp of a chapter—or asks how to earn grades—remind her to check off that chapter in the sidebar and ask her teacher for the official makeup assessment for that chapter.
"""

# --- INITIALIZE GEMINI CLIENT ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_gemini_client():
    api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        st.error("Missing GEMINI_API_KEY. Please add it to Streamlit Secrets.")
        st.stop()
    return genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})

client = get_gemini_client()

# --- UPLOAD & CACHE PDFS VIA GEMINI FILE API ---
def find_local_pdfs():
    materials_dir = os.path.join(BASE_DIR, "materials")
    return sorted(
        glob.glob(os.path.join(materials_dir, "*.pdf"))
        + glob.glob(os.path.join(BASE_DIR, "*.pdf"))
    )

@st.cache_resource(ttl=3600 * 24, show_spinner="Preparing chapter PDF...")
def get_uploaded_gemini_file(pdf_path):
    """Uploads a single PDF to Gemini's File API and returns the remote file object."""
    return client.files.upload(file=pdf_path)

def get_chapter_file_parts(selected_chapter):
    """Matches active chapter PDFs and returns valid URI Part references."""
    all_pdfs = find_local_pdfs()
    if not all_pdfs:
        return [], []

    if selected_chapter == "All Chapters (Slower)":
        matched_paths = all_pdfs
    else:
        match = re.search(r"Chapter\s+(\d+)", selected_chapter, re.IGNORECASE)
        ch_num = match.group(1) if match else ""
        pattern = re.compile(rf"(?:chapter|ch)[\s_-]*0?{ch_num}(?!\d)", re.IGNORECASE)
        matched_paths = [p for p in all_pdfs if pattern.search(os.path.basename(p))]
        if not matched_paths:
            matched_paths = all_pdfs

    uri_parts = []
    matched_names = []
    for path in matched_paths:
        try:
            remote_file = get_uploaded_gemini_file(path)
            uri_parts.append(
                types.Part.from_uri(file_uri=remote_file.uri, mime_type="application/pdf")
            )
            matched_names.append(os.path.basename(path))
        except Exception as e:
            st.sidebar.warning(f"Could not attach {os.path.basename(path)}: {e}")

    return uri_parts, matched_names

# --- SIDEBAR: CHAPTER FOCUS, PROGRESS & ASSESSMENT HANDOFF ---
CHAPTERS = [
    "Chapter 1 - Stats Starts Here",
    "Chapter 2 - Displaying and Describing Categorical Data",
    "Chapter 3 - Displaying and Summarizing Quantitative Data",
    "Chapter 4 - Understanding and Comparing Distributions",
    "Chapter 5 - The Standard Deviation as a Ruler and the Normal Model",
    "Chapter 6 - Sample Surveys",
    "Chapter 7 - Experiments and Observational Studies",
    "Chapter 8 - Designing a Statistical Study",
]

with st.sidebar:
    st.header("🎯 Current Study Focus")
    active_chapter = st.selectbox(
        "Which chapter are you working on right now?",
        options=CHAPTERS + ["All Chapters (Slower)"],
        index=0,
        help="Select the chapter you are studying so only those PDFs are attached."
    )

    active_file_parts, active_names = get_chapter_file_parts(active_chapter)
    if active_names:
        st.caption("Active PDFs: " + ", ".join(f"`{f}`" for f in active_names))
    else:
        st.caption("No PDFs found in repository.")

    st.divider()
    st.header("📋 Q1 Catch-Up Plan")
    completed_count = 0

    st.caption("**Exploring & Understanding Data**")
    for chapter in CHAPTERS[:5]:
        if st.checkbox(chapter, key=chapter):
            completed_count += 1

    st.caption("**Gathering Data**")
    for chapter in CHAPTERS[5:]:
        if st.checkbox(chapter, key=chapter):
            completed_count += 1

    st.progress(completed_count / len(CHAPTERS))
    st.caption(f"Session Progress: **{completed_count} of {len(CHAPTERS)}** checked")

    st.divider()
    st.subheader("Ready for a Grade?")
    st.info(
        "This tutor is for practice only and cannot enter grades. "
        "Once you feel confident on a chapter:\n\n"
        "1. Check off the chapter above.\n"
        "2. Ask your teacher for the **Makeup Assessment** for that chapter."
    )

    if st.button("Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# --- MAIN CHAT INTERFACE ---
st.title("📊 Q1 Statistics Catch-Up Tutor")
st.caption(f"Currently focused on: **{active_chapter}**")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Welcome! I'm here to help you get caught up on Quarter 1 Statistics (Chapters 1–8) at your own pace. "
                "Use the **Current Study Focus** menu on the left to pick the chapter you're working on, then ask a question or share a practice problem—I'll give you hints and guide you step-by-step rather than just handing over answers.\n\n"
                "What would you like to start with?"
            )
        }
    ]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Handle student input
if prompt := st.chat_input("Ask a question or share what you have so far on a problem..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Attach active chapter PDFs on the first user message using proper URI parts
    gemini_contents = []
    for idx, m in enumerate(st.session_state.messages):
        role = "user" if m["role"] == "user" else "model"
        parts = []
        if idx == 1 and role == "user" and active_file_parts:
            parts.extend(active_file_parts)
        parts.append(types.Part.from_text(text=m["content"]))
        gemini_contents.append(types.Content(role=role, parts=parts))

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=gemini_contents,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.4,
                    ),
                )
                reply_text = response.text
                st.markdown(reply_text)
                st.session_state.messages.append({"role": "assistant", "content": reply_text})
            except Exception as e:
                err_str = str(e)
                if "503" in err_str or "UNAVAILABLE" in err_str:
                    st.warning("Google's Gemini server is momentarily busy (503). Wait 5 seconds and click send again.")
                elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    st.warning("Rate limit reached on the free API tier. Wait ~30 seconds before sending your next message.")
                else:
                    st.error(f"Error communicating with Gemini: {e}")
