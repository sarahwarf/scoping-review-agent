"""
Scoping Review Agent — L2 Writing
Streamlit web app
"""

import json
import re
import time

import anthropic
import gspread
import pandas as pd
import requests
import streamlit as st
from google.oauth2.service_account import Credentials

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Scoping Review Agent",
    page_icon="📄",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Default tag lists
# ---------------------------------------------------------------------------
DEFAULT_TOPIC_TAGS = [
    "L2 writing",
    "ESL writing",
    "EFL writing",
    "academic writing",
    "writing instruction",
    "writing feedback",
    "written corrective feedback (WCF)",
    "peer feedback",
    "teacher feedback",
    "automated writing evaluation (AWE)",
    "AI writing tools",
    "ChatGPT / LLMs",
    "grammar / language accuracy",
    "genre-based writing",
    "process writing",
    "writing development",
    "writing anxiety / affect",
    "writer identity",
    "translanguaging",
    "multilingual writers",
    "contrastive rhetoric",
    "corpus-based writing",
    "writing assessment",
    "revision / editing",
    "writing in the disciplines",
    "text analysis / NLP",
]

DEFAULT_POPULATION_TAGS = [
    "undergraduate students",
    "graduate students",
    "K-12 learners",
    "adult / community learners",
    "ESL learners (English-dominant context)",
    "EFL learners (foreign-language context)",
    "heritage language learners",
    "international students",
    "teachers / instructors",
]

CRESWELL_DESIGNS = [
    # Quantitative
    "Experimental", "Quasi-experimental", "Survey", "Descriptive (quantitative)", "Correlational",
    # Qualitative
    "Case study", "Ethnography", "Narrative inquiry", "Phenomenological", "Grounded theory",
    # Mixed
    "Convergent mixed methods", "Explanatory sequential mixed methods",
    "Exploratory sequential mixed methods", "Complex/embedded mixed methods",
    # Other
    "Meta-analysis", "Systematic review", "Literature review",
    "Corpus analysis", "Conceptual/theoretical (no data)",
]

# ---------------------------------------------------------------------------
# Google Sheets connection
# ---------------------------------------------------------------------------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

@st.cache_resource
def get_gspread_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    return gspread.authorize(creds)


def load_sheet(url: str) -> tuple[pd.DataFrame, gspread.Spreadsheet]:
    gc = get_gspread_client()
    sh = gc.open_by_url(url)
    ws = sh.sheet1
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    df.columns = df.columns.str.strip().str.lower()
    return df, sh


# ---------------------------------------------------------------------------
# OpenAlex
# ---------------------------------------------------------------------------
OPENALEX_HEADERS = {"User-Agent": "ScopingReviewAgent/1.0"}

def lookup_openalex(doi: str, title: str) -> dict:
    try:
        if doi:
            r = requests.get(
                "https://api.openalex.org/works",
                headers=OPENALEX_HEADERS,
                params={"filter": f"doi:{doi}"},
                timeout=10,
            )
            if r.status_code == 200:
                works = r.json().get("results", [])
                if works:
                    return _parse_openalex(works[0])
        if title:
            r = requests.get(
                "https://api.openalex.org/works",
                headers=OPENALEX_HEADERS,
                params={"search": title, "per-page": 1},
                timeout=10,
            )
            if r.status_code == 200:
                works = r.json().get("results", [])
                if works:
                    return _parse_openalex(works[0])
    except Exception as e:
        return {"openalex_error": str(e)}
    return {}


def _parse_openalex(work: dict) -> dict:
    source = (work.get("primary_location") or {}).get("source") or {}
    oa = work.get("open_access") or {}
    return {
        "openalex_id": work.get("id", ""),
        "verified_journal": source.get("display_name", ""),
        "verified_issn": source.get("issn_l", ""),
        "source_type": source.get("type", ""),
        "work_type": work.get("type", ""),
        "cited_by_count": work.get("cited_by_count", ""),
        "is_open_access": oa.get("is_oa", None),
        "oa_status": oa.get("oa_status", ""),
        "openalex_peer_reviewed": source.get("type") == "journal",
    }


