import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ingest import fetch_all_regions

print("=" * 60)
print("FETCHING DATA...")
print("=" * 60)
df = fetch_all_regions(days_back=7)

print("\n" + "=" * 60)
print("BASIC SHAPE")
print("=" * 60)
print(f"Rows:    {len(df)}")
print(f"Columns: {list(df.columns)}")

print("\n" + "=" * 60)
print("REGIONS IN DATASET")
print("=" * 60)
region_counts = df.groupby(["region", "region_name"]).size().reset_index(name="record_count")
print(region_counts.to_string(index=False))

print("\n" + "=" * 60)
print("TIME RANGE")
print("=" * 60)
print(f"Earliest: {df['timestamp'].min()}")
print(f"Latest:   {df['timestamp'].max()}")
print(f"Span:     {df['timestamp'].max() - df['timestamp'].min()}")

print("\n" + "=" * 60)
print("DEMAND (MW) STATS BY REGION")
print("=" * 60)
demand_stats = df.groupby("region_name")["demand_mw"].agg(["min", "mean", "max"]).round(0)
demand_stats.columns = ["min_mw", "avg_mw", "max_mw"]
print(demand_stats.to_string())

print("\n" + "=" * 60)
print("GENERATION (MW) STATS BY REGION")
print("=" * 60)
gen_stats = df.groupby("region_name")["generation_mw"].agg(["min", "mean", "max"]).round(0)
gen_stats.columns = ["min_mw", "avg_mw", "max_mw"]
print(gen_stats.to_string())

print("\n" + "=" * 60)
print("NET BALANCE (Generation - Demand) BY REGION")
print("=" * 60)
df["net_balance_mw"] = df["generation_mw"] - df["demand_mw"]
balance = df.groupby("region_name")["net_balance_mw"].agg(["min", "mean", "max"]).round(0)
balance.columns = ["min_mw", "avg_mw", "max_mw"]
print(balance.to_string())
print("\nNegative avg = region is consistently importing more than it generates")

print("\n" + "=" * 60)
print("MISSING VALUES")
print("=" * 60)
print(df[["demand_mw", "generation_mw"]].isnull().sum())

print("\n" + "=" * 60)
print("SAMPLE ROWS")
print("=" * 60)
print(df.sample(5).to_string(index=False))
