"""Error metrics, subgroups, paired ablation and day resampling. / 误差、分组、配对消融和按日重采样。"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MODEL_NAMES = ["persistence", "historical", "ridge_speed_only", "ridge_full", "random_forest"]
MODEL_DISPLAY = {
    "persistence": "Persistence", "historical": "Historical", "ridge_speed_only": "Ridge (speed only)",
    "ridge_full": "Ridge (full)", "random_forest": "Random Forest", "ols": "OLS (full)",
}


def evaluate(true, prediction):
    delta = np.asarray(prediction) - np.asarray(true)
    return {"n": len(delta), "mae": float(np.mean(np.abs(delta))),
            "rmse": float(np.sqrt(np.mean(delta ** 2))), "bias": float(np.mean(delta))}


def score_table(pred, by=None, *, model_names=MODEL_NAMES):
    rows = []
    groups = pred.groupby(by, sort=True) if by else [("Overall", pred)]
    for key, part in groups:
        base = evaluate(part["target_speed"], part["persistence"])["mae"]
        for model in model_names:
            score = evaluate(part["target_speed"], part[model])
            rows.append({"group": str(key), "model": model, **score,
                         "mae_gain_vs_persistence_pct": 100 * (base - score["mae"]) / base if base else np.nan})
    scores = pd.DataFrame(rows)
    if by is None and scores["mae"].notna().any():
        best = scores.loc[scores["mae"].idxmin()]
        logger.info("Evaluated %s shared test rows across %d models. %s had the lowest MAE (%.3f km/h)."
                    " / 在共同测试样本上比较模型并给出最低 MAE。",
                    f"{len(pred):,}", len(scores), MODEL_DISPLAY[best["model"]], best["mae"])
    return scores


def paired_ablation(pred, seed):
    difference = (pred["ridge_speed_only"] - pred["target_speed"]).abs() - (pred["ridge_full"] - pred["target_speed"]).abs()
    by_day = difference.groupby(pred["target_day"]).agg(["sum", "size"])
    interval = None
    if len(by_day) >= 7:
        rng = np.random.default_rng(seed)
        picks = rng.integers(0, len(by_day), size=(2000, len(by_day)))
        sims = by_day["sum"].to_numpy()[picks].sum(axis=1) / by_day["size"].to_numpy()[picks].sum(axis=1)
        interval = [float(v) for v in np.quantile(sims, [0.025, 0.975])]
    gain = float(difference.mean())
    logger.info("Paired ablation: MAE reduction from flow and occupancy was %+.3f km/h (%d test days)."
                " / 配对消融：报告加入流量和占用率后的 MAE 改善量。",
                gain, len(by_day))
    return {"full_mae_improvement_kmh": gain, "test_days": len(by_day),
            "paired_daily_bootstrap_95pct": interval}