# ---------------------------------------------------------------------------
# Claude analysis
# ---------------------------------------------------------------------------
def build_system_prompt(modules: dict, topic_tags: list, population_tags: list,
                        flag_conditions: list = None) -> str:
    fields = {}
    fields["authors"] = 'parsed from citation, semicolon-separated, e.g. "Lee, J.; Park, S."'
    fields["year"] = "integer"
    fields["journal_or_source"] = "journal name or book/conference name"
    fields["doi"] = 'DOI string if present, else ""'

    if modules["openalex"]:
        fields["peer_reviewed"] = "true/false — use OpenAlex data if provided, else infer from citation"

    if modules["article_type"]:
        fields["article_type"] = "one of: Empirical-Quantitative | Empirical-Qualitative | Empirical-Mixed | Review/Synthesis | Conceptual/Theoretical | Practitioner/Commentary"

    if modules["research_design"]:
        fields["research_design"] = "Creswell design term from the list below; empty string if not empirical or unclear"
        fields["research_design_confidence"] = "one of: confirmed | inferred | unclear"

    if modules["sample_size"]:
        fields["sample_size"] = 'who and how many, e.g. "42 Chinese EFL undergraduates"; empty string if not applicable'

    if modules["topic_tags"]:
        fields["topic_tags"] = "array — subset of provided topic tags that apply; add an unlisted tag only if clearly needed"

    if modules["population_tags"]:
        fields["population_tags"] = "array — subset of provided population tags that apply; use exact labels from the list"
        fields["suggested_population_tags"] = 'array — populations clearly present in this abstract that are NOT in your list; empty array [] if none'

    if modules["setting"]:
        fields["setting"] = 'country or region if identifiable, else ""'

    if modules["relevance"]:
        fields["relevance_score"] = "integer 1–5: 5 = core L2 writing paper; 3 = relevant but peripheral; 1 = unlikely to include"
        fields["relevance_rationale"] = "one sentence explaining the score"

    fields["flag_full_text"] = "true if any flag condition below is met, else false"
    fields["flag_reason"] = 'which flag condition was triggered, else ""'

    json_template = json.dumps(
        {k: f"<{v}>" for k, v in fields.items()}, indent=2
    )

    prompt = f"You are a systematic review assistant specializing in second language (L2) writing research.\n\n"
    prompt += f"Return ONLY a valid JSON object with these fields:\n{json_template}\n\n"

    if modules["research_design"]:
        prompt += "Creswell research design options (use exact labels):\n"
        prompt += "\n".join(f"- {d}" for d in CRESWELL_DESIGNS) + "\n\n"

    if modules["topic_tags"]:
        prompt += "Topic tag options (use exact labels):\n"
        prompt += "\n".join(f"- {t}" for t in topic_tags) + "\n\n"

    if modules["population_tags"]:
        if population_tags:
            prompt += "Population tag options (use exact labels):\n"
            prompt += "\n".join(f"- {p}" for p in population_tags) + "\n\n"
            prompt += ("For suggested_population_tags: if the abstract clearly describes a population "
                       "not covered by any tag above, name it concisely (e.g. 'nursing students', "
                       "'refugee learners'). Do not suggest near-duplicates of existing tags.\n\n")
        else:
            prompt += ("No population tags have been defined yet. For population_tags return []. "
                       "For suggested_population_tags: list every distinct population group you can "
                       "identify from the abstract, named concisely.\n\n")

    if flag_conditions:
        prompt += "Flag conditions — set flag_full_text to true and state the condition in flag_reason if ANY of these apply:\n"
        prompt += "\n".join(f"- {c}" for c in flag_conditions) + "\n\n"
    else:
        prompt += ("Flag conditions — set flag_full_text to true only if the abstract is genuinely "
                   "too ambiguous to classify on any field above. State the reason in flag_reason.\n\n")

    prompt += "Return ONLY valid JSON. No commentary, no markdown fences."
    return prompt


def analyze_paper(client, system_prompt: str, title: str, abstract: str,
                  citation: str, openalex: dict) -> dict:
    oa_lines = []
    if openalex.get("verified_journal"):
        oa_lines.append(f"Verified journal: {openalex['verified_journal']}")
    if openalex.get("work_type"):
        oa_lines.append(f"Work type: {openalex['work_type']}")
    if openalex.get("source_type"):
        oa_lines.append(f"Source type: {openalex['source_type']}")
    if openalex.get("cited_by_count") != "":
        oa_lines.append(f"Cited by: {openalex['cited_by_count']}")

    oa_block = ("\n\nVerified metadata from OpenAlex:\n" + "\n".join(oa_lines)) if oa_lines \
               else "\n\nOpenAlex: no record found."

    content = f"Title: {title}\n\nAbstract: {abstract}\n\nAPA Citation: {citation}{oa_block}"

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": content}],
    )
    raw = response.content[0].text.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    return json.loads(raw)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
