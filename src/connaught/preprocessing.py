"""清洗车道记录并生成五分钟检测点面板。 / Clean lane records and build five-minute detector panels."""

from pathlib import Path

import numpy as np
import pandas as pd

from .artifacts import sha256_file, write_json


def build_panel(root, config):
    """汇总同一检测点的合格车道记录。 / Aggregate valid lane observations within each detector."""
    input_path = root / config["input"]
    if not input_path.is_file():
        raise FileNotFoundError(f"Missing {input_path}. See README.md for preparation.")
    meta = pd.read_csv(root / config["detectors"], dtype={"detector_id": str})
    if meta["detector_id"].duplicated().any():
        raise ValueError("Detector IDs in the reference table must be unique.")
    raw = pd.read_csv(input_path, dtype={"detector_id": str, "archive_day": str})
    start, end = (pd.Timestamp(config[k]) for k in ("start", "end_exclusive"))
    raw["timestamp"] = pd.to_datetime(raw["date"] + " " + raw["period_from"], errors="coerce")
    raw["period_end"] = pd.to_datetime(raw["date"] + " " + raw["period_to"], errors="coerce")
    raw.loc[raw["period_end"] <= raw["timestamp"], "period_end"] += pd.Timedelta(days=1)
    in_window = raw["timestamp"].ge(start) & raw["timestamp"].lt(end)
    window = raw.loc[in_window].sort_values(["archive_day", "snapshot"], kind="stable")
    unknown = set(window["detector_id"]) - set(meta["detector_id"])
    if unknown:
        raise ValueError(f"Input has unmapped detectors: {sorted(unknown)}")
    dedup = window.drop_duplicates(["timestamp", "detector_id", "lane_id"], keep="last").copy()
    lane_counts = dedup.groupby("detector_id")["lane_id"].nunique().reindex(meta["detector_id"])
    for key in ("speed", "volume", "occupancy"):
        dedup[key] = pd.to_numeric(dedup[key], errors="coerce")
    eligible = (dedup["valid"].eq("Y") & dedup["speed"].between(0, 200) &
                dedup["volume"].ge(0) & dedup["occupancy"].between(0, 100) &
                dedup["lane_id"].notna() &
                dedup["period_end"].sub(dedup["timestamp"]).eq(pd.Timedelta(seconds=30)) &
                dedup["timestamp"].dt.second.isin([0, 30]))
    clean = dedup.loc[eligible].copy()
    clean["bin_end"] = clean["timestamp"].dt.floor("5min") + pd.Timedelta(minutes=5)
    # 以车辆数加权同一点位各车道的 30 秒车速。 / Weight each lane's 30-second speed by its vehicle count.
    clean["weighted_speed"] = clean["speed"] * clean["volume"]
    agg = clean.groupby(["detector_id", "bin_end"]).agg(
        valid_records=("speed", "size"), vehicles=("volume", "sum"),
        weighted_speed=("weighted_speed", "sum"), occupancy=("occupancy", "mean"),
    )
    time_grid = pd.date_range(start + pd.Timedelta(minutes=5), end, freq="5min")
    grid = pd.MultiIndex.from_product([meta["detector_id"], time_grid], names=["detector_id", "bin_end"])
    panel = agg.reindex(grid).reset_index()
    panel["expected_lanes"] = panel["detector_id"].map(lane_counts)
    panel["valid_records"] = panel["valid_records"].fillna(0).astype(int)
    panel["coverage"] = (panel["valid_records"] / (10 * panel["expected_lanes"])).fillna(0)
    if (panel["coverage"] > 1 + 1e-10).any():
        raise ValueError("Coverage > 1, check lane inventory and snapshot deduplication.")
    panel["speed"] = panel["weighted_speed"] / panel["vehicles"].where(panel["vehicles"].gt(0))
    panel["flow_per_lane_hour"] = panel["vehicles"] * 120 / panel["valid_records"].where(panel["valid_records"].gt(0))
    panel.loc[panel["coverage"].lt(config["min_coverage"]), ["speed", "flow_per_lane_hour", "occupancy"]] = np.nan
    panel = panel.drop(columns="weighted_speed").merge(meta, on="detector_id", validate="many_to_one")
    if not len(panel) or not panel["speed"].notna().any():
        raise ValueError("No usable speed bins. Check archive dates and coverage.")
    raw_summary = {
        "input_rows": len(raw), "missing_timestamps": int(raw["timestamp"].isna().sum()),
        "out_of_window_or_invalid_time": len(raw) - len(window), "duplicate_rows": len(window) - len(dedup),
        "invalid_or_offline_rows": len(dedup) - len(clean), "valid_lane_rows": len(clean),
        "registered_detectors": len(meta), "detectors_with_rows": len(lane_counts.dropna()),
        "usable_detectors": int(panel.loc[panel["speed"].notna(), "detector_id"].nunique()),
        "grid_rows": len(panel), "usable_bins": int(panel["speed"].notna().sum()),
        "sha256": sha256_file(input_path),
    }
    coverage = panel.groupby(["detector_id", "road_group"], as_index=False).agg(
        expected_bins=("bin_end", "size"), usable_bins=("speed", "count"), mean_lane_coverage=("coverage", "mean"))
    coverage["usable_share"] = coverage["usable_bins"] / coverage["expected_bins"]
    return panel, coverage, raw_summary


def daily_coverage(panel):
    day = (panel["bin_end"] - pd.Timedelta(seconds=1)).dt.strftime("%Y-%m-%d")
    table = panel.assign(date=day).groupby(["date", "detector_id", "road_group"], as_index=False).agg(
        expected_bins=("bin_end", "size"), usable_bins=("speed", "count"), mean_lane_coverage=("coverage", "mean"))
    table["usable_share"] = table["usable_bins"] / table["expected_bins"]
    return table

def write_coverage_outputs(panel, coverage, quality, output):
    """保存质量审计与覆盖率。 / Write data quality and coverage outputs."""
    coverage.to_csv(output / "detector_coverage.csv", index=False)
    daily_coverage(panel).to_csv(output / "daily_coverage.csv", index=False)
    write_json(output / "data_quality.json", quality)


def audit_coverage(root, config, output_dir=None):
    """清洗数据并输出覆盖率。 / Clean data and write coverage outputs."""
    output = Path(output_dir).resolve() if output_dir else root / config["output"]
    output.mkdir(parents=True, exist_ok=True)
    panel, coverage, quality = build_panel(root, config)
    write_coverage_outputs(panel, coverage, quality, output)
    return output
