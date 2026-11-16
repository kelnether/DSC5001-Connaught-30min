"""Benchmarks, Ridge, random forest and chronological tuning. / 基线、Ridge、随机森林和时序选参。"""

import logging

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .evaluation import evaluate
from .features import FULL_FEATURES, SPEED_FEATURES, split_at

logger = logging.getLogger(__name__)


def historical_baseline(train, test):
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
        typical = train.groupby(keys, sort=False)["target_speed"].median().rename("typical")
        values = test[keys].join(typical, on=keys)["typical"].to_numpy()
        use = np.isnan(prediction) & np.isfinite(values)
        prediction[use], levels[use] = values[use], label
    missing = np.isnan(prediction)
    prediction[missing], levels[missing] = test["speed"].to_numpy()[missing], "persistence_fallback"
    return prediction, levels


def build_model(family, value, features, config):
    prep = ColumnTransformer([
        ("numeric", StandardScaler(), features),
        ("site", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["detector_id"]),
    ])
    if family == "ridge":
        estimator = Ridge(alpha=float(value))
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


def predict_all(train, test, specs, config):
    pred = test[["detector_id", "road_group", "origin", "target_end", "target_day",
                 "target_weekend", "time_group", "speed", "target_speed"]].copy()
    pred["persistence"] = test["speed"]
    pred["historical"], pred["historical_level"] = historical_baseline(train, test)
    logger.info("Generated persistence and historical median forecasts for %s test rows. / 已生成两种基线预测。", f"{len(test):,}")
    coefficients = pd.DataFrame()
    for label, (family, value, features) in specs.items():
        parameter = "alpha" if family == "ridge" else "min_samples_leaf"
        logger.info("Fitting %s with %s=%s, %d numeric or binary features and detector encoding. / 正在拟合模型，含点位编码。",
                    label, parameter, value, len(features))
        model = build_model(family, value, features, config)
        cols = features + ["detector_id"]
        model.fit(train[cols], train["target_speed"])
        pred[label] = model.predict(test[cols])
        if label == "ridge_full":
            names = model.named_steps["columntransformer"].get_feature_names_out()
            coefficients = pd.DataFrame({"feature": names, "coefficient": model.named_steps["ridge"].coef_})
    return pred.reset_index(drop=True), coefficients