st.title("📄 Scoping Review Agent")
st.caption("L2 Writing — powered by Claude + OpenAlex")

# ── Step 1: Connect Google Sheet ──────────────────────────────────────────
st.header("Step 1 — Connect your Google Sheet")
st.markdown(
    "The sheet must have columns named **title**, **abstract**, and **citation**. "
    "Share the sheet with your service account email before pasting the URL."
)

sheet_url = st.text_input("Google Sheet URL", placeholder="https://docs.google.com/spreadsheets/d/...")

df_papers = None
spreadsheet = None

if sheet_url:
    try:
        with st.spinner("Loading sheet..."):
            df_papers, spreadsheet = load_sheet(sheet_url)
        missing = {"title", "abstract", "citation"} - set(df_papers.columns)
        if missing:
            st.error(f"Missing columns: {missing}. Found: {list(df_papers.columns)}")
            df_papers = None
        else:
            # Deduplicate
            before = len(df_papers)
            df_papers["_norm"] = df_papers["title"].str.strip().str.lower()
            df_papers = df_papers.drop_duplicates(subset="_norm").drop(columns="_norm")
            dupes = before - len(df_papers)
            st.success(f"Loaded {len(df_papers)} papers." +
                       (f" Removed {dupes} duplicate(s)." if dupes else ""))
            st.dataframe(df_papers[["title", "abstract", "citation"]].head(5),
                         use_container_width=True)
    except Exception as e:
        st.error(f"Could not open sheet: {e}")

if df_papers is None:
    st.stop()

st.divider()

# ── Step 2: Choose modules ────────────────────────────────────────────────
st.header("Step 2 — Choose what to analyze")
st.markdown("Start with bare bones and add more as your team decides what you need.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Always included")
    st.markdown("✅ Basic metadata (authors, year, journal, DOI)")

    st.subheader("Classification")
    use_article_type = st.checkbox("Article type (Empirical / Review / Conceptual...)", value=False)
    use_research_design = st.checkbox("Research design (Creswell taxonomy)", value=False)
    use_sample_size = st.checkbox("Sample size", value=False)
    use_setting = st.checkbox("Setting (country/region)", value=False)

with col2:
    st.subheader("Tagging")
    use_topic_tags = st.checkbox("Topic tags", value=False)
    use_population_tags = st.checkbox("Population tags", value=False)

    st.subheader("Synthesis")
    use_key_finding = False
    use_relevance = st.checkbox("Relevance score (1–5) with rationale", value=False)

    st.subheader("OpenAlex details")
    st.caption("Add these to understand why peer-review status was assigned.")
    use_openalex = True  # always runs silently for peer_reviewed
    show_work_type = st.checkbox("Work type (article, book-chapter, preprint...)", value=False)
    show_source_type = st.checkbox("Source type (journal, repository...)", value=False)
    show_cited_by = st.checkbox("Citation count", value=False)
    show_oa_status = st.checkbox("Open access status", value=False)
    show_openalex_id = st.checkbox("OpenAlex record link", value=False)

modules = {
    "openalex": True,
    "article_type": use_article_type,
    "research_design": use_research_design,
    "sample_size": use_sample_size,
    "setting": use_setting,
    "topic_tags": use_topic_tags,
    "population_tags": use_population_tags,
    "key_finding": use_key_finding,
    "relevance": use_relevance,
    "show_work_type": show_work_type,
    "show_source_type": show_source_type,
    "show_cited_by": show_cited_by,
    "show_oa_status": show_oa_status,
    "show_openalex_id": show_openalex_id,
}

st.divider()

# ── Step 3: Flag conditions ───────────────────────────────────────────────
st.header("Step 3 — What should get flagged for full-text review?")
st.markdown(
    "Select the conditions that should trigger a flag. "
    "Flagged papers will show **⚑ REVIEW** in the output sheet with a reason. "
    "Leave everything unchecked and the agent will only flag papers it finds genuinely ambiguous on its own."
)

