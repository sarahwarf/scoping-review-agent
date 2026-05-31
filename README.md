# Scoping Review Agent — L2 Writing

An AI-powered first-pass screening tool for scoping reviews. Paste in a Google Sheet of paper titles, abstracts, and APA 7 citations and the agent extracts structured metadata — peer-review status, article type, research design, topic tags, population tags, and more — and writes the results back to the shared sheet for the team to review together.

**Live app:** [scopingreview.streamlit.app](https://scopingreview.streamlit.app)

---

## How to use

### Before you start

Your Google Sheet must:
- Have three columns named exactly: **Title**, **Abstract**, **Citation**
- Be shared with the service account email as Editor:
  `scoping-review@chatbotphase1sarahwarf.iam.gserviceaccount.com`

> **Note:** The sheet must be a Google Sheet, not an uploaded Excel file. If you have an `.xlsx` file, open it in Google Drive and go to **File → Save as Google Sheets** first.

---

### Step-by-step

**1. Connect your sheet**
Paste the Google Sheet URL into the app. The agent loads and deduplicates your papers automatically.

**2. Choose what to analyze**
Select which modules to run. For a first round, bare bones is recommended:
- ✅ Basic metadata (authors, year, journal, DOI) — always included
- ✅ OpenAlex lookup — verifies peer-review status
- Add more (article type, research design, topic tags, population tags, relevance score) as your team decides what it needs

**3. Set flag conditions**
Choose what should trigger a **⚑ REVIEW** flag — papers the agent wasn't confident about that need a human to check. Options include:
- Abstract too short or vague to classify
- Research design cannot be determined
- Population not clearly identified
- Setting not identifiable
- Article type ambiguous
- Journal not found in OpenAlex
- Possible predatory or non-peer-reviewed journal

Or use the **Other** box to write your own condition (e.g. "flag if no L2 population is mentioned").

> The agent flags based on language signals in the abstract — these are inferences, not verified facts. A human should always make the final call on flagged papers.

**4. Customize tags** *(if topic or population tags are selected)*
- **Topic tags** — remove defaults that don't fit, add your own
- **Population tags** — enter your team's agreed keywords one per line. Leave blank to run in discovery mode, where the agent suggests populations it finds across all abstracts.

**5. Run the analysis**
Give your output tab a short name (e.g. `Results Round 1`) and click **Run analysis**. The agent processes one paper at a time — roughly 3–5 seconds each.

**6. Write results to Google Sheet**
Click **Write to Google Sheet**. Results land in a new tab in the same sheet. The first tab is your original data; the new tab is the analyzed output. DOIs are written as clickable hyperlinks.

---

## What the app analyzes

| Field | Description |
|---|---|
| `authors` | Parsed from APA citation |
| `year` | Publication year |
| `journal_or_source` | Journal or book/conference name |
| `doi` | Clickable DOI link |
| `peer_reviewed` | Verified via OpenAlex |
| `article_type` | Empirical-Quantitative / Qualitative / Mixed / Review / Conceptual / Practitioner |
| `research_design` | Creswell taxonomy (Quasi-experimental, Case study, Ethnography, etc.) |
| `research_design_confidence` | confirmed / inferred / unclear |
| `sample_size` | Who and how many participants |
| `l2_focus` | Whether the paper is centrally about L2/ESL/EFL writing |
| `topic_tags` | L2 writing topic tags (customizable) |
| `population_tags` | Team-defined population keywords |
| `suggested_population_tags` | Populations found but not in your keyword list |
| `setting` | Country or region |
| `relevance_score` | 1–5 with rationale *(round 2)* |
| `flag_full_text` | ⚑ REVIEW if flagged |
| `flag_reason` | Which condition triggered the flag |

Optional OpenAlex columns (off by default, available under **OpenAlex details**):
- Work type, source type, citation count, open access status, OpenAlex record link

---

## Tips

- **Round 1:** Run bare bones — metadata, peer-review, flags. Get the sheet into shape.
- **Round 2:** Add article type, research design, topic tags, population tags, relevance score once the team has agreed on inclusion criteria.
- **Population tags:** Start in discovery mode (leave blank) on the first batch. The agent will suggest what populations are actually in your corpus.
- **Batching:** Safe ceiling is ~300 papers per run on Streamlit Cloud. For larger sets, split into batches and write to separate tabs.
- **Cost:** ~$0.002 per paper via the Claude API. 200 papers ≈ $0.40.

---

## Built with

- [Claude](https://anthropic.com) (Anthropic) — abstract analysis and classification
- [OpenAlex](https://openalex.org) — bibliographic verification (free, no key required)
- [Streamlit](https://streamlit.io) — web interface
- [gspread](https://github.com/burnash/gspread) — Google Sheets integration

---

## Fork this project

Want to adapt this for your own scoping review? Fork the repo, update the topic and population tag lists in `app.py` to match your domain, and deploy your own instance on Streamlit Cloud. The setup instructions above apply unchanged. If you build something with it, a credit back to this repo is appreciated.

---

MIT License © Sarah Warfield
