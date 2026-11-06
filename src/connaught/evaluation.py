"""误差、分组、配对消融和按日重采样。 / Error metrics, subgroups, paired ablation and day resampling."""

import numpy as np
import pandas as pd


MODEL_NAMES = ["persistence", "historical", "ridge_speed_only", "ridge_full", "random_forest"]
MODEL_DISPLAY = {
    "persistence": "Persistence", "historical": "Historical", "ridge_speed_only": "Ridge (speed only)",
    "ridge_full": "Ridge (full)", "random_forest": "Random Forest",
}


def evaluate(true, prediction):
    delta = np.asarray(prediction) - np.asarray(true)
    return {"n": len(delta), "mae": float(np.mean(np.abs(delta))),
            "rmse": float(np.sqrt(np.mean(delta ** 2))), "bias": float(np.mean(delta))}


def score_table(pred, by=None):
    rows = []
    groups = pred.groupby(by, sort=True) if by else [("Overall", pred)]
    for key, part in groups:
        base = evaluate(part["target_speed"], part["persistence"])["mae"]
        for model in MODEL_NAMES:
            score = evaluate(part["target_speed"], part[model])
            rows.append({"group": str(key), "model": model, **score,
                         "mae_gain_vs_persistence_pct": 100 * (base - score["mae"]) / base if base else np.nan})
    return pd.DataFrame(rows)


def paired_ablation(pred, seed):
    difference = (pred["ridge_speed_only"] - pred["target_speed"]).abs() - (pred["ridge_full"] - pred["target_speed"]).abs()
    by_day = difference.groupby(pred["target_day"]).agg(["sum", "size"])
    interval = None
    if len(by_day) >= 7:
        rng = np.random.default_rng(seed)
        picks = rng.integers(0, len(by_day), size=(2000, len(by_day)))
        sims = by_day["sum"].to_numpy()[picks].sum(axis=1) / by_day["size"].to_numpy()[picks].sum(axis=1)
        interval = [float(v) for v in np.quantile(sims, [0.025, 0.975])]
    return {"full_mae_improvement_kmh": float(difference.mean()), "test_days": len(by_day),
            "paired_daily_bootstrap_95pct": interval}
