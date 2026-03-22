# ⚡ U.S. Energy Grid Risk Monitor

A real-time operational intelligence tool that ingests live U.S. electricity data, runs an automated risk scoring pipeline, and surfaces grid stress signals to operators through an interactive dashboard.

Built to mirror the data workflows Palantir Foundry deploys with utility and infrastructure clients — raw data in, clean ontology out, actionable decision support on top.

---

## The Problem

Grid operators across the U.S. manage a constant balancing act: generation must meet demand in real time. When demand chronically outpaces local generation, regions become dependent on imported power — and vulnerable to cascading failures if interconnections are disrupted. Identifying *which* regions are structurally stressed, and *how* stressed they are right now, is an operational problem with real consequences.

This tool answers that question continuously, across all 9 major U.S. balancing authorities.

---

## Dashboard

![Dashboard Top](screenshots/top.png)

![Dashboard Map & Detail](screenshots/mid.png)

![Dashboard Table & Definitions](screenshots/low.png)

---

## Architecture

A six-layer pipeline, each stage independently testable:

```
[Ingest]  →  [Transform]  →  [Score]  →  [Storage]  →  [Agent]  →  [Dashboard]
EIA API       Clean + derive   Risk level   DuckDB        Claude        Streamlit
              operational      + trend      persistence   tool use      + Folium
              fields           velocity
```

| Layer | File | Description |
|---|---|---|
| Ingestion | `src/ingest.py` | Pulls hourly demand & generation from EIA API v2 for 9 regions |
| Transform | `src/transform.py` | Derives net balance, balance ratio, rolling averages, stress flags |
| Scoring | `src/score.py` | Assigns CRITICAL / HIGH / MEDIUM / LOW risk + 6-hour trend velocity |
| Storage | `src/storage.py` | Persists time series and scores to DuckDB |
| Agent | `src/agent.py` | Claude-powered situation report and Q&A; all answers grounded in tool calls against DuckDB |
| Dashboard | `app.py` | Interactive Streamlit app with geospatial map, time series, and AI analyst panel |

---

## Key Findings

> The table below reflects a historical data pull (2026-03-12 → 2026-03-19). Because this tool ingests live EIA data, scores change hourly — results when you run it today will differ. See [`reports/eda_report.md`](reports/eda_report.md) for the full snapshot with methodology notes.

| Region | Risk | Avg Net Balance | Stress Hours |
|---|---|---|---|
| California ISO | CRITICAL | -8,601 MW | 100% |
| New York | HIGH | -2,692 MW | 100% |
| Texas | HIGH | +78 MW | 100% |
| Midwest | HIGH | +672 MW | 100% |
| Mid-Atlantic | HIGH | +2,149 MW | 98.7% |
| New England | HIGH | -183 MW | 92.9% |
| Southeast | MEDIUM | +1,212 MW | 47.7% |
| Southwest | MEDIUM | +831 MW | 38.2% |
| Northwest | LOW | +5,297 MW | 11.5% |

**California** never generates enough to meet its own demand — running a chronic -8,601 MW deficit driven by solar intermittency and high consumption. **Texas (ERCOT)** operates with a razor-thin +78 MW average surplus on a ~49,000 MW system. The **Northwest's** hydro surplus (+5,297 MW avg) makes it the grid's primary stabilizing buffer.

---

## AI Features

The dashboard includes a Claude-powered analyst layer (`src/agent.py`) built on Anthropic's tool use API:

- **Situation Report** — auto-generated on load; Claude calls `get_current_scores()` against DuckDB and produces a 3-5 sentence operational briefing covering risk distribution, deteriorating regions, and the grid's strongest buffer
- **Ask the Grid Analyst** — free-text Q&A panel; Claude can call `get_current_scores`, `get_region_history`, and `compare_regions` to answer questions about current conditions

**Anti-hallucination design:** Claude is prohibited from performing arithmetic on tool results, using prior knowledge about grid infrastructure, or inferring causes. Every number in its output comes directly from a tool call against DuckDB. This mirrors Palantir AIP's pattern of grounding LLM responses in ontology-backed tool calls rather than model inference.

---

## Tech Stack

| Tool | Purpose |
|---|---|
| Python | Pipeline orchestration |
| Pandas | Data transformation |
| DuckDB | Local SQL storage layer |
| Streamlit | Operational dashboard |
| Folium | Geospatial risk map |
| EIA API v2 | Live U.S. grid data source |
| Claude (claude-sonnet-4-6) | AI situation report and Q&A analyst |

---

## Running Locally

**Prerequisites:** Python 3.10+, an [EIA API key](https://www.eia.gov/opendata/) (free), an [Anthropic API key](https://console.anthropic.com/) (for AI features)

```bash
# Clone the repo
git clone https://github.com/MilanJ22/energy-grid-monitor.git
cd energy-grid-monitor

# Set up virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Add your API keys
cp .env.example .env
# Edit .env and set EIA_API_KEY and ANTHROPIC_API_KEY

# Launch the dashboard
streamlit run app.py
```

The pipeline runs automatically on startup and refreshes every hour. No database setup required — DuckDB creates the file locally on first run.

---

## Project Structure

```
energy-grid-monitor/
├── src/
│   ├── ingest.py       # EIA API data fetching
│   ├── transform.py    # Pipeline transforms and derived metrics
│   ├── score.py        # Risk scoring engine + 6-hour trend velocity
│   ├── storage.py      # DuckDB read/write layer
│   └── agent.py        # Claude AI agent — situation report and Q&A
├── app.py              # Streamlit dashboard
├── reports/
│   └── eda_report.md   # Exploratory data analysis findings (historical snapshot)
├── screenshots/        # Dashboard previews
├── .env.example        # API key template
└── requirements.txt    # Dependencies
```

---

## Data Source

All data sourced from the **U.S. Energy Information Administration (EIA) Open Data API v2** — specifically the hourly regional electricity demand and net generation endpoints for U.S. balancing authorities. Data is public, free, and updated hourly.

---

*Built by Milan Jain · [github.com/MilanJ22](https://github.com/MilanJ22)*
