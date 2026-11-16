import os
import re
import glob
import time
import streamlit as st
from pypdf import PdfReader
import trafilatura
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
5. GROUNDING IN COURSE MATERIALS: Base your explanations, definitions, and notation strictly on the provided Quarter 1 Reference Materials when available.
6. ASSESSMENT HANDOFF: You do NOT administer or grade official tests or quizzes. When the student demonstrates a solid grasp of a chapter—or asks how to earn grades—remind her to check off that chapter in the sidebar and ask her teacher for the official makeup assessment for that chapter.
"""

# --- RESOURCE INGESTION (CACHED PER FILE FOR FAST FILTERING) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@st.cache_data(show_spinner="Indexing Quarter 1 course materials...")
def load_course_materials_dict():
    """Returns a dictionary mapping filename -> extracted text, plus any web resources."""
    docs = {}

    materials_dir = os.path.join(BASE_DIR, "materials")
    pdf_files = sorted(
        glob.glob(os.path.join(materials_dir, "*.pdf"))
        + glob.glob(os.path.join(BASE_DIR, "*.pdf"))
    )

    for pdf_path in pdf_files:
        try:
            reader = PdfReader(pdf_path)
            filename = os.path.basename(pdf_path)
            pdf_text = [f"\n--- SOURCE DOCUMENT: {filename} ---"]
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    pdf_text.append(f"[Page {i+1}]\n{text}")
            docs[filename] = "\n".join(pdf_text)
        except Exception as e:
            st.warning(f"Could not read {pdf_path}: {e}")

    web_text = []
    urls_path = os.path.join(BASE_DIR, "urls.txt")
    if os.path.exists(urls_path):
        with open(urls_path, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        for url in urls:
            try:
                downloaded = trafilatura.fetch_url(url)
                if downloaded:
                    extracted = trafilatura.extract(downloaded)
                    if extracted:
                        web_text.append(f"\n--- WEB RESOURCE: {url} ---\n{extracted}")
            except Exception as e:
                st.warning(f"Could not fetch {url}: {e}")

    return docs, "\n\n".join(web_text)

def get_filtered_context(docs_dict, web_context, selected_chapter):
    """Filters PDFs to only the active chapter (matching 'Chapter 6', 'Ch 6', 'Ch06', etc.) for fast responses."""
    if selected_chapter == "All Chapters (Slower)":
        selected_texts = list(docs_dict.values())
        matched_names = list(docs_dict.keys())
    else:
        match = re.search(r"Chapter\s+(\d+)", selected_chapter, re.IGNORECASE)
        ch_num = match.group(1) if match else ""
        pattern = re.compile(rf"(?:chapter|ch)[\s_-]*0?{ch_num}(?!\d)", re.IGNORECASE)

        matched_names = [fname for fname in docs_dict if pattern.search(fname)]
        if matched_names:
            selected_texts = [docs_dict[fname] for fname in matched_names]
        else:
            selected_texts = list(docs_dict.values())
            matched_names = list(docs_dict.keys())

    combined = "\n\n".join(selected_texts)
    if web_context.strip():
        combined += "\n\n" + web_context
    return combined, matched_names

# --- INITIALIZE GEMINI CLIENT & AUTO-DISCOVER AVAILABLE MODELS ---
def get_gemini_client():
    api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        st.error("Missing GEMINI_API_KEY. Please add it to Streamlit Secrets.")
        st.stop()
    return genai.Client(api_key=api_key)

client = get_gemini_client()

@st.cache_data(ttl=3600)
def get_available_models():
    """Queries the API for valid generateContent models, prioritizing fast Flash models."""
    preferred_order = [
        "gemini-3.8-flash",
        "gemini-3.8-pro",
    ]
    discovered = []
    try:
        for m in client.models.list():
            name = m.name.replace("models/", "")
            methods = getattr(m, "supported_generation_methods", []) or []
            if "generateContent" in methods and "gemini" in name and "embedding" not in name and "tts" not in name:
                discovered.append(name)
    except Exception:
        return preferred_order

    ordered = [m for m in preferred_order if m in discovered]
    for m in discovered:
        if m not in ordered and ("flash" in m or "pro" in m):
            ordered.append(m)

    return ordered if ordered else preferred_order

docs_dict, web_context = load_course_materials_dict()
AVAILABLE_MODELS = get_available_models()

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
        help="Filtering to one chapter loads only those PDFs so the tutor responds much faster."
    )

    reference_context, active_files = get_filtered_context(docs_dict, web_context, active_chapter)
    if active_files:
        st.caption("Active PDFs: " + ", ".join(f"`{f}`" for f in active_files))

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

# Handle student input with streaming response and automatic retry/fallback
if prompt := st.chat_input("Ask a question or share what you have so far on a problem..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    full_system_instruction = SYSTEM_PROMPT
    if reference_context.strip():
        full_system_instruction += (
            "\n\n=== QUARTER 1 REFERENCE MATERIALS ===\n"
            + reference_context
        )

    gemini_contents = []
    for m in st.session_state.messages:
        role = "user" if m["role"] == "user" else "model"
        gemini_contents.append(
            types.Content(
                role=role,
                parts=[types.Part.from_text(text=m["content"])]
            )
        )

    with st.chat_message("assistant"):
        attempt_queue = [AVAILABLE_MODELS[0], AVAILABLE_MODELS[0]] + AVAILABLE_MODELS[1:]

        reply_text = None
        last_error = None

        for attempt_idx, model_name in enumerate(attempt_queue):
            try:
                def response_generator(target_model=model_name):
                    stream = client.models.generate_content_stream(
                        model=target_model,
                        contents=gemini_contents,
                        config=types.GenerateContentConfig(
                            system_instruction=full_system_instruction,
                            temperature=0.4,
                        ),
                    )
                    for chunk in stream:
                        if chunk.text:
                            yield chunk.text

                reply_text = st.write_stream(response_generator())
                break
            except Exception as e:
                last_error = e
                err_str = str(e)
                if any(code in err_str for code in ["503", "429", "404", "UNAVAILABLE", "NOT_FOUND"]):
                    time.sleep(2.0 * (attempt_idx + 1))
                    continue
                else:
                    break

        if reply_text:
            st.session_state.messages.append({"role": "assistant", "content": reply_text})
        else:
            st.warning(
                "The AI tutor is experiencing high traffic right now. Please wait a few seconds and send your message again."
            )
            st.caption(f"Technical details: {last_error}")
