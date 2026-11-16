import os
import glob
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
6. ASSESSMENT HANDOFF: You do NOT administer or grade official tests or quizzes. When the student demonstrates a solid grasp of a chapter—or asks how to earn grades—remind them to check off that chapter in the sidebar and ask their teacher for the official makeup assessment for that chapter.
"""

# --- RESOURCE INGESTION (CACHED) ---
@st.cache_data(show_spinner="Loading Quarter 1 course materials...")
def load_course_materials():
    compiled_text = []

    # 1. Load all PDFs from the 'materials' directory
    pdf_files = sorted(glob.glob("materials/*.pdf"))
    for pdf_path in pdf_files:
        try:
            reader = PdfReader(pdf_path)
            filename = os.path.basename(pdf_path)
            pdf_text = [f"\n--- SOURCE DOCUMENT: {filename} ---"]
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    pdf_text.append(f"[Page {i+1}]\n{text}")
            compiled_text.append("\n".join(pdf_text))
        except Exception as e:
            st.warning(f"Could not read {pdf_path}: {e}")

    # 2. Load any URLs listed in urls.txt
    if os.path.exists("urls.txt"):
        with open("urls.txt", "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        for url in urls:
            try:
                downloaded = trafilatura.fetch_url(url)
                if downloaded:
                    extracted = trafilatura.extract(downloaded)
                    if extracted:
                        compiled_text.append(f"\n--- WEB RESOURCE: {url} ---\n{extracted}")
            except Exception as e:
                st.warning(f"Could not fetch {url}: {e}")

    return "\n\n".join(compiled_text)

# --- INITIALIZE GEMINI CLIENT ---
def get_gemini_client():
    api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        st.error("Missing GEMINI_API_KEY. Please add it to Streamlit Secrets.")
        st.stop()
    return genai.Client(api_key=api_key)

client = get_gemini_client()
reference_context = load_course_materials()

# --- SIDEBAR: PROGRESS & ASSESSMENT HANDOFF ---
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
    st.header("📋 Q1 Catch-Up Plan")
    st.markdown(
        "Review missed notes, ask questions, and work through practice problems step-by-step."
    )

    st.subheader("Chapters to Master")
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
st.caption("Ask questions about Chapters 1–8 or share a practice problem to work through it step-by-step.")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Welcome! I'm here to help you get caught up on Quarter 1 Statistics (Chapters 1–8) at your own pace. "
                "We can review concepts from your class notes, break down vocabulary, or work through practice problems together—I'll give you hints and guide you step-by-step rather than just handing over answers.\n\n"
                "Which chapter or practice problem do you want to start with today?"
            )
        }
    ]

# Display conversation history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Handle student input
if prompt := st.chat_input("Ask a question or share what you have so far on a problem..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Build conversation payload with reference materials injected into system instructions
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
        with st.spinner("Thinking..."):
            try:
                response = client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=gemini_contents,
                    config=types.GenerateContentConfig(
                        system_instruction=full_system_instruction,
                        temperature=0.4,
                    ),
                )
                reply_text = response.text
                st.markdown(reply_text)
                st.session_state.messages.append({"role": "assistant", "content": reply_text})
            except Exception as e:
                st.error(f"Error communicating with Gemini: {e}")