FLAG_OPTIONS = [
    "Abstract too short or vague to classify",
    "Research design cannot be determined from the abstract",
    "Population not clearly identified",
    "Setting / country not identifiable",
    "Article type is ambiguous",
    "Journal not found in OpenAlex",
    "Possible predatory or non-peer-reviewed journal",
    "Full text needed before inclusion decision can be made",
]

selected_flags = st.multiselect(
    "Flag a paper when:",
    options=FLAG_OPTIONS,
    default=[],
    placeholder="Choose flag conditions...",
)

custom_flag = st.text_input(
    "Other — describe your own flag condition:",
    placeholder="e.g. flag if no L2 population is mentioned",
)
if custom_flag.strip():
    selected_flags = selected_flags + [custom_flag.strip()]

if selected_flags:
    st.caption(f"{len(selected_flags)} flag condition(s) active")
else:
    st.caption("No conditions selected — agent will flag only papers it finds genuinely ambiguous.")

st.divider()

# ── Step 4: Customize tags ────────────────────────────────────────────────
if use_topic_tags or use_population_tags:
    st.header("Step 4 — Customize tags")

if use_topic_tags:
    st.subheader("Topic tags")
    st.markdown("Remove tags that don't fit your review. Add your own below.")

    if "topic_tags" not in st.session_state:
        st.session_state.topic_tags = DEFAULT_TOPIC_TAGS.copy()

    selected_tags = st.multiselect(
        "Active topic tags (deselect to remove):",
        options=st.session_state.topic_tags,
        default=st.session_state.topic_tags,
    )
    new_tag = st.text_input("Add a custom topic tag:", placeholder="e.g. systemic functional linguistics")
    if st.button("Add topic tag") and new_tag.strip():
        tag = new_tag.strip()
        if tag not in st.session_state.topic_tags:
            st.session_state.topic_tags.append(tag)
            st.rerun()

    final_topic_tags = selected_tags
    st.caption(f"{len(final_topic_tags)} topic tags active")
else:
    final_topic_tags = DEFAULT_TOPIC_TAGS

if use_population_tags:
    st.subheader("Population keywords")
    st.markdown(
        "Enter the population keywords your team agreed on — one per line. "
        "The agent will tag each paper against these **and** flag any populations "
        "it finds that aren't on your list, so you can grow the vocabulary as you go."
    )

    if "population_tags" not in st.session_state:
        st.session_state.population_tags = []

    # Free-entry text area
    raw_input = st.text_area(
        "Your population keywords (one per line):",
        value="\n".join(st.session_state.population_tags),
        height=150,
        placeholder="e.g.\nEFL learners\nuniversity students\nChinese students\nadult learners",
    )
    entered_tags = [t.strip() for t in raw_input.splitlines() if t.strip()]
    st.session_state.population_tags = entered_tags

    if entered_tags:
        st.caption(f"{len(entered_tags)} population keywords defined")
    else:
        st.info(
            "No keywords entered yet — the agent will run in discovery mode: "
            "it won't assign tags but will suggest populations it finds in each abstract."
        )

    final_population_tags = entered_tags
else:
    final_population_tags = []

if use_topic_tags or use_population_tags:
    st.divider()

# ── Step 5: Run ───────────────────────────────────────────────────────────
st.header("Step 5 — Run analysis")

api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
if not api_key:
    st.error("ANTHROPIC_API_KEY not found in Streamlit secrets.")
    st.stop()

output_tab_name = st.text_input("Output tab name in Google Sheet:", value="Results")

