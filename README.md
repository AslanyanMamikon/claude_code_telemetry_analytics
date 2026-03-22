# Claude Code Telemetry Analytics

An end-to-end analytics platform that processes synthetic telemetry data from Claude Code sessions and presents developer usage patterns through an interactive dashboard.

Built as part of a technical assignment to demonstrate data engineering, analytics, and AI-assisted development skills.

---

## Architecture Overview

```
generate_fake_data.py        →       output/
(synthetic data generator)           ├── telemetry_logs.jsonl   (raw event stream)
                                     └── employees.csv          (engineer profiles)
                                              │
                                         ingest.py
                                    (parse & load into DB)
                                              │
                                       analytics.duckdb
                                    (structured tables)
                                              │
                                        dashboard.py
                                  (Streamlit + Plotly UI)
```

### Components

- **Data Generator** (`generate_fake_data.py`) — Produces realistic synthetic telemetry events: API requests, tool usage, user prompts, and errors across 100 engineers over 60 days
- **Ingestion Script** (`ingest.py`) — Parses the raw nested JSONL batches, extracts meaningful fields from each event type, and loads them into a structured DuckDB database
- **Database** (`analytics.duckdb`) — Five clean tables: `api_requests`, `user_prompts`, `tool_events`, `api_errors`, `employees`
- **Dashboard** (`dashboard.py`) — Interactive Streamlit app with Plotly charts, sidebar filters, and KPI metrics

---

## Tech Stack

| Layer | Tool |
|---|---|
| Data generation | Python 3 (standard library) |
| Data storage | DuckDB |
| Dashboard | Streamlit |
| Charts | Plotly |
| Data manipulation | Pandas |

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/AslanyanMamikon/claude_code_telemetry_analytics.git
cd claude-code-telemetry-analytics
```

### 2. Install dependencies

```bash
pip install duckdb streamlit plotly pandas
```

### 3. Generate the dataset

```bash
python3 generate_fake_data.py --num-users 100 --num-sessions 5000 --days 60
```

This creates two files in the `output/` directory:
- `output/telemetry_logs.jsonl` — raw telemetry event batches
- `output/employees.csv` — engineer directory

### 4. Ingest data into DuckDB

```bash
python3 ingest.py
```

By default this reads from `output/` and creates `analytics.duckdb` in the current directory.

Optional flags:
```bash
python3 ingest.py --telemetry output/telemetry_logs.jsonl --employees output/employees.csv --db analytics.duckdb
```

Expected output:
```
=== Ingestion Complete ===
  api_requests : 118,014
  user_prompts :  35,173
  tool_events  : 299,879
  api_errors   :   1,362
  skipped      :       0
```

### 5. Launch the dashboard

```bash
streamlit run dashboard.py
```

The dashboard will open automatically in your browser at `http://localhost:8501`.

---

## Database Schema

| Table | Description |
|---|---|
| `api_requests` | One row per Claude API call — model, cost, tokens, duration |
| `user_prompts` | One row per user message — session, email, prompt length |
| `tool_events` | One row per tool decision or result — tool name, success, duration |
| `api_errors` | One row per API error — error message, status code, model |
| `employees` | Engineer directory — name, practice, level, location |

All tables join on `user_email` ↔ `employees.email`.

---

## Dashboard Features

- **KPI Row** — Total sessions, API calls, cost, avg cost per call, tokens, active engineers
- **Model Breakdown** — API calls by model, cost distribution by engineering practice
- **Usage Over Time** — Daily API call trend, hour × day heatmap
- **Token Consumption** — Avg tokens per call by seniority level, top tools by usage and success rate
- **Error Analysis** — Most frequent API errors by model
- **Geographic Distribution** — Total cost by engineer location
- **Top Engineers Table** — Ranked leaderboard with sessions, calls, cost, and tokens
- **Sidebar Filters** — Filter all charts by practice, level, location, model, and date range

---

## LLM Usage Log

**Tools used:** Claude (Anthropic)

Throughout this project, Claude was used as a core part of the engineering workflow — not just for code generation, but as a thinking partner for architecture decisions.

**Key prompts and how they were used:**

- Provided Claude with the full assignment brief and raw data schema upfront, asking it to reason about the optimal storage design before writing any code: *"Given this telemetry event structure, design a normalized DuckDB schema that supports analytics queries on cost, tool usage, and session behavior by engineer level and practice."*

- Directed Claude to write the ingestion script with specific constraints: *"Parse the JSONL batch format, handle malformed lines gracefully, flush inserts in batches of 5000 for performance, and print a verification summary at the end."*

- Prompted Claude to build a dark-themed Streamlit dashboard with Plotly charts covering model usage, cost breakdown, time-based heatmaps, tool analysis, and a filterable engineer leaderboard.

- Used Claude to generate the insights PDF, providing the actual dashboard data as input and specifying the 5-slide structure. Reviewed each slide visually, identified layout overflow issues on slides and directed Claude to fix the boundary calculations until all elements were correctly contained.

- Used Claude iteratively — reviewing generated output, identifying gaps, and re-prompting with corrections rather than accepting first drafts blindly.

**Validation approach:**

- Verified row counts after ingestion matched expected event distribution from the generator
- Spot-checked individual records against raw JSONL to confirm fields were parsed correctly
- Reviewed all generated code before running it
- Cross-referenced dashboard numbers against direct DuckDB queries to confirm accuracy

---

## Project Structure

```
claude-code-telemetry-analytics/
├── generate_fake_data.py   # Synthetic data generator (provided)
├── ingest.py               # Data ingestion into DuckDB
├── dashboard.py            # Streamlit analytics dashboard
├── README.md               # This file
└── output/                 # Generated data files (not committed to git)
    ├── telemetry_logs.jsonl
    └── employees.csv
```

---

## Notes

- All user identifiers in the dataset are fully synthetic
- Prompt contents are redacted in the telemetry data
- The `output/` directory and `analytics.duckdb` file should be added to `.gitignore` as they are generated locally
