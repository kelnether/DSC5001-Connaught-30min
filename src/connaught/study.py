"""Run the six-week study and its paired coverage check. / 运行六周实验及配对覆盖率检查。"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn

from .artifacts import sha256_file, write_json
from .eda import write_eda_outputs
from .evaluation import MODEL_NAMES, evaluate, paired_ablation, score_table
from .features import FULL_FEATURES, make_examples, split_at
from .models import build_model, choose_parameters, historical_baseline, predict_all
from .plotting import save_eda_figures, save_forecast_figures
from .preprocessing import build_panel, detector_coverage
from .study_diagnostics import bootstrap_mae, paired_model_intervals, save_interpretation

logger = logging.getLogger(__name__)

STUDY_MODELS = (*MODEL_NAMES[:2], "ols", *MODEL_NAMES[2:])
GROUP_KEYS = ("detector_id", "road_group", "time_group", "target_weekend", "target_day")
PREDICTION_KEY = ["detector_id", "origin", "target_end"]
MODEL_COMPARISONS = (
    ("persistence", "ridge_full"), ("historical", "ridge_full"),
    ("persistence", "random_forest"), ("historical", "random_forest"),
    ("ridge_full", "random_forest"), ("ridge_speed_only", "ridge_full"),
)


def fit_plan(panel, config):
    """Select settings on development rows before scoring either holdout. / 仅用开发期样本选参。"""
    examples = make_examples(panel, config)
    train, test = split_at(examples, config["test_start"], config["end_exclusive"])
    specs, tuning = choose_parameters(train, config)
    specs["ols"] = ("ols", None, FULL_FEATURES)
    choices = {model: value for model, (_, value, _) in specs.items()}
    folds = []
    benchmark_rows = []
    columns = [*FULL_FEATURES, "detector_id"]
    for i, fold in enumerate(config["validation"], 1):
        before, valid = split_at(train, fold["start"], fold["end"])
        folds.append({
            "fold": i, **fold, "train_n": len(before), "validation_n": len(valid),
            "last_training_target": str(before["target_end"].max()),
            "first_validation_origin": str(valid["origin"].min()),
            "last_validation_target": str(valid["target_end"].max()),
        })
        ols = build_model("ols", None, FULL_FEATURES, config)
        ols.fit(before[columns], before["target_speed"])
        forecasts = {
            "persistence": valid["speed"],
            "historical": historical_baseline(before, valid)[0],
            "ols": ols.predict(valid[columns]),
        }
        for model, prediction in forecasts.items():
            benchmark_rows.append({"model": model, "parameter": None, "fold": i,
                                   **evaluate(valid["target_speed"], prediction)})
    cv = pd.concat([tuning, pd.DataFrame(benchmark_rows)], ignore_index=True)
    selected = cv.loc[cv["parameter"].isna() | cv["parameter"].eq(cv["model"].map(choices))]
    cv_summary = selected.groupby("model", sort=False)["mae"].agg(
        cv_folds="size", cv_mae_mean="mean", cv_mae_sd="std").reset_index()
    logger.info("Fixed study settings on %d validation folds; %s training rows, %s held-out rows."
                " / 已用开发折固定设置并记录正式切分。", len(folds), f"{len(train):,}", f"{len(test):,}")
    return train, test, specs, cv, cv_summary, {
        "selected_parameters": choices, "validation": folds, "train_n": len(train),
        "test_n": len(test), "complete_rows": len(examples),
        "boundary_excluded": len(examples) - len(train) - len(test),
        "last_train_target": str(train["target_end"].max()),
        "first_test_origin": str(test["origin"].min()), "last_test_target": str(test["target_end"].max()),
        "test_days": int(test["target_day"].nunique()), "test_detectors": int(test["detector_id"].nunique()),
    }


def apply_coverage(panel, quality, threshold):
    """Apply a threshold to one shared panel. / 在共同面板上应用覆盖率门槛。"""
    data = panel.copy()
    below = data["coverage"].lt(threshold)
    no_vehicle = ~data["vehicles"].gt(0)
    data.loc[below, ["speed", "flow_per_lane_hour", "occupancy"]] = np.nan
    usable = data["speed"].notna()
    return data, {
        **quality, "min_coverage": threshold, "usable_bins": int(usable.sum()),
        "usable_detectors": int(data.loc[usable, "detector_id"].nunique()),
        "low_coverage_bins": int(below.sum()), "no_vehicle_after_coverage_bins": int((~below & no_vehicle).sum()),
    }


def evaluate_plan(plan, config, output):
    """Score the frozen models and persist per-row evidence. / 对冻结模型评分并保存逐行证据。"""
    train, test, specs, cv, cv_summary, split = plan
    fitted = {}
    predictions, coefficients = predict_all(train, test, specs, config, fitted=fitted)
    scores = score_table(predictions, model_names=STUDY_MODELS)
    scores = scores.merge(cv_summary, on="model", validate="one_to_one")
    scores = scores.merge(bootstrap_mae(predictions, STUDY_MODELS, config["seed"]), on="model", validate="one_to_one")
    scores["fit_seconds"] = scores["model"].map({model: time for model, (_, time) in fitted.items()})
    scores["parameter"] = scores["model"].map(split["selected_parameters"])
    groups = pd.concat([score_table(predictions, key, model_names=STUDY_MODELS).assign(dimension=key)
                        for key in GROUP_KEYS], ignore_index=True)
    ablation = paired_ablation(predictions, config["seed"])
    paired = paired_model_intervals(predictions, MODEL_COMPARISONS, config["seed"])
    output.mkdir(parents=True, exist_ok=True)
    for name, table in {"predictions": predictions, "model_metrics": scores,
                        "errors_by_group": groups, "cv_scores": cv,
                        "ridge_coefficients": coefficients, "paired_model_comparisons": paired}.items():
        table.to_csv(output / f"{name}.csv", index=False)
    return predictions, scores, coefficients, ablation, fitted["random_forest"][0]


def compare_coverage(pairs, cuts, splits, seed, output):
    """Compare both full samples and their shared prediction keys. / 比较各门槛全样本和共同预测行。"""
    by_threshold = [p.set_index(PREDICTION_KEY) for p in pairs]
    if any(not p.index.is_unique for p in by_threshold):
        raise ValueError("Prediction keys must be unique. / 预测键必须唯一。")
    shared = by_threshold[0].index.intersection(by_threshold[1].index)
    if shared.empty:
        raise ValueError("Coverage rules have no shared test rows. / 两个门槛没有共同测试行。")
    np.testing.assert_allclose(by_threshold[0].loc[shared, "target_speed"],
                               by_threshold[1].loc[shared, "target_speed"])
    tables = []
    contrasts = []
    for threshold, split, predictions in zip(cuts, splits, by_threshold, strict=True):
        samples = {"all": predictions, "common": predictions.loc[shared]}
        for sample, rows in samples.items():
            tables.append(score_table(rows, model_names=STUDY_MODELS).assign(
                threshold=threshold, sample=sample, train_n=split["train_n"]))
            contrasts.append({"threshold": threshold, "sample": sample, "n": len(rows),
                              **paired_ablation(rows, seed)})
    pd.concat(tables, ignore_index=True).to_csv(output / "coverage_robustness_metrics.csv", index=False)
    write_json(output / "coverage_robustness_ablation.json", contrasts)
    shared.to_frame(index=False).to_csv(output / "coverage_common_keys.csv", index=False)
    logger.info("Matched %s held-out keys across thresholds. / 已按点位和时刻匹配共同样本。", f"{len(shared):,}")
    return len(shared)


def run_study(root, config, output_dir=None):
    """Run the frozen six-week protocol and export analytical evidence. / 运行冻结后的正式方案并保存分析证据。"""
    output = Path(output_dir).resolve() if output_dir else root / config["output"]
    output.mkdir(parents=True, exist_ok=True)
    cuts = (config["min_coverage"], config["alternative_coverage"])
    panel, _, quality = build_panel(root, {**config, "min_coverage": 0.0})
    variants = [apply_coverage(panel, quality, cut) for cut in cuts]
    main_panel, _ = variants[0]
    eda_dir = output / "eda" / "development"
    eda_dir.mkdir(parents=True, exist_ok=True)
    development = main_panel.loc[main_panel["bin_end"].le(pd.Timestamp(config["test_start"]))]
    detector_coverage(development).to_csv(eda_dir / "detector_coverage.csv", index=False)
    write_json(eda_dir / "eda_scope.json", {"scope": "development", "start": config["start"],
                                           "end_exclusive": config["test_start"]})
    figures = save_eda_figures(development, eda_dir)
    plans = [fit_plan(data, config) for data, _ in variants]
    splits = [plan[-1] for plan in plans]
    freeze = {
        "configuration": config,
        "data_sha256": quality["sha256"],
        "archive_manifest_sha256": sha256_file(root / config["manifest"]),
        "lane_inventory": quality["lane_inventory"],
        "validation_metric": "MAE",
        "thresholds": [{"threshold": cut, **split} for cut, split in zip(cuts, splits, strict=True)],
        "source_sha256": {file.name: sha256_file(file) for file in sorted(Path(__file__).parent.glob("*.py"))},
        "versions": {"numpy": np.__version__, "pandas": pd.__version__, "sklearn": sklearn.__version__},
    }
    write_json(output / "frozen_protocol.json", freeze)
    logger.info("Saved selections before holdout model scoring. / 已在留出集评分前记录选参结果。")
    destinations = (output, output / "coverage_alternative")
    fitted_results = []
    summaries = []
    for (data, audit), plan, location in zip(variants, plans, destinations, strict=True):
        location.mkdir(parents=True, exist_ok=True)
        write_eda_outputs(data, detector_coverage(data), audit, location)
        fitted_results.append(evaluate_plan(plan, config, location))
        pred, _, _, ablation, _ = fitted_results[-1]
        outcome = {
            "split": plan[-1], "ablation": ablation, "data": audit,
            "historical_levels": {str(k): int(v) for k, v in pred["historical_level"].value_counts().items()},
        }
        write_json(location / "summary.json", outcome)
        summaries.append(outcome)
    predictions, scores, coefficients, _, forest = fitted_results[0]
    threshold_n = compare_coverage([result[0] for result in fitted_results], cuts, splits, config["seed"], output)
    figures.update(save_forecast_figures(predictions, scores, output, config))
    figures.update(save_interpretation(forest, plans[0][1], coefficients, config["seed"], output))
    write_json(output / "study_complete.json", {
        "main_summary": "summary.json", "alternative_summary": "coverage_alternative/summary.json",
        "shared_coverage_test_rows": threshold_n,
        "thresholds": list(cuts), "figures": {key: str(path.relative_to(output)) for key, path in figures.items()},
    })
    return {"output": output, "metrics": scores, "summary": summaries[0],
            "coverage": detector_coverage(main_panel), "predictions": predictions, "figures": figures}
