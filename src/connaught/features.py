"""特征、预测标签与时序切分。 / Features, forecast labels and chronological splits."""

import numpy as np
import pandas as pd


SPEED_FEATURES = ["speed", "speed_lag_5", "speed_lag_10", "target_sin", "target_cos", "target_weekend"]
# 车道数用于覆盖率，速度差试验收益不稳定。 / Lane count supports coverage. Speed-gap gains were inconsistent.
FULL_FEATURES = SPEED_FEATURES + ["flow_per_lane_hour", "occupancy"]


def make_examples(panel, config):
    """用同一检测点的未来 5 分钟均速作标签。 / Label each row with the future five-minute mean speed at the same detector."""
    frame = panel.sort_values(["detector_id", "bin_end"]).copy().rename(columns={"bin_end": "origin"})
    offsets = frame.groupby("detector_id")["origin"].diff().dropna()
    if not offsets.eq(pd.Timedelta(minutes=5)).all():
        raise ValueError("Expected complete five-minute grids for every detector.")
    speeds = frame.groupby("detector_id")["speed"]
    frame["speed_lag_5"] = speeds.shift(1)
    frame["speed_lag_10"] = speeds.shift(2)
    h = config["horizon_minutes"]
    frame["target_end"] = frame["origin"] + pd.Timedelta(minutes=h)
    frame["target_speed"] = speeds.shift(-(h // 5))
    minute = frame["target_end"].dt.hour * 60 + frame["target_end"].dt.minute
    frame["target_slot"] = minute // 5
    frame["target_hour"] = minute // 60
    frame["target_dow"] = frame["target_end"].dt.dayofweek
    frame["target_weekend"] = frame["target_dow"].ge(5).astype(int)
    frame["target_sin"] = np.sin(2 * np.pi * minute / 1440)
    frame["target_cos"] = np.cos(2 * np.pi * minute / 1440)
    frame["target_day"] = (frame["target_end"] - pd.Timedelta(seconds=1)).dt.strftime("%Y-%m-%d")
    frame["time_group"] = np.select(
        [frame["target_hour"].between(7, 9), frame["target_hour"].between(17, 19)],
        ["07:00–09:59", "17:00–19:59"], default="Other")
    return frame.dropna(subset=FULL_FEATURES + ["target_speed"]).reset_index(drop=True)


def split_at(examples, start, end):
    boundary, last = pd.Timestamp(start), pd.Timestamp(end)
    train = examples.loc[examples["target_end"].le(boundary)].copy()
    test = examples.loc[examples["origin"].ge(boundary) & examples["target_end"].le(last)].copy()
    if train.empty or test.empty:
        raise ValueError(f"Insufficient eligible rows for split at {boundary}.")
    if not train["target_end"].max() <= test["origin"].min():
        raise ValueError("Target leakage across split boundary.")
    return train, test
