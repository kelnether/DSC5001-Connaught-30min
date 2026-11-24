"""Benchmarks, Ridge, random forest and chronological tuning. / 基线、Ridge、随机森林和时序选参。"""

import logging
from time import perf_counter

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .evaluation import evaluate
from .features import FULL_FEATURES, SPEED_FEATURES, split_at

logger = logging.getLogger(__name__)


def historical_baseline(train, test, *, fit_durations=None):
    """Training-only typical speed, with a documented backoff hierarchy. / 仅用训练数据计算典型车速，并记录分层回退规则。"""
    prediction = np.full(len(test), np.nan)
    levels = np.full(len(test), "", dtype=object)
    hierarchy = [
        (["detector_id", "target_dow", "target_slot"], "point_weekday_slot"),
        (["detector_id", "target_weekend", "target_hour"], "point_daytype_hour"),
        (["detector_id", "target_hour"], "point_hour"),
        (["detector_id"], "point_median"),
    ]
    for keys, label in hierarchy:
        started = perf_counter()
        typical = train.groupby(keys, sort=False)["target_speed"].median().rename("typical")
        if fit_durations is not None:
            fit_durations.append(perf_counter() - started)
        values = test[keys].join(typical, on=keys)["typical"].to_numpy()
        use = np.isnan(prediction) & np.isfinite(values)
        prediction[use], levels[use] = values[use], label
    missing = np.isnan(prediction)
    prediction[missing], levels[missing] = test["speed"].to_numpy()[missing], "persistence_fallback"
    return prediction, levels


def build_model(family, value, features, config):
    drop = "first" if family == "ols" else None
    prep = ColumnTransformer([
        ("numeric", StandardScaler(), features),
        ("site", OneHotEncoder(handle_unknown="ignore", sparse_output=False, drop=drop), ["detector_id"]),
    ])
    if family == "ridge":
        estimator = Ridge(alpha=float(value))
    elif family == "ols":
        estimator = LinearRegression()
    else:
        estimator = RandomForestRegressor(n_estimators=config["forest_trees"], min_samples_leaf=int(value),
                                          max_features=0.8, random_state=config["seed"], n_jobs=1)
    return make_pipeline(prep, estimator)


def choose_parameters(examples, config):
    families = [
        ("ridge_full", "ridge", config["ridge_alphas"], FULL_FEATURES),
        ("ridge_speed_only", "ridge", config["ridge_alphas"], SPEED_FEATURES),
        ("random_forest", "forest", config["forest_leaf_sizes"], FULL_FEATURES),
    ]
    folds = [split_at(examples, f["start"], f["end"]) for f in config.get("validation", [])]
    if folds:
        logger.info("Selecting parameters by MAE across %d chronological folds. / 按时序验证的 MAE 选参。", len(folds))
    else:
        logger.info("Using the fixed pilot parameters. / 使用原型配置的固定参数。")
    rows, selected = [], {}
    for label, family, candidates, features in families:
        if not folds and len(candidates) > 1:
            raise ValueError(f"{label}: multiple candidates require validation folds. / 比较多个参数值需要配置验证折。")
        means = []
        for value in candidates:
            fold_scores = []
            for i, (train, valid) in enumerate(folds, 1):
                model = build_model(family, value, features, config)
                cols = features + ["detector_id"]
                model.fit(train[cols], train["target_speed"])
                score = evaluate(valid["target_speed"], model.predict(valid[cols]))
                rows.append({"model": label, "parameter": value, "fold": i, **score})
                fold_scores.append(score["mae"])
            means.append(np.mean(fold_scores) if fold_scores else 0.0)
        selected[label] = (family, candidates[int(np.argmin(means))], features)
    return selected, pd.DataFrame(rows, columns=["model", "parameter", "fold", "n", "mae", "rmse", "bias"])


def predict_all(train, test, specs, config, *, fitted=None):
    pred = test[["detector_id", "road_group", "origin", "target_end", "target_day",
                 "target_weekend", "time_group", "speed", "target_speed"]].copy()
    pred["persistence"] = test["speed"]
    fit_durations = [] if fitted is not None else None
    pred["historical"], pred["historical_level"] = historical_baseline(train, test, fit_durations=fit_durations)
    if fitted is not None:
        fitted["persistence"] = (None, 0.0)
        fitted["historical"] = (None, sum(fit_durations))
    logger.info("Generated persistence and historical median forecasts for %s test rows. / 已生成两种基线预测。", f"{len(test):,}")
    coefficients = pd.DataFrame()
    for label, (family, value, features) in specs.items():
        logger.info("Fitting %s with parameter %s and %d numeric or binary features plus detector encoding."
                    " / 正在拟合模型，含点位编码。", label, value, len(features))
        model = build_model(family, value, features, config)
        cols = features + ["detector_id"]
        started = perf_counter()
        model.fit(train[cols], train["target_speed"])
        if fitted is not None:
            fitted[label] = (model, perf_counter() - started)
        pred[label] = model.predict(test[cols])
        if label == "ridge_full":
            names = model.named_steps["columntransformer"].get_feature_names_out()
            coefficients = pd.DataFrame({"feature": names, "coefficient": model.named_steps["ridge"].coef_})
    return pred.reset_index(drop=True), coefficients
