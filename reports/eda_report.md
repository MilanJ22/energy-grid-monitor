# EDA Report — U.S. Energy Grid Monitor

> **Note:** This is a point-in-time snapshot. The live dashboard pulls fresh EIA data hourly — numbers there will differ from what's recorded here. This report documents the findings from the initial data pull used to calibrate the scoring thresholds.

**Date:** 2026-03-19
**Data Source:** U.S. Energy Information Administration (EIA) API v2
**Time Range:** 2026-03-12 17:00 UTC → 2026-03-19 06:00 UTC (6 days, 13 hours)
**Regions:** 9 U.S. grid balancing authorities
**Total Records:** 1,405 hourly observations

---

## Dataset Shape

| Field | Value |
|---|---|
| Rows | 1,405 |
| Columns | region, region_name, timestamp, demand_mw, generation_mw |
| Missing Values | 0 (clean) |
| Granularity | Hourly per region |

---

## Regions Covered

| Code | Region Name | Records |
|---|---|---|
| CISO | California ISO | 158 |
| MIDA | Mid-Atlantic | 155 |
| MIDW | Midwest | 155 |
| NE | New England | 155 |
| NW | Northwest | 157 |
| NY | New York | 155 |
| SE | Southeast | 156 |
| SW | Southwest | 158 |
| TEX | Texas | 156 |

---

## Demand Statistics by Region (MW)

| Region | Min | Avg | Max |
|---|---|---|---|
| California ISO | 19,079 | 25,608 | 35,135 |
| Mid-Atlantic | 79,136 | 95,021 | 117,928 |
| Midwest | 65,319 | 79,254 | 98,808 |
| New England | 9,675 | 12,941 | 16,074 |
| New York | 13,902 | 16,639 | 19,730 |
| Northwest | 34,551 | 41,791 | 46,619 |
| Southeast | 18,218 | 24,263 | 34,825 |
| Southwest | 9,491 | 12,180 | 17,698 |
| Texas | 40,699 | 49,162 | 58,963 |

---

## Generation Statistics by Region (MW)

| Region | Min | Avg | Max |
|---|---|---|---|
| California ISO | 11,133 | 17,008 | 28,908 |
| Mid-Atlantic | 83,193 | 97,170 | 119,059 |
| Midwest | 66,988 | 79,926 | 94,944 |
| New England | 9,910 | 12,758 | 16,906 |
| New York | 10,888 | 13,947 | 17,119 |
| Northwest | 39,183 | 47,088 | 51,930 |
| Southeast | 19,437 | 25,474 | 36,257 |
| Southwest | 10,073 | 13,011 | 16,786 |
| Texas | 40,427 | 49,240 | 58,995 |

---

## Net Balance by Region (Generation - Demand, MW)

> A negative value means the region imports more power than it generates.

| Region | Min | Avg | Max | Assessment |
|---|---|---|---|---|
| California ISO | -13,972 | -8,601 | -4,187 | Chronic high importer |
| New York | -3,750 | -2,692 | -1,470 | Structural deficit — always negative |
| New England | -1,212 | -183 | +1,322 | Borderline — occasional deficit |
| Texas | -839 | +78 | +1,037 | Razor thin surplus |
| Midwest | -3,864 | +672 | +3,503 | Volatile — stress spikes |
| Southwest | -1,616 | +831 | +3,304 | Moderate surplus |
| Southeast | +215 | +1,212 | +2,521 | Healthy — always positive |
| Mid-Atlantic | -240 | +2,149 | +4,932 | Healthy |
| Northwest | -87 | +5,297 | +12,440 | Strong surplus (hydro-driven) |

---

## Key Takeaways

### 1. California is the most structurally stressed region
California never generates enough to meet its own demand across the entire observation window. With an average deficit of -8,601 MW and a worst-case of -13,972 MW, it is the largest net importer on the grid. This reflects its heavy reliance on solar (zero output at night) and imported hydro/wind from the Northwest and Southwest.

### 2. New York has a permanent structural deficit
New York's net balance never goes positive — even at its best hour it still ran a -1,470 MW deficit. This makes it chronically dependent on neighboring regions, a significant operational risk if interconnections are disrupted.

### 3. Texas operates with almost zero margin
Texas (ERCOT) averages only +78 MW of surplus on a ~49,000 MW system — effectively 0.16% margin. Its worst hour hit -839 MW. This is consistent with ERCOT's well-documented history of operating near capacity limits with limited interconnection to other grids.

### 4. The Midwest shows dangerous volatility
Despite a positive average (+672 MW), the Midwest drops to -3,864 MW at its worst. High variance is a risk signal — the grid can swing from surplus to significant deficit within hours.

### 5. The Northwest is the grid's primary buffer
Driven by Pacific Northwest hydropower, the Northwest averages +5,297 MW surplus and peaks at +12,440 MW. It is the largest exporter and acts as a stabilizing force for California and the Southwest.

### 6. Data is clean — no missing values
All 1,405 records have complete demand and generation readings. No imputation required before the transform and scoring steps.

---

## Implications for Risk Scoring

These findings directly inform the scoring logic in `src/score.py`:

- **Chronic negative balance** → elevated baseline risk (CA, NY)
- **High variance / stress spikes** → intermittent risk flag (Midwest, Texas)
- **Demand/generation ratio approaching or exceeding 1.0** → critical threshold trigger
- **Consistently positive balance** → low risk baseline (Northwest, Southeast)
