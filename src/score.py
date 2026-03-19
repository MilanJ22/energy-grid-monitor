import pandas as pd


# Risk level labels and their numeric rank (used for sorting/coloring in dashboard)
RISK_LEVELS = {
    "LOW": 0,
    "MEDIUM": 1,
    "HIGH": 2,
    "CRITICAL": 3,
}

RISK_COLORS = {
    "LOW": "#2ecc71",       # green
    "MEDIUM": "#f39c12",    # orange
    "HIGH": "#e74c3c",      # red
    "CRITICAL": "#8e44ad",  # purple
}


def score_region(row: pd.Series) -> str:
    """
    Assigns a risk level to a region based on three signals:
      1. avg_balance_ratio     — chronic stress (structural importer?)
      2. stress_pct            — how often is the region under stress?
      3. stress_streak         — how many consecutive stress hours right now?

    Scoring logic:
      CRITICAL — chronic high importer AND currently in a long stress streak
      HIGH     — consistently near or over capacity
      MEDIUM   — intermittent stress or moderate imbalance
      LOW      — healthy surplus, rarely stressed
    """
    ratio = row["avg_balance_ratio"]
    stress_pct = row["stress_pct"]
    streak = row["stress_streak"]

    # CRITICAL: demand consistently far exceeds generation AND long active streak
    if ratio >= 1.4 and streak >= 24:
        return "CRITICAL"

    # CRITICAL: extreme chronic importer regardless of streak
    if ratio >= 1.8:
        return "CRITICAL"

    # HIGH: demand regularly meets or exceeds generation
    if ratio >= 1.0 and stress_pct >= 90:
        return "HIGH"

    # HIGH: long active stress streak even if avg ratio is moderate
    if streak >= 48 and stress_pct >= 80:
        return "HIGH"

    # MEDIUM: frequent stress but not chronic, or active streak with moderate stress
    if stress_pct >= 35 or ratio >= 0.97 or (streak >= 10 and stress_pct >= 20):
        return "MEDIUM"

    # LOW: healthy surplus, infrequent stress
    return "LOW"


def score(summary_df: pd.DataFrame) -> pd.DataFrame:
    """
    Takes the region summary from transform.summarize_by_region()
    and appends risk_level, risk_rank, and risk_color columns.
    Returns the scored summary sorted by risk (most critical first).
    """
    df = summary_df.copy()

    df["risk_level"] = df.apply(score_region, axis=1)
    df["risk_rank"] = df["risk_level"].map(RISK_LEVELS)
    df["risk_color"] = df["risk_level"].map(RISK_COLORS)

    df = df.sort_values("risk_rank", ascending=False).reset_index(drop=True)

    return df


def print_risk_report(scored_df: pd.DataFrame) -> None:
    """Prints a human-readable risk report to the console."""
    print("\n" + "=" * 65)
    print("U.S. ENERGY GRID RISK REPORT")
    print("=" * 65)

    for _, row in scored_df.iterrows():
        print(f"\n[{row['risk_level']}] {row['region_name']}")
        print(f"  Avg balance ratio : {row['avg_balance_ratio']:.4f}  (>1.0 = deficit)")
        print(f"  Stress hours      : {int(row['stress_hours'])}/{int(row['total_hours'])} ({row['stress_pct']}%)")
        print(f"  Current streak    : {int(row['stress_streak'])} consecutive stress hours")
        print(f"  Avg net balance   : {int(row['avg_net_balance_mw']):+,} MW")
        print(f"  Last updated      : {row['last_updated']}")

    print("\n" + "=" * 65)
    risk_counts = scored_df["risk_level"].value_counts()
    for level in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        count = risk_counts.get(level, 0)
        print(f"  {level}: {count} region(s)")
    print("=" * 65)


if __name__ == "__main__":
    from src.ingest import fetch_all_regions
    from src.transform import transform, summarize_by_region

    raw = fetch_all_regions(days_back=7)
    transformed = transform(raw)
    summary = summarize_by_region(transformed)
    scored = score(summary)

    print_risk_report(scored)
