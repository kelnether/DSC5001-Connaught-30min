"""Day-block uncertainty and model interpretation. / 按日分块的不确定性与模型解释。"""

import logging

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance

from .artifacts import write_json
from .features import FULL_FEATURES
from .plotting import _save_figure

logger = logging.getLogger(__name__)


def _day_intervals(values, target_days, seed):
    day = values.groupby(target_days, sort=True)
    n_days = day.ngroups
    intervals = np.full((values.shape[1], 2), np.nan)
    if n_days >= 7:
        picks = np.random.default_rng(seed).integers(0, n_days, size=(2000, n_days))
        sampled_sums = day.sum().to_numpy()[picks].sum(axis=1)
        sampled_sizes = day.size().to_numpy()[picks].sum(axis=1)
        intervals = np.quantile(sampled_sums / sampled_sizes[:, None], [0.025, 0.975], axis=0).T
    return n_days, intervals


def bootstrap_mae(predictions, models, seed):
    """Resample whole target days with shared draws across models. / 各模型使用相同的目标日期整块抽样。"""
    error = predictions[list(models)].sub(predictions["target_speed"], axis=0).abs()
    n_days, intervals = _day_intervals(error, predictions["target_day"], seed)
    return pd.DataFrame({"model": models, "test_days": n_days,
                         "mae_ci_low": intervals[:, 0], "mae_ci_high": intervals[:, 1]})


def paired_model_intervals(predictions, comparisons, seed):
    """Estimate paired MAE reductions with shared day draws. / 用共同的日期整块抽样估计配对误差下降。"""
    models = sorted({model for pair in comparisons for model in pair})
    errors = predictions[models].sub(predictions["target_speed"], axis=0).abs()
    differences = pd.concat([errors[reference] - errors[candidate]
                             for reference, candidate in comparisons], axis=1, ignore_index=True)
    n_days, intervals = _day_intervals(differences, predictions["target_day"], seed)
    return pd.DataFrame({"reference": [pair[0] for pair in comparisons],
                         "candidate": [pair[1] for pair in comparisons],
                         "test_days": n_days, "n": len(predictions),
                         "mae_reduction": differences.mean().to_numpy(),
                         "ci_low": intervals[:, 0], "ci_high": intervals[:, 1]})


def save_interpretation(forest, test, coefficients, seed, output):
    """Save test-only RF diagnostics and the Ridge coefficient chart. / 保存随机森林留出解释诊断及 Ridge 系数图。"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sample_size = min(8000, len(test))
    sample = test.sample(n=sample_size, random_state=seed)
    columns = [*FULL_FEATURES, "detector_id"]
    features = sample[columns]
    target = sample["target_speed"]
    repeats = 5
    result = permutation_importance(forest, features, target, scoring="neg_mean_absolute_error",
                                    n_repeats=repeats, random_state=seed, n_jobs=1)
    importance = pd.DataFrame({"feature": columns, "mean_mae_increase": result.importances_mean,
                               "sd_mae_increase": result.importances_std, "n": sample_size, "repeats": repeats})
    importance = importance.sort_values("mean_mae_increase", ascending=False)
    importance.to_csv(output / "rf_permutation_importance.csv", index=False)

    curves = []
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for name, unit, axis in zip(("occupancy", "flow_per_lane_hour"), ("%", "veh/lane/h"), axes, strict=True):
        grid = np.unique(np.quantile(features[name], np.linspace(.05, .95, 17)))
        modified = features.copy()
        for value in grid:
            modified[name] = value
            curves.append({"feature": name, "value": value,
                           "mean_prediction_kmh": float(forest.predict(modified).mean()), "n": sample_size})
        series = pd.DataFrame(curves)
        selected = series[series["feature"].eq(name)]
        axis.plot(selected["value"], selected["mean_prediction_kmh"], color="#11867e", marker="o", markersize=3)
        axis.set(xlabel=f"{name} ({unit})", ylabel="Mean predicted speed (km/h)", title=name)
        axis.grid(alpha=.25)
    fig.suptitle("Random Forest partial dependence (held-out sample)")
    pd.DataFrame(curves).to_csv(output / "rf_partial_dependence.csv", index=False)
    folder = output / "figures"
    figures = {"06_rf_partial_dependence": _save_figure(plt, fig, folder, "06_rf_partial_dependence")}

    fig, ax = plt.subplots(figsize=(9, 4))
    ranked = importance.sort_values("mean_mae_increase")
    ax.barh(ranked["feature"], ranked["mean_mae_increase"], xerr=ranked["sd_mae_increase"], color="#11867e")
    ax.axvline(0, color="#152839", linewidth=.8)
    ax.set(xlabel="Increase in held-out MAE after permutation (km/h)", title="Random Forest permutation importance")
    ax.grid(axis="x", alpha=.25)
    figures["05_rf_importance"] = _save_figure(plt, fig, folder, "05_rf_importance")

    fig, ax = plt.subplots(figsize=(9, 4))
    numeric = coefficients.loc[coefficients["feature"].str.startswith("numeric__")].copy()
    numeric["feature"] = numeric["feature"].str.removeprefix("numeric__")
    numeric = numeric.sort_values("coefficient")
    ax.barh(numeric["feature"], numeric["coefficient"],
            color=np.where(numeric["coefficient"].lt(0), "#ad603b", "#11867e"))
    ax.axvline(0, color="#152839", linewidth=.8)
    ax.set(xlabel="Change in predicted speed per training SD (km/h)", title="Formal-study Ridge coefficients")
    ax.grid(axis="x", alpha=.25)
    figures["07_ridge_coefficients"] = _save_figure(plt, fig, folder, "07_ridge_coefficients")
    write_json(output / "interpretation_scope.json", {"sample": "main held-out test only", "sample_n": sample_size,
                "seed": seed, "permutation_repeats": repeats,
                "partial_dependence_quantiles": [.05, .95], "partial_dependence_max_grid_points": 17})
    logger.info("Saved held-out importance, response curves and coefficient charts. / 已保存变量重要性、响应曲线和系数图。")
    return figures
