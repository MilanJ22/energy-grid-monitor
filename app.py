import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from src.storage import init_db, save_time_series, save_region_scores, load_time_series, load_region_scores
from src.ingest import fetch_all_regions
from src.transform import transform, summarize_by_region
from src.score import score, TREND_ICONS, TREND_COLORS
from src.agent import generate_situation_report, ask as grid_ask

# --- Page config ---
st.set_page_config(
    page_title="U.S. Energy Grid Risk Monitor",
    page_icon="⚡",
    layout="wide"
)

# --- Professional light theme styling ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background-color: #eef1f7;
    }

    /* Top header bar */
    .header-bar {
        background: linear-gradient(135deg, #1a1f36 0%, #2d3561 100%);
        padding: 28px 36px;
        border-radius: 12px;
        margin-bottom: 28px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .header-title {
        font-size: 26px;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: 0.01em;
        margin: 0;
    }
    .header-subtitle {
        font-size: 13px;
        color: #a0aec0;
        margin-top: 4px;
        font-weight: 400;
    }
    .header-badge {
        background-color: rgba(255,255,255,0.1);
        border: 1px solid rgba(255,255,255,0.2);
        color: #e2e8f0;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 500;
    }

    /* Section labels */
    .section-label {
        font-size: 11px;
        font-weight: 700;
        color: #ffffff;
        background: linear-gradient(90deg, #1a1f36 0%, #2d3561 100%);
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 14px;
        margin-top: 4px;
        padding: 7px 14px;
        border-radius: 6px;
        display: inline-block;
    }

    /* Risk cards */
    .risk-card {
        background: #ffffff;
        border: 1px solid #dce3f0;
        border-radius: 10px;
        padding: 14px 12px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        transition: box-shadow 0.2s;
    }

    /* Metric block wrappers */
    [data-testid="metric-container"] {
        background: #ffffff;
        border: 1px solid #dce3f0;
        border-top: 3px solid #2d3561;
        border-radius: 8px;
        padding: 14px 16px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05);
    }
    [data-testid="stMetricLabel"] {
        font-size: 11px !important;
        font-weight: 600 !important;
        color: #718096 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    [data-testid="stMetricValue"] {
        font-size: 22px !important;
        font-weight: 700 !important;
        color: #1a1f36 !important;
    }

    /* Panel containers */
    .panel {
        background: #ffffff;
        border: 1px solid #dce3f0;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 1px 6px rgba(0,0,0,0.04);
    }

    /* Divider */
    hr {
        border-color: #dce3f0;
        margin: 24px 0;
    }

    /* Expander */
    [data-testid="stExpander"] {
        background: #ffffff;
        border: 1px solid #dce3f0 !important;
        border-radius: 10px !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    }
    [data-testid="stExpander"] summary {
        font-weight: 600;
        color: #1a1f36;
        font-size: 14px;
    }

    /* Dataframe */
    [data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #e2e8f0;
    }

    /* Button */
    .stButton > button {
        background-color: #1a1f36;
        color: #ffffff;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        font-size: 13px;
        padding: 8px 20px;
        letter-spacing: 0.02em;
    }
    .stButton > button:hover {
        background-color: #2d3561;
        color: #ffffff;
    }

    /* Selectbox */
    [data-testid="stSelectbox"] label {
        font-size: 11px !important;
        font-weight: 600 !important;
        color: #718096 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Hide streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Spinner */
    .stSpinner > div {
        border-top-color: #2d3561 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Region coordinates for map markers ---
REGION_COORDS = {
    "CISO": (36.7783, -119.4179),
    "MIDA": (38.9072, -77.0369),
    "MIDW": (41.8781, -87.6298),
    "NE":   (42.3601, -71.0589),
    "NW":   (47.6062, -122.3321),
    "NY":   (40.7128, -74.0060),
    "SE":   (33.7490, -84.3880),
    "SW":   (33.4484, -112.0740),
    "TEX":  (30.2672, -97.7431),
}


# --- Pipeline runner ---
@st.cache_data(ttl=3600)
def run_situation_report():
    """Cached situation report — refreshes with the pipeline (1 hour TTL)."""
    return generate_situation_report()


@st.cache_data(ttl=3600)
def run_pipeline():
    """Fetch, transform, score, and store. Cached for 1 hour."""
    raw = fetch_all_regions(days_back=7)
    transformed = transform(raw)
    summary = summarize_by_region(transformed)
    scored = score(summary, transformed)
    init_db()
    save_time_series(transformed)
    save_region_scores(scored)
    return transformed, scored


def _db_is_fresh() -> bool:
    """Returns True if region_scores exists and was last updated within the past hour."""
    try:
        scores = load_region_scores()
        if scores.empty:
            return False
        import pandas as pd
        last = pd.to_datetime(scores["last_updated"]).max()
        age = pd.Timestamp.utcnow().tz_localize(None) - last.tz_localize(None) if last.tzinfo else pd.Timestamp.utcnow() - last
        return age.total_seconds() < 3600
    except Exception:
        return False


# --- Load data ---
if _db_is_fresh():
    scored_df = load_region_scores()
    time_series_df = load_time_series()
else:
    with st.spinner("Fetching live grid data..."):
        time_series_df, scored_df = run_pipeline()
    time_series_df = load_time_series()

last_updated = scored_df["last_updated"].max()

# --- Header ---
st.markdown(f"""
<div class="header-bar">
    <div>
        <div class="header-title">⚡ U.S. Energy Grid Risk Monitor</div>
        <div class="header-subtitle">
            Real-time demand vs. generation analysis across 9 U.S. balancing authorities · Source: EIA API v2
        </div>
    </div>
    <div class="header-badge">Last updated: {last_updated} UTC</div>
</div>
""", unsafe_allow_html=True)

# --- Refresh button ---
col_refresh, _ = st.columns([1, 7])
with col_refresh:
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

# --- Risk summary cards ---
st.markdown("""
<div style="background: linear-gradient(90deg, #1a1f36 0%, #2d3561 60%, #3d4f8a 100%);
            height: 3px; border-radius: 2px; margin-bottom: 24px;"></div>
""", unsafe_allow_html=True)
st.markdown('<div class="section-label">Regional Risk Overview</div>', unsafe_allow_html=True)

cols = st.columns(len(scored_df))
for i, (_, row) in enumerate(scored_df.iterrows()):
    with cols[i]:
        color = row["risk_color"]
        trend = row["trend"]
        trend_icon = TREND_ICONS[trend]
        trend_color = TREND_COLORS[trend]
        st.markdown(
            f"""
            <div class="risk-card" style="border-top: 3px solid {color};">
                <div style="font-size:10px; font-weight:700; color:#a0aec0;
                            text-transform:uppercase; letter-spacing:0.06em; margin-bottom:6px;">
                    {row['region_name']}
                </div>
                <div style="font-size:16px; font-weight:800; color:{color};
                            letter-spacing:0.04em; margin-bottom:4px;">
                    {row['risk_level']}
                </div>
                <div style="font-size:12px; color:#4a5568; font-weight:500; margin-bottom:3px;">
                    {int(row['avg_net_balance_mw']):+,} MW
                </div>
                <div style="font-size:11px; font-weight:600; color:{trend_color};">
                    {trend_icon} {trend}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

st.markdown("<br>", unsafe_allow_html=True)

# --- AI Situation Report ---
st.markdown("""
<div style="background: linear-gradient(90deg, #1a1f36 0%, #2d3561 60%, #3d4f8a 100%);
            height: 3px; border-radius: 2px; margin-bottom: 24px;"></div>
""", unsafe_allow_html=True)
st.markdown('<div class="section-label">AI Situation Report</div>', unsafe_allow_html=True)

with st.spinner("Generating situation report..."):
    situation_report = run_situation_report()

st.markdown(
    f"""
    <div style="background:#ffffff; border:1px solid #dce3f0; border-left:4px solid #2d3561;
                border-radius:10px; padding:20px 24px;
                box-shadow:0 1px 6px rgba(0,0,0,0.04); font-size:14px;
                color:#1a1f36; line-height:1.7;">
        {situation_report}
    </div>
    <div style="font-size:11px; color:#a0aec0; margin-top:8px; padding-left:4px;">
        Generated by Claude · All figures sourced directly from EIA data via tool calls · No inference
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown("<br>", unsafe_allow_html=True)

# --- Map + Region Detail ---
left, right = st.columns([1.5, 1])

with left:
    st.markdown('<div class="section-label">Grid Risk Map</div>', unsafe_allow_html=True)
    st.markdown('<div class="panel" style="padding: 16px;">', unsafe_allow_html=True)

    m = folium.Map(location=[39.5, -98.35], zoom_start=4, tiles="CartoDB positron")

    for _, row in scored_df.iterrows():
        coords = REGION_COORDS.get(row["region"])
        if not coords:
            continue

        folium.Marker(
            location=coords,
            icon=folium.DivIcon(
                html=f'''
                    <div style="
                        width: 52px;
                        height: 52px;
                        background-color: {row["risk_color"]};
                        border: 2px solid rgba(255,255,255,0.4);
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 9px;
                        font-weight: 800;
                        color: white;
                        text-align: center;
                        line-height: 1.1;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.25);
                        margin-left: -26px;
                        margin-top: -26px;
                    ">{row["risk_level"]}</div>
                ''',
                icon_size=(52, 52),
                icon_anchor=(26, 26),
            ),
            tooltip=folium.Tooltip(
                f"<b style='font-size:13px'>{row['region_name']}</b><br>"
                f"Risk: <b>{row['risk_level']}</b><br>"
                f"Trend (6h): <b>{TREND_ICONS[row['trend']]} {row['trend']}</b><br>"
                f"Avg balance: {int(row['avg_net_balance_mw']):+,} MW<br>"
                f"Stress hours: {row['stress_pct']}%<br>"
                f"Current streak: {int(row['stress_streak'])} hrs"
            )
        ).add_to(m)

    st_folium(m, width=680, height=420)
    st.markdown('</div>', unsafe_allow_html=True)

with right:
    st.markdown('<div class="section-label">Region Detail</div>', unsafe_allow_html=True)

    selected = st.selectbox(
        "Select a region",
        options=scored_df["region_name"].tolist()
    )

    region_row = scored_df[scored_df["region_name"] == selected].iloc[0]
    color = region_row["risk_color"]

    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, {color}15 0%, {color}08 100%);
                    border: 1px solid {color}40; border-left: 4px solid {color};
                    padding: 16px 18px; border-radius: 10px; margin-bottom: 20px;">
            <div style="font-size:10px; font-weight:700; color:#718096;
                        text-transform:uppercase; letter-spacing:0.06em; margin-bottom:6px;">
                Current Risk Level
            </div>
            <div style="font-size:28px; font-weight:800; color:{color};
                        letter-spacing:0.04em;">{region_row['risk_level']}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    m1, m2 = st.columns(2)
    m1.metric("Avg Demand", f"{int(region_row['avg_demand_mw']):,} MW")
    m2.metric("Avg Generation", f"{int(region_row['avg_generation_mw']):,} MW")

    m3, m4 = st.columns(2)
    m3.metric("Avg Net Balance", f"{int(region_row['avg_net_balance_mw']):+,} MW")
    m4.metric("Stress Hours", f"{region_row['stress_pct']}%")

    m5, m6 = st.columns(2)
    m5.metric("Current Streak", f"{int(region_row['stress_streak'])} hrs")
    m6.metric("Avg Ratio", f"{region_row['avg_balance_ratio']:.3f}")

    trend = region_row["trend"]
    trend_icon = TREND_ICONS[trend]
    trend_color = TREND_COLORS[trend]
    st.markdown(
        f"""
        <div style="background: {trend_color}15; border: 1px solid {trend_color}40;
                    border-left: 4px solid {trend_color}; padding: 10px 14px;
                    border-radius: 8px; margin-top: 12px;">
            <div style="font-size:10px; font-weight:700; color:#718096;
                        text-transform:uppercase; letter-spacing:0.06em; margin-bottom:4px;">
                6-Hour Trend
            </div>
            <div style="font-size:18px; font-weight:800; color:{trend_color};">
                {trend_icon} {trend}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown("<br>", unsafe_allow_html=True)

# --- Time series chart ---
st.markdown(f'<div class="section-label">Demand vs. Generation — {selected}</div>', unsafe_allow_html=True)

region_code = scored_df[scored_df["region_name"] == selected]["region"].iloc[0]
ts = time_series_df[time_series_df["region"] == region_code].copy()
ts = ts.set_index("timestamp")[["demand_mw", "generation_mw"]].rename(
    columns={"demand_mw": "Demand (MW)", "generation_mw": "Generation (MW)"}
)

st.line_chart(ts, height=260, color=["#e53e3e", "#2d3561"])

st.markdown("<br>", unsafe_allow_html=True)

# --- Full risk table ---
st.markdown('<div class="section-label">Full Risk Summary</div>', unsafe_allow_html=True)

display_cols = ["region_name", "risk_level", "trend", "avg_net_balance_mw",
                "avg_balance_ratio", "stress_pct", "stress_streak", "last_updated"]

st.dataframe(
    scored_df[display_cols].rename(columns={
        "region_name": "Region",
        "risk_level": "Risk Level",
        "trend": "Trend (6h)",
        "avg_net_balance_mw": "Avg Balance (MW)",
        "avg_balance_ratio": "Avg Ratio",
        "stress_pct": "Stress %",
        "stress_streak": "Current Streak (hrs)",
        "last_updated": "Last Updated"
    }),
    use_container_width=True,
    hide_index=True
)

# --- Ask the Grid Analyst ---
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("""
<div style="background: linear-gradient(90deg, #1a1f36 0%, #2d3561 60%, #3d4f8a 100%);
            height: 3px; border-radius: 2px; margin-bottom: 24px;"></div>
""", unsafe_allow_html=True)
st.markdown('<div class="section-label">Ask the Grid Analyst</div>', unsafe_allow_html=True)

question = st.text_input(
    "Ask a question about current grid conditions",
    placeholder="e.g. Which regions are deteriorating right now? How does California compare to Texas?",
    label_visibility="collapsed"
)

if question:
    with st.spinner("Querying data..."):
        answer = grid_ask(question)
    st.markdown(
        f"""
        <div style="background:#ffffff; border:1px solid #dce3f0; border-left:4px solid #2d3561;
                    border-radius:10px; padding:20px 24px;
                    box-shadow:0 1px 6px rgba(0,0,0,0.04); font-size:14px;
                    color:#1a1f36; line-height:1.7; margin-top:12px;">
            {answer}
        </div>
        <div style="font-size:11px; color:#a0aec0; margin-top:8px; padding-left:4px;">
            Generated by Claude · All figures sourced directly from EIA data via tool calls · No inference
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown("<br>", unsafe_allow_html=True)

# --- Key Definitions ---
st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div class="section-label">Reference</div>', unsafe_allow_html=True)

with st.expander("Key Definitions & Methodology"):
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("""
**Metrics**

**Net Balance (MW)**
The difference between generation and demand at a given hour.
A positive value means the region is producing more than it consumes (surplus).
A negative value means it is importing power from neighboring regions (deficit).

**Balance Ratio**
Demand divided by generation. A ratio above 1.0 indicates demand exceeds local generation.
Values significantly above 1.0 represent structural dependence on imported power.

**Rolling Avg Ratio**
A 24-hour moving average of the balance ratio. Smooths out hourly spikes to reveal
whether grid stress is building or easing over time.

**Stress Hour**
Any hour where the balance ratio is ≥ 0.95 — i.e., demand is at least 95% of generation.
This threshold flags periods of tight supply margin.

**Stress Streak**
The number of consecutive stress hours currently active in a region.
Long streaks indicate sustained grid pressure, not just isolated spikes.

**6-Hour Trend**
The direction a region is moving over the last 6 hours, based on the change in
balance ratio (demand ÷ generation). A delta above +0.05 signals deterioration;
below −0.05 signals recovery; within ±0.05 is stable. A HIGH region that is
DETERIORATING is operationally distinct from one that is HIGH and STABLE.
        """)

    with col_b:
        st.markdown("""
**Risk Levels**

🟣 **CRITICAL**
Demand chronically and significantly exceeds local generation (avg ratio ≥ 1.4)
with a sustained active stress streak (≥ 24 hrs), or ratio ≥ 1.8 regardless of streak.
The region is structurally dependent on imports to remain operational.

🔴 **HIGH**
Demand regularly meets or exceeds generation (ratio ≥ 1.0) with stress occurring
in ≥ 90% of observed hours, or an extended streak (≥ 48 hrs) with frequent stress.
Resilience is limited — any supply disruption poses immediate risk.

🟠 **MEDIUM**
Intermittent stress with moderate imbalance. Stress occurs in 35–89% of hours
or the balance ratio approaches 0.97. Manageable under normal conditions
but vulnerable during peak demand or generation shortfalls.

🟢 **LOW**
Healthy surplus with infrequent stress (< 35% of hours) and no sustained streak.
Region has sufficient generation capacity and acts as a net exporter.

---
**Data Source:** U.S. Energy Information Administration (EIA) Open Data API v2.
Balancing authority hourly demand and net generation data, rolling 7-day window.
        """)

# --- Footer ---
st.markdown("""
<div style="text-align:center; color:#a0aec0; font-size:11px; margin-top:40px;
            padding-top:20px; border-top: 1px solid #edf2f7; font-weight:500;">
    U.S. Energy Grid Risk Monitor &nbsp;·&nbsp; Data: EIA Open Data API v2
    &nbsp;·&nbsp; Refreshes hourly
</div>
""", unsafe_allow_html=True)
