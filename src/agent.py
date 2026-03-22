import os
import json
import anthropic
from dotenv import load_dotenv
import duckdb
from pathlib import Path

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-6"
MAX_TOOL_ROUNDS = 5

DB_PATH = Path("data/grid_monitor.db")


VALID_REGIONS = {"CISO", "MIDA", "MIDW", "NE", "NW", "NY", "SE", "SW", "TEX"}


def _db_query(sql: str, params: list = None) -> str:
    """Run SQL against DuckDB and return a clean string. Returns a message if no rows found."""
    con = duckdb.connect(str(DB_PATH))
    df = con.execute(sql, params or []).df()
    con.close()
    if df.empty:
        return "No data found."
    return df.to_string(index=False)


# ── System prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a U.S. grid operations analyst. Your role is to produce clear, \
factual briefings about current grid conditions based strictly on data returned by your tools.

You have access to live EIA demand and generation data for 9 U.S. balancing authorities, \
stored in a local DuckDB database and refreshed hourly:
  CISO  — California ISO
  MIDA  — Mid-Atlantic
  MIDW  — Midwest
  NE    — New England
  NW    — Northwest
  NY    — New York
  SE    — Southeast
  SW    — Southwest
  TEX   — Texas

RISK LEVELS (assigned by the scoring engine, not by you):
  CRITICAL — chronic high importer with a sustained active stress streak
  HIGH     — demand regularly meets or exceeds generation
  MEDIUM   — intermittent stress, moderate imbalance
  LOW      — healthy surplus, rarely stressed

TREND (computed over 6-hour balance_ratio velocity):
  DETERIORATING — demand is rising relative to generation over the last 6 hours
  STABLE        — conditions are holding steady
  RECOVERING    — supply is improving relative to demand over the last 6 hours

ABSOLUTE RULES — these are non-negotiable:
1. Every factual claim must be directly supported by a value returned by a tool call. \
If a tool returns a number, you may report it exactly. You may not round, estimate, or \
adjust it.
2. Never perform any arithmetic on tool results — no addition, subtraction, averaging, \
or ratio computation. If a number is not in the tool result, do not state it.
3. Never use your prior knowledge about U.S. grid regions, energy markets, weather, \
or infrastructure to explain or infer why a region is stressed. Report only what the \
data shows.
4. If a tool returns no data, say so explicitly and do not speculate about why.
5. Do not state causes, predictions, or recommendations beyond what the data directly supports.

Tone: concise, operational, factual. You are a data readout, not an analyst."""


# ── Tool definitions ─────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "get_current_scores",
        "description": (
            "Returns the current risk score for all 9 grid regions: region name, risk level "
            "(CRITICAL/HIGH/MEDIUM/LOW), 6-hour trend (DETERIORATING/STABLE/RECOVERING), "
            "average net balance in MW, average balance ratio, stress percentage, current "
            "stress streak in hours, and the timestamp of the most recent data point. "
            "Always call this first for any question about current grid conditions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_region_history",
        "description": (
            "Returns the hourly net balance (MW) and balance ratio for a specific region "
            "over the last N hours (default 24). Use this to describe how a region's "
            "conditions have moved over time. region_code must be one of: "
            "CISO, MIDA, MIDW, NE, NW, NY, SE, SW, TEX."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "region_code": {
                    "type": "string",
                    "description": "The region code, e.g. 'CISO' or 'TEX'.",
                },
                "hours": {
                    "type": "integer",
                    "description": "Number of recent hours to return. Default 24.",
                },
            },
            "required": ["region_code"],
        },
    },
    {
        "name": "compare_regions",
        "description": (
            "Returns a side-by-side comparison of two regions from the current scores table. "
            "Use this when asked to compare two specific regions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "region_a": {
                    "type": "string",
                    "description": "Region code for the first region, e.g. 'CISO'.",
                },
                "region_b": {
                    "type": "string",
                    "description": "Region code for the second region, e.g. 'TEX'.",
                },
            },
            "required": ["region_a", "region_b"],
        },
    },
]


# ── Tool execution ────────────────────────────────────────────────────────────

def _get_current_scores() -> str:
    return _db_query("""
        SELECT region_name,
               risk_level,
               trend,
               CAST(avg_net_balance_mw AS INTEGER)  AS avg_net_balance_mw,
               ROUND(avg_balance_ratio, 4)           AS avg_balance_ratio,
               stress_pct,
               stress_streak,
               last_updated
        FROM region_scores
        ORDER BY risk_rank DESC
    """)


def _get_region_history(region_code: str, hours: int = 24) -> str:
    region_code = region_code.upper().strip()
    if region_code not in VALID_REGIONS:
        return f"Invalid region code '{region_code}'. Must be one of: {', '.join(sorted(VALID_REGIONS))}"
    hours = max(1, min(int(hours), 168))  # clamp to 1h–7 days
    return _db_query(f"""
        SELECT timestamp,
               CAST(net_balance_mw AS INTEGER) AS net_balance_mw,
               ROUND(balance_ratio, 4)         AS balance_ratio,
               is_stress_hour
        FROM time_series
        WHERE region = ?
          AND timestamp >= (
              SELECT MAX(timestamp) - INTERVAL '{hours} hours'
              FROM time_series
              WHERE region = ?
          )
        ORDER BY timestamp
    """, [region_code, region_code])


def _compare_regions(region_a: str, region_b: str) -> str:
    a = region_a.upper().strip()
    b = region_b.upper().strip()
    for code in (a, b):
        if code not in VALID_REGIONS:
            return f"Invalid region code '{code}'. Must be one of: {', '.join(sorted(VALID_REGIONS))}"
    return _db_query("""
        SELECT region_name,
               risk_level,
               trend,
               CAST(avg_net_balance_mw AS INTEGER) AS avg_net_balance_mw,
               ROUND(avg_balance_ratio, 4)         AS avg_balance_ratio,
               stress_pct,
               stress_streak
        FROM region_scores
        WHERE region IN (?, ?)
        ORDER BY risk_rank DESC
    """, [a, b])


def _execute_tool(name: str, inputs: dict) -> str:
    if name == "get_current_scores":
        return _get_current_scores()
    elif name == "get_region_history":
        return _get_region_history(**inputs)
    elif name == "compare_regions":
        return _compare_regions(**inputs)
    else:
        return f"Unknown tool: {name}"


# ── Core agentic loop ─────────────────────────────────────────────────────────

def _run(initial_message: str) -> str:
    """Send a message to Claude, execute tool calls, and return the final text."""
    messages = [{"role": "user", "content": initial_message}]

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            return _extract_text(response)

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = _execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

    return _extract_text(response)


def _extract_text(response) -> str:
    return "\n".join(
        block.text for block in response.content if hasattr(block, "text")
    )


# ── Public interface ──────────────────────────────────────────────────────────

def generate_situation_report() -> str:
    """
    Generates a 3-5 sentence operational briefing of current grid conditions.
    Claude calls get_current_scores(), then synthesizes a factual summary.
    All numbers in the output come directly from tool results — no inference.
    """
    return _run(
        "Generate a current grid situation report. Call get_current_scores first. "
        "Summarize in 3-5 sentences: how many regions are at each risk level, "
        "which CRITICAL or HIGH regions are deteriorating vs stable, "
        "which regions are recovering, and which region has the strongest surplus. "
        "Report only numbers and labels returned by the tool. Do not infer causes."
    )


def ask(question: str) -> str:
    """
    Answer a specific question about current grid conditions.
    Claude will call tools as needed and return a factual response.
    """
    return _run(question)


if __name__ == "__main__":
    print(generate_situation_report())
