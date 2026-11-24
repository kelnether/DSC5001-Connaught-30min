"""Clean lane records and build five-minute detector panels. / 清洗车道记录并生成五分钟检测点面板。"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from .artifacts import sha256_file, write_json

logger = logging.getLogger(__name__)


def build_panel(root, config):
    """Aggregate valid lane observations within each detector. / 汇总同一检测点的合格车道记录。"""
    input_path = root / config["input"]
    if not input_path.is_file():
        raise FileNotFoundError(f"Missing {input_path}. See README.md for preparation. / 缺少输入数据，请参阅 README.md 中的数据准备步骤。")
    logger.info("Reading lane records from %s for vehicle-weighted detector speeds (coverage threshold %.0f%%)."
                " / 读取车道记录，按覆盖率门槛汇总五分钟点位均速。",
                input_path, 100 * config["min_coverage"])
    meta = pd.read_csv(root / config["detectors"], dtype={"detector_id": str})
    if meta["detector_id"].duplicated().any():
        raise ValueError("Detector IDs in the reference table must be unique. / 点位表中的检测器 ID 必须唯一。")
    raw = pd.read_csv(input_path, dtype={"detector_id": str, "archive_day": str})
    start, end = (pd.Timestamp(config[k]) for k in ("start", "end_exclusive"))
    raw["timestamp"] = pd.to_datetime(raw["date"] + " " + raw["period_from"], errors="coerce")
    raw["period_end"] = pd.to_datetime(raw["date"] + " " + raw["period_to"], errors="coerce")
    raw.loc[raw["period_end"] <= raw["timestamp"], "period_end"] += pd.Timedelta(days=1)
    in_window = raw["timestamp"].ge(start) & raw["timestamp"].lt(end)
    window = raw.loc[in_window].sort_values(["archive_day", "snapshot"], kind="stable")
    unknown = set(window["detector_id"]) - set(meta["detector_id"])
    if unknown:
        raise ValueError(f"Input has unmapped detectors: {sorted(unknown)}. / 输入含未登记的检测器。")
    dedup = window.drop_duplicates(["timestamp", "detector_id", "lane_id"], keep="last").copy()
    cutoff = config.get("lane_inventory_cutoff")
    inventory_source = dedup if cutoff is None else dedup.loc[dedup["timestamp"].lt(pd.Timestamp(cutoff))]
    lane_counts = inventory_source.groupby("detector_id")["lane_id"].nunique().reindex(meta["detector_id"])
    for key in ("speed", "volume", "occupancy"):
        dedup[key] = pd.to_numeric(dedup[key], errors="coerce")
    rules = {
        "valid_flag": dedup["valid"].eq("Y"),
        "speed_range": dedup["speed"].between(0, 200),
        "volume_nonnegative": dedup["volume"].ge(0),
        "occupancy_range": dedup["occupancy"].between(0, 100),
        "lane_label": dedup["lane_id"].notna(),
        "duration_30_seconds": dedup["period_end"].sub(dedup["timestamp"]).eq(pd.Timedelta(seconds=30)),
        "seconds_grid": dedup["timestamp"].dt.second.isin([0, 30]),
    }
    eligible = pd.Series(True, index=dedup.index)
    cleaning_steps = {"outside_window": len(raw) - len(window), "duplicates": len(window) - len(dedup)}
    for name, passes in rules.items():
        if cutoff is not None:
            cleaning_steps[name] = int((eligible & ~passes).sum())
        eligible &= passes
    inventory_audit = None
    if cutoff is not None:
        keys = ["detector_id", "lane_id"]
        inventory = inventory_source[keys].dropna().drop_duplicates()
        observed = dedup[keys].dropna().drop_duplicates()
        unseen = observed.merge(inventory, on=keys, how="left", indicator=True)
        unseen = unseen.loc[unseen["_merge"].eq("left_only"), keys]
        new_lane = (np.zeros(len(dedup), dtype=bool) if unseen.empty else
                    pd.MultiIndex.from_frame(dedup[keys]).isin(pd.MultiIndex.from_frame(unseen)))
        inventory_audit = {
            "cutoff_exclusive": cutoff,
            "known": {str(site): sorted(part["lane_id"].tolist())
                      for site, part in inventory.groupby("detector_id")},
            "later_only": unseen.to_dict("records"),
            "later_only_rows": int(new_lane.sum()),
            "later_only_valid_rows_excluded": int((eligible & new_lane).sum()),
        }
        eligible &= ~new_lane
        cleaning_steps["later_only_valid_lanes"] = inventory_audit["later_only_valid_rows_excluded"]
    clean = dedup.loc[eligible].copy()
    clean["bin_end"] = clean["timestamp"].dt.floor("5min") + pd.Timedelta(minutes=5)
    # Weight each lane's 30-second speed by its vehicle count. / 以车辆数加权同一点位各车道的 30 秒车速。
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
        raise ValueError("Coverage exceeds 100%. Check lane inventory and snapshot deduplication. / 覆盖率超过 100%，请核对车道清单及快照去重。")
    panel["speed"] = panel["weighted_speed"] / panel["vehicles"].where(panel["vehicles"].gt(0))
    panel["flow_per_lane_hour"] = panel["vehicles"] * 120 / panel["valid_records"].where(panel["valid_records"].gt(0))
    panel.loc[panel["coverage"].lt(config["min_coverage"]), ["speed", "flow_per_lane_hour", "occupancy"]] = np.nan
    panel = panel.drop(columns="weighted_speed").merge(meta, on="detector_id", validate="many_to_one")
    if not len(panel) or not panel["speed"].notna().any():
        raise ValueError("No usable speed bins. Check archive dates and coverage. / 缺少可用车速窗口，请核对归档日期及覆盖率。")
    raw_summary = {
        "input_rows": len(raw), "missing_timestamps": int(raw["timestamp"].isna().sum()),
        "out_of_window_or_invalid_time": len(raw) - len(window), "duplicate_rows": len(window) - len(dedup),
        "invalid_or_offline_rows": len(dedup) - len(clean), "valid_lane_rows": len(clean),
        "registered_detectors": len(meta), "detectors_with_rows": len(lane_counts.dropna()),
        "usable_detectors": int(panel.loc[panel["speed"].notna(), "detector_id"].nunique()),
        "grid_rows": len(panel), "usable_bins": int(panel["speed"].notna().sum()),
        "sha256": sha256_file(input_path),
    }
    if inventory_audit is not None:
        raw_summary["lane_inventory"] = inventory_audit
        raw_summary["sequential_lane_row_exclusions"] = cleaning_steps
    coverage = detector_coverage(panel)
    logger.info("Cleaned lane records: %s input, %s valid, %s/%s detectors and %s/%s five-minute bins usable."
                " / 清洗完成，统计输入、有效记录、可用检测点及时间窗。",
                f"{len(raw):,}", f"{len(clean):,}", raw_summary["usable_detectors"], len(meta),
                f"{raw_summary['usable_bins']:,}", f"{len(panel):,}")
    return panel, coverage, raw_summary


def detector_coverage(panel):
    """Summarize usable speed bins by detector. / 汇总各点位的可用车速窗。"""
    coverage = panel.groupby(["detector_id", "road_group"], as_index=False).agg(
        expected_bins=("bin_end", "size"), usable_bins=("speed", "count"), mean_lane_coverage=("coverage", "mean"))
    coverage["usable_share"] = coverage["usable_bins"] / coverage["expected_bins"]
    return coverage


def daily_coverage(panel):
    day = (panel["bin_end"] - pd.Timedelta(seconds=1)).dt.strftime("%Y-%m-%d")
    table = panel.assign(date=day).groupby(["date", "detector_id", "road_group"], as_index=False).agg(
        expected_bins=("bin_end", "size"), usable_bins=("speed", "count"), mean_lane_coverage=("coverage", "mean"))
    table["usable_share"] = table["usable_bins"] / table["expected_bins"]
    return table

def write_coverage_outputs(panel, coverage, quality, output):
    """Write data quality and coverage outputs. / 保存质量审计与覆盖率。"""
    coverage.to_csv(output / "detector_coverage.csv", index=False)
    daily_coverage(panel).to_csv(output / "daily_coverage.csv", index=False)
    write_json(output / "data_quality.json", quality)
    logger.info("Saved detector_coverage.csv, daily_coverage.csv and data_quality.json to %s."
                " / 已保存点位覆盖率、逐日覆盖率及数据质量统计。", output)


def audit_coverage(root, config, output_dir=None):
    """Clean data and write coverage outputs. / 清洗数据并输出覆盖率。"""
    output = Path(output_dir).resolve() if output_dir else root / config["output"]
    output.mkdir(parents=True, exist_ok=True)
    panel, coverage, quality = build_panel(root, config)
    write_coverage_outputs(panel, coverage, quality, output)
    return output
