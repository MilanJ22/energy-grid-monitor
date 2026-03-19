import pandas as pd


def transform(df: pd.DataFrame) -> pd.DataFrame:
    """
    Takes raw ingested data and derives operational fields.
    Input:  region, region_name, timestamp, demand_mw, generation_mw
    Output: all of the above + net_balance_mw, balance_ratio, rolling_avg_ratio, is_stress_hour
    """
    df = df.copy()
    df = df.sort_values(["region", "timestamp"]).reset_index(drop=True)

    # 1. Net balance — positive means surplus, negative means deficit
    df["net_balance_mw"] = df["generation_mw"] - df["demand_mw"]

    # 2. Balance ratio — demand as a fraction of generation
    #    > 1.0 means demand exceeds generation (deficit)
    #    Clip generation at 1 to avoid division by zero
    df["balance_ratio"] = df["demand_mw"] / df["generation_mw"].clip(lower=1)

    # 3. Rolling 24-hour average ratio per region
    #    Shows whether stress is building or easing over time
    df["rolling_avg_ratio"] = (
        df.groupby("region")["balance_ratio"]
        .transform(lambda x: x.rolling(window=24, min_periods=1).mean())
    )

    # 4. Stress hour flag — demand is >= 95% of generation
    df["is_stress_hour"] = df["balance_ratio"] >= 0.95

    # 5. Stress streak — how many consecutive stress hours in this region
    df["stress_streak"] = (
        df.groupby("region")["is_stress_hour"]
        .transform(lambda x: x * (x.groupby((x != x.shift()).cumsum()).cumcount() + 1))
    )

    # Round derived floats for readability
    df["balance_ratio"] = df["balance_ratio"].round(4)
    df["rolling_avg_ratio"] = df["rolling_avg_ratio"].round(4)

    return df


def summarize_by_region(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregates the transformed data to one row per region.
    Used by the risk scorer and dashboard to get the current state of each region.
    """
    latest = df.sort_values("timestamp").groupby("region").last().reset_index()

    summary = df.groupby(["region", "region_name"]).agg(
        avg_demand_mw=("demand_mw", "mean"),
        avg_generation_mw=("generation_mw", "mean"),
        avg_net_balance_mw=("net_balance_mw", "mean"),
        avg_balance_ratio=("balance_ratio", "mean"),
        max_balance_ratio=("balance_ratio", "max"),
        stress_hours=("is_stress_hour", "sum"),
        total_hours=("is_stress_hour", "count"),
    ).reset_index()

    summary["stress_pct"] = (summary["stress_hours"] / summary["total_hours"] * 100).round(1)

    # Attach the latest rolling avg ratio and stress streak from the most recent hour
    latest_cols = latest[["region", "rolling_avg_ratio", "stress_streak", "timestamp"]]
    summary = summary.merge(latest_cols, on="region", how="left")
    summary = summary.rename(columns={"timestamp": "last_updated"})

    summary = summary.round({"avg_demand_mw": 0, "avg_generation_mw": 0, "avg_net_balance_mw": 0,
                              "avg_balance_ratio": 4, "max_balance_ratio": 4})

    return summary


if __name__ == "__main__":
    from src.ingest import fetch_all_regions

    raw = fetch_all_regions(days_back=7)
    transformed = transform(raw)
    summary = summarize_by_region(transformed)

    print("TRANSFORMED DATA (sample):")
    print(transformed[["region", "timestamp", "net_balance_mw", "balance_ratio",
                        "rolling_avg_ratio", "is_stress_hour", "stress_streak"]].head(20).to_string(index=False))

    print("\nREGION SUMMARY:")
    print(summary[["region_name", "avg_net_balance_mw", "avg_balance_ratio",
                   "max_balance_ratio", "stress_hours", "stress_pct",
                   "stress_streak", "last_updated"]].to_string(index=False))
