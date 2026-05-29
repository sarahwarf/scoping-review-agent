# Scoping Review Agent — L2 Writing

Analyzes a CSV of paper titles, abstracts, and APA 7 citations and produces a structured Excel workbook ready for team screening.

## Setup (one time per person)

```bash
pip3 install anthropic pandas openpyxl
export ANTHROPIC_API_KEY="sk-ant-..."   # add to ~/.zshrc or ~/.bash_profile to persist
```

## Input CSV format

Three required columns (header names exact, case-insensitive):

| column | contents |
|--------|----------|
| `title` | Paper title |
| `abstract` | Full abstract text |
| `citation` | APA 7 citation string |

See `sample_input.csv` for examples. Export directly from Zotero, Mendeley, or Excel.

## Running

```bash
# Full analysis (calls Claude API, ~$0.001–0.003 per paper)
python3 scoping_review.py your_papers.csv

# Specify output file
python3 scoping_review.py your_papers.csv --output results_round1.xlsx

# Dry run — parses citations only, no API cost
python3 scoping_review.py your_papers.csv --dry-run
```

## Output columns

| column | description |
|--------|-------------|
| `authors` | Parsed author list |
| `year` | Publication year |
| `journal_or_source` | Journal or book/conference name |
| `doi` | DOI if found |
| `peer_reviewed` | true/false |
| `article_type` | Empirical-Quantitative / Qualitative / Mixed / Review / Conceptual / Practitioner |
| `study_design` | experiment, survey, case study, corpus analysis, etc. |
| `sample_size` | Brief description |
| `l2_focus` | true if paper is centrally about L2/ESL/EFL writing |
| `topic_tags` | Semicolon-separated L2 writing topic tags |
| `population_tags` | Semicolon-separated population tags |
| `setting` | Country/region context |
| `relevance_score` | 1–5 (5 = core L2 writing; 1 = exclude) |
| `relevance_rationale` | One-sentence explanation |
| `key_finding_or_claim` | 1–2 sentence summary |
| `flag_full_text` | true = abstract ambiguous, retrieve full text |
| `flag_reason` | Why flagged |

Relevance score coloring in Excel: green (4–5), yellow (3), red (1–2).

## Tips

- Duplicates are removed automatically (matched on title).
- Run `--dry-run` first to confirm your CSV columns are recognized.
- Use `--delay 1.0` to slow API calls if you hit rate limits on large batches.
- Add a `notes` column to your input CSV — it passes through to the output.
