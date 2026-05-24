import os
import re
import json
import streamlit as st
import openai

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Code Review Assistant",
    page_icon="🔍",
    layout="wide",
)

# ── prompts ───────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert code reviewer with deep knowledge of security, performance, and best practices. When given a code snippet you must respond with exactly this JSON structure and nothing else:

{
  "language": "<detected language>",
  "positive": "<one specific positive observation about the code>",
  "security": {
    "rating": "<safe|low|medium|high>",
    "note": "<one specific security observation, or 'No security concerns found' if safe>"
  },
  "improvements": [
    {"title": "<short title>", "severity": "<low|medium|high>", "description": "<actionable suggestion>"},
    {"title": "<short title>", "severity": "<low|medium|high>", "description": "<actionable suggestion>"},
    {"title": "<short title>", "severity": "<low|medium|high>", "description": "<actionable suggestion>"}
  ]
}

Rules:
- The "positive" must highlight something genuinely good (e.g. clear naming, good structure, proper use of a pattern).
- Each improvement must be concrete and specific to the code shown.
- Severity reflects impact on correctness, performance, or maintainability.
- Security rating: safe = no issues, low = minor, medium = exploitable in some scenarios, high = critical flaw.
- Do NOT wrap the JSON in markdown fences.
- Return raw JSON only."""

STEPS = [
    ("🔍", "Detecting language and structure…"),
    ("🛡️", "Scanning for security vulnerabilities…"),
    ("⚡", "Evaluating performance and patterns…"),
    ("✍️", "Generating improvement recommendations…"),
]

SEVERITY_COLOR = {"low": "🟡", "medium": "🟠", "high": "🔴"}
SECURITY_COLOR = {"safe": "✅", "low": "🟡", "medium": "🟠", "high": "🔴"}


# ── helpers ───────────────────────────────────────────────────────────────────
def stream_review(code: str, api_key: str):
    client = openai.OpenAI(api_key=api_key)
    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1024,
        stream=True,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": code},
        ],
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def parse_result(raw: str) -> dict:
    raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\n?```$", "", raw, flags=re.MULTILINE)
    return json.loads(raw)


# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Configuration")
    api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        value=os.environ.get("OPENAI_API_KEY", ""),
        help="Your key is never stored.",
    )
    st.divider()
    st.markdown(
        "**How it works:**\n"
        "1. Paste your code below\n"
        "2. Click **Review Code**\n"
        "3. Watch the AI analyse it live\n"
        "4. Get instant, actionable feedback"
    )
    st.divider()
    st.caption("Powered by GPT-4o mini · Built with Streamlit")

# ── header ────────────────────────────────────────────────────────────────────
st.title("🔍 Code Review Assistant")
st.caption("Paste any code snippet and get instant analysis: security check, 3 prioritised improvements, and a positive note.")

# ── sample snippets ───────────────────────────────────────────────────────────
SAMPLES = {
    "— choose a sample —": "",
    "Python: calculate average": (
        "def avg(numbers):\n"
        "    total = 0\n"
        "    for n in numbers:\n"
        "        total = total + n\n"
        "    return total / len(numbers)\n"
    ),
    "JavaScript: fetch data": (
        "function getData(url) {\n"
        "  fetch(url)\n"
        "    .then(response => response.json())\n"
        "    .then(data => {\n"
        "      console.log(data);\n"
        "    });\n"
        "}\n"
    ),
    "Python: find duplicates": (
        "def find_duplicates(lst):\n"
        "    seen = []\n"
        "    duplicates = []\n"
        "    for item in lst:\n"
        "        if item in seen:\n"
        "            duplicates.append(item)\n"
        "        seen.append(item)\n"
        "    return duplicates\n"
    ),
    "Python: SQL query builder": (
        "def get_user(username):\n"
        "    import sqlite3\n"
        "    conn = sqlite3.connect('users.db')\n"
        "    cursor = conn.cursor()\n"
        "    query = f\"SELECT * FROM users WHERE username = '{username}'\"\n"
        "    cursor.execute(query)\n"
        "    return cursor.fetchone()\n"
    ),
}

selected = st.selectbox("Load a sample snippet (optional)", list(SAMPLES.keys()))
default_code = SAMPLES[selected]

code_input = st.text_area(
    "Paste your code here",
    value=default_code,
    height=260,
    placeholder="def hello():\n    print('Hello, world!')",
)

col1, col2 = st.columns([1, 5])
with col1:
    submit = st.button("Review Code", type="primary", use_container_width=True)
with col2:
    if not api_key:
        st.warning("Add your OpenAI API key in the sidebar to continue.")

# ── review logic ──────────────────────────────────────────────────────────────
if submit:
    if not api_key:
        st.error("Please enter your OpenAI API key in the sidebar.")
    elif not code_input.strip():
        st.error("Please paste some code to review.")
    else:
        st.divider()

        # Animated reasoning steps
        steps_container = st.empty()
        completed = []
        import time

        for icon, label in STEPS:
            completed.append(f"**{icon} {label}**")
            steps_container.markdown("\n\n".join(completed))
            time.sleep(0.45)

        steps_container.empty()
        st.success("Analysis complete", icon="✅")

        # Stream the raw response invisibly, then parse
        with st.spinner("Streaming response from GPT-4o mini…"):
            raw_chunks = []
            try:
                for chunk in stream_review(code_input, api_key):
                    raw_chunks.append(chunk)
            except Exception as exc:
                st.error(f"Review failed: {exc}")
                st.stop()

        raw = "".join(raw_chunks)
        try:
            result = parse_result(raw)
        except Exception:
            st.error("Could not parse the model response. Try again.")
            with st.expander("Raw response"):
                st.code(raw)
            st.stop()

        # ── results ───────────────────────────────────────────────────────────
        lang = result.get("language", "unknown")
        st.markdown(f"**Detected language:** `{lang}`")
        st.divider()

        # Security
        sec = result.get("security", {})
        sec_rating = sec.get("rating", "safe")
        sec_icon = SECURITY_COLOR.get(sec_rating, "✅")
        with st.expander(f"{sec_icon} Security — **{sec_rating.upper()}**", expanded=True):
            st.write(sec.get("note", "No security concerns found."))

        st.divider()

        # Positive
        st.subheader("✅ What's good")
        st.success(result.get("positive", ""))

        # Improvements
        st.subheader("🛠 Improvements")
        improvements = result.get("improvements", [])
        for i, item in enumerate(improvements, 1):
            sev = item.get("severity", "low")
            sev_icon = SEVERITY_COLOR.get(sev, "🟡")
            label = f"#{i} — {item.get('title', '')}  {sev_icon} `{sev}`"
            with st.expander(label, expanded=True):
                st.write(item.get("description", ""))
