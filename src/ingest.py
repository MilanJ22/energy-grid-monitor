import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

EIA_API_KEY = os.getenv("EIA_API_KEY")
BASE_URL = "https://api.eia.gov/v2"

# U.S. grid regions (balancing authorities) we want to monitor
REGIONS = {
    "CISO": "California ISO",
    "MIDA": "Mid-Atlantic",
    "MIDW": "Midwest",
    "NE": "New England",
    "NY": "New York",
    "SE": "Southeast",
    "SW": "Southwest",
    "NW": "Northwest",
    "TEX": "Texas",
}


def fetch_demand(region: str, days_back: int = 7) -> pd.DataFrame:
    """
    Fetch hourly electricity demand data for a given region from the EIA API.
    Returns a cleaned DataFrame with columns: region, timestamp, demand_mw.
    """
    end = datetime.utcnow()
    start = end - timedelta(days=days_back)

    params = {
        "api_key": EIA_API_KEY,
        "frequency": "hourly",
        "data[0]": "value",
        "facets[respondent][]": region,
        "facets[type][]": "D",  # D = Demand
        "start": start.strftime("%Y-%m-%dT%H"),
        "end": end.strftime("%Y-%m-%dT%H"),
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "length": 500,
    }

    for attempt in range(3):
        response = requests.get(f"{BASE_URL}/electricity/rto/region-data/data", params=params)
        if response.status_code == 502:
            print(f"  EIA API returned 502, retrying in 5s (attempt {attempt + 1}/3)...")
            time.sleep(5)
            continue
        response.raise_for_status()
        break

    raw = response.json()
    records = raw.get("response", {}).get("data", [])

    if not records:
        print(f"  No demand data returned for {region}")
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df = df.rename(columns={"period": "timestamp", "value": "demand_mw"})
    df["region"] = region
    df["region_name"] = REGIONS.get(region, region)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["demand_mw"] = pd.to_numeric(df["demand_mw"], errors="coerce")

    return df[["region", "region_name", "timestamp", "demand_mw"]]


def fetch_generation(region: str, days_back: int = 7) -> pd.DataFrame:
    """
    Fetch hourly net generation data for a given region from the EIA API.
    Returns a cleaned DataFrame with columns: region, timestamp, generation_mw.
    """
    end = datetime.utcnow()
    start = end - timedelta(days=days_back)

    params = {
        "api_key": EIA_API_KEY,
        "frequency": "hourly",
        "data[0]": "value",
        "facets[respondent][]": region,
        "facets[type][]": "NG",  # NG = Net Generation
        "start": start.strftime("%Y-%m-%dT%H"),
        "end": end.strftime("%Y-%m-%dT%H"),
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "length": 500,
    }

    for attempt in range(3):
        response = requests.get(f"{BASE_URL}/electricity/rto/region-data/data", params=params)
        if response.status_code == 502:
            print(f"  EIA API returned 502, retrying in 5s (attempt {attempt + 1}/3)...")
            time.sleep(5)
            continue
        response.raise_for_status()
        break

    raw = response.json()
    records = raw.get("response", {}).get("data", [])

    if not records:
        print(f"  No generation data returned for {region}")
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df = df.rename(columns={"period": "timestamp", "value": "generation_mw"})
    df["region"] = region
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["generation_mw"] = pd.to_numeric(df["generation_mw"], errors="coerce")

    return df[["region", "timestamp", "generation_mw"]]


def fetch_all_regions(days_back: int = 7) -> pd.DataFrame:
    """
    Loop through all regions, fetch demand + generation, merge into one DataFrame.
    This is the main entry point for the ingestion layer.
    """
    all_data = []

    for region_code in REGIONS:
        print(f"Fetching data for {region_code}...")

        demand_df = fetch_demand(region_code, days_back)
        generation_df = fetch_generation(region_code, days_back)

        if demand_df.empty or generation_df.empty:
            print(f"  Skipping {region_code} — incomplete data")
            continue

        merged = pd.merge(demand_df, generation_df, on=["region", "timestamp"], how="inner")
        all_data.append(merged)

    if not all_data:
        raise RuntimeError("No data fetched for any region. Check your API key.")

    combined = pd.concat(all_data, ignore_index=True)
    print(f"\nIngestion complete: {len(combined)} records across {len(all_data)} regions.")
    return combined


if __name__ == "__main__":
    df = fetch_all_regions(days_back=7)
    print(df.head(20))
