import duckdb
import pandas as pd
from pathlib import Path

DB_PATH = Path("data/grid_monitor.db")


def get_connection() -> duckdb.DuckDBPyConnection:
    """Returns a connection to the local DuckDB database."""
    DB_PATH.parent.mkdir(exist_ok=True)
    return duckdb.connect(str(DB_PATH))


def init_db() -> None:
    """
    Creates the two core tables if they don't already exist.
      - time_series : full hourly records for every region (transformed data)
      - region_scores: latest scored summary, one row per region
    """
    con = get_connection()

    con.execute("""
        CREATE TABLE IF NOT EXISTS time_series (
            region            VARCHAR,
            region_name       VARCHAR,
            timestamp         TIMESTAMP,
            demand_mw         DOUBLE,
            generation_mw     DOUBLE,
            net_balance_mw    DOUBLE,
            balance_ratio     DOUBLE,
            rolling_avg_ratio DOUBLE,
            is_stress_hour    BOOLEAN,
            stress_streak     INTEGER,
            PRIMARY KEY (region, timestamp)
        )
    """)

    con.execute("""
        CREATE OR REPLACE TABLE region_scores (
            region              VARCHAR PRIMARY KEY,
            region_name         VARCHAR,
            avg_demand_mw       DOUBLE,
            avg_generation_mw   DOUBLE,
            avg_net_balance_mw  DOUBLE,
            avg_balance_ratio   DOUBLE,
            max_balance_ratio   DOUBLE,
            stress_hours        INTEGER,
            total_hours         INTEGER,
            stress_pct          DOUBLE,
            rolling_avg_ratio   DOUBLE,
            stress_streak       INTEGER,
            last_updated        TIMESTAMP,
            risk_level          VARCHAR,
            risk_rank           INTEGER,
            risk_color          VARCHAR,
            trend               VARCHAR
        )
    """)

    con.close()
    print(f"Database initialized at {DB_PATH}")


def save_time_series(df: pd.DataFrame) -> None:
    """
    Inserts transformed hourly records into time_series.
    Skips duplicates using INSERT OR IGNORE on (region, timestamp).
    """
    con = get_connection()

    con.execute("""
        INSERT OR IGNORE INTO time_series
        SELECT
            region, region_name, timestamp, demand_mw, generation_mw,
            net_balance_mw, balance_ratio, rolling_avg_ratio,
            is_stress_hour, stress_streak
        FROM df
    """)

    count = con.execute("SELECT COUNT(*) FROM time_series").fetchone()[0]
    con.close()
    print(f"time_series table: {count} total records")


def save_region_scores(df: pd.DataFrame) -> None:
    """
    Upserts the scored region summary into region_scores.
    Replaces existing rows so the table always reflects the latest run.
    """
    con = get_connection()

    con.execute("DELETE FROM region_scores")
    con.execute("""
        INSERT INTO region_scores
        SELECT
            region, region_name, avg_demand_mw, avg_generation_mw,
            avg_net_balance_mw, avg_balance_ratio, max_balance_ratio,
            stress_hours, total_hours, stress_pct, rolling_avg_ratio,
            stress_streak, last_updated, risk_level, risk_rank, risk_color, trend
        FROM df
    """)

    con.close()
    print(f"region_scores table: {len(df)} regions saved")


def load_time_series(region: str = None) -> pd.DataFrame:
    """Loads time series data, optionally filtered by region."""
    con = get_connection()
    if region:
        df = con.execute(
            "SELECT * FROM time_series WHERE region = ? ORDER BY timestamp",
            [region]
        ).df()
    else:
        df = con.execute("SELECT * FROM time_series ORDER BY region, timestamp").df()
    con.close()
    return df


def load_region_scores() -> pd.DataFrame:
    """Loads the latest scored region summary, sorted by risk (most critical first)."""
    con = get_connection()
    df = con.execute("SELECT * FROM region_scores ORDER BY risk_rank DESC").df()
    con.close()
    return df


if __name__ == "__main__":
    from src.ingest import fetch_all_regions
    from src.transform import transform, summarize_by_region
    from src.score import score

    print("Running full pipeline...")
    raw = fetch_all_regions(days_back=7)
    transformed = transform(raw)
    summary = summarize_by_region(transformed)
    scored = score(summary, transformed)

    init_db()
    save_time_series(transformed)
    save_region_scores(scored)

    print("\nVerifying stored data:")
    print(load_region_scores()[["region_name", "risk_level", "avg_net_balance_mw", "stress_pct"]])