if st.button("▶ Run analysis", type="primary"):
    client = anthropic.Anthropic(api_key=api_key)
    system_prompt = build_system_prompt(modules, final_topic_tags, final_population_tags, selected_flags)

    results = []
    progress = st.progress(0)
    status = st.empty()
    total = len(df_papers)

    for i, row in df_papers.iterrows():
        n = len(results) + 1
        title = str(row.get("title", "")).strip()
        abstract = str(row.get("abstract", "")).strip()
        citation = str(row.get("citation", "")).strip()

        status.markdown(f"**[{n}/{total}]** {title[:80]}{'...' if len(title) > 80 else ''}")

        doi_match = re.search(r'https?://doi\.org/(\S+)|doi[:\s]+(\S+)', citation, re.IGNORECASE)
        doi_raw = (doi_match.group(1) or doi_match.group(2)).rstrip('.') if doi_match else ""

        openalex = {}
        if modules["openalex"]:
            openalex = lookup_openalex(doi_raw, title)

        try:
            analysis = analyze_paper(client, system_prompt, title, abstract, citation, openalex)
            for field in ("topic_tags", "population_tags", "suggested_population_tags"):
                if isinstance(analysis.get(field), list):
                    analysis[field] = "; ".join(analysis[field])
            # Convert flag to readable label
            if analysis.get("flag_full_text") in (True, "true", "True"):
                analysis["flag_full_text"] = "⚑ REVIEW"
            else:
                analysis["flag_full_text"] = ""
            record = {
                "title": title, "citation": citation, "abstract": abstract,
                "parse_error": "",
                **analysis,
            }
            if modules["show_work_type"]:
                record["openalex_work_type"] = openalex.get("work_type", "")
            if modules["show_source_type"]:
                record["openalex_source_type"] = openalex.get("source_type", "")
            if modules["show_cited_by"]:
                record["cited_by_count"] = openalex.get("cited_by_count", "")
            if modules["show_oa_status"]:
                record["oa_status"] = openalex.get("oa_status", "")
            if modules["show_openalex_id"]:
                record["openalex_id"] = openalex.get("openalex_id", "")
        except Exception as e:
            record = {"title": title, "citation": citation, "abstract": abstract,
                      "parse_error": str(e)}

        results.append(record)
        progress.progress(n / total)
        time.sleep(0.3)

    status.markdown("✅ Analysis complete.")
    df_results = pd.DataFrame(results)
    st.session_state.df_results = df_results
    st.session_state.spreadsheet = spreadsheet
    st.session_state.output_tab_name = output_tab_name

# ── Step 6: Preview and write results ─────────────────────────────────────
if "df_results" in st.session_state:
    st.divider()
    st.header("Step 6 — Results")

    df_results = st.session_state.df_results

    # Summary stats
    cols = st.columns(4)
    cols[0].metric("Total papers", len(df_results))
    if "relevance_score" in df_results.columns:
        high = (pd.to_numeric(df_results["relevance_score"], errors="coerce") >= 4).sum()
        cols[1].metric("High relevance (4–5)", int(high))
    if "flag_full_text" in df_results.columns:
        flagged = (df_results["flag_full_text"] == "⚑ REVIEW").sum()
        cols[2].metric("Flagged for review", int(flagged))
    if "parse_error" in df_results.columns:
        errors = (df_results["parse_error"] != "").sum()
        cols[3].metric("Errors", int(errors))

    st.dataframe(df_results, use_container_width=True, height=400)

    # Surface suggested population tags so team can grow their keyword list
    if "suggested_population_tags" in df_results.columns:
        all_suggestions = []
        for val in df_results["suggested_population_tags"].dropna():
            all_suggestions.extend([s.strip() for s in str(val).split(";") if s.strip()])
        if all_suggestions:
            from collections import Counter
            counts = Counter(all_suggestions)
            st.subheader("💡 Suggested population keywords")
            st.markdown(
                "These populations appeared in abstracts but weren't in your keyword list. "
                "Consider adding the frequent ones to your list and rerunning."
            )
            suggestion_df = pd.DataFrame(
                counts.most_common(), columns=["Suggested keyword", "Papers"]
            )
            st.dataframe(suggestion_df, use_container_width=False, hide_index=True)

    if st.button("📤 Write to Google Sheet", type="primary"):
        try:
            sh = st.session_state.spreadsheet
            tab_name = st.session_state.output_tab_name

            # Create or clear the output tab
            try:
                ws = sh.worksheet(tab_name)
                ws.clear()
            except gspread.WorksheetNotFound:
                ws = sh.add_worksheet(title=tab_name, rows=len(df_results) + 10, cols=len(df_results.columns) + 5)

            # Write header + data
            df_out = df_results.fillna("").astype(str)
            ws.update([df_out.columns.tolist()] + df_out.values.tolist())

            st.success(f"Written to tab '{tab_name}' in your Google Sheet.")
            st.markdown(f"[Open Google Sheet]({sheet_url})")
        except Exception as e:
            st.error(f"Could not write to sheet: {e}")
