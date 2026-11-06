"""连接清洗、特征、模型、评估与报告。 / Orchestrate preprocessing, features, models, evaluation and reporting."""

import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd
from sklearn import __version__ as sklearn_version

from .artifacts import write_json
from .config import load_config
from .eda import write_eda_outputs
from .evaluation import paired_ablation, score_table
from .features import make_examples, split_at
from .models import choose_parameters, predict_all
from .plotting import save_figures
from .preprocessing import build_panel
from .reporting import LANE_PILOT, build_report


def run(root, config, output_dir=None):
    output = Path(output_dir).resolve() if output_dir else root / config["output"]
    output.mkdir(parents=True, exist_ok=True)
    panel, coverage, raw = build_panel(root, config)
    examples = make_examples(panel, config)
    train, test = split_at(examples, config["test_start"], config["end_exclusive"])
    specs, cv = choose_parameters(examples, config)
    predictions, coefficients = predict_all(train, test, specs, config)
    scores = score_table(predictions)
    grouped = pd.concat([score_table(predictions, key).assign(dimension=key)
                         for key in ("detector_id", "road_group", "time_group", "target_weekend", "target_day")], ignore_index=True)
    ablation = paired_ablation(predictions, config["seed"])
    summary = {
        "configuration": config,
        "forecast_target": {
            "column": "target_speed", "unit": "km/h", "spatial_unit": "detector_id",
            "aggregation": "vehicle-count-weighted mean of valid lane observations within one detector",
            "window_minutes": config["bin_minutes"], "horizon_minutes": config["horizon_minutes"],
            "additional_predictors": {"flow_per_lane_hour": "vehicles per lane per hour", "occupancy": "%"},
        },
        "lane_decision": {
            "primary_unit": "detector",
            "lane_count_role": "coverage and subgroup checks",
            "lane_speed_role": "vehicle-weighted detector mean and exploratory speed-gap trial",
            "decision_reason": "Small matched-row gains and worse all-row MAE on both pilot holdouts.",
            "pilot_mae_unit": "km/h",
            "pilot_comparisons": LANE_PILOT,
        },
        "data": raw, "versions": {"numpy": np.__version__, "pandas": pd.__version__, "sklearn": sklearn_version},
        "split": {
            "train_n": len(train), "test_n": len(test),
            "last_train_target": str(train["target_end"].max()), "first_test_origin": str(test["origin"].min()),
            "last_test_target": str(test["target_end"].max()), "test_days": int(test["target_day"].nunique()),
            "test_detectors": int(test["detector_id"].nunique()),
        },
        "selected_parameters": {name: value for name, (_, value, _) in specs.items()},
        "historical_levels": {str(k): int(v) for k, v in predictions["historical_level"].value_counts().items()},
        "ablation": ablation,
    }
    write_eda_outputs(panel, coverage, raw, output)
    for name, table in {"predictions": predictions, "model_metrics": scores,
                        "errors_by_group": grouped, "cv_scores": cv, "ridge_coefficients": coefficients}.items():
        table.to_csv(output / f"{name}.csv", index=False)
    write_json(output / "summary.json", summary)
    figures = save_figures(panel, predictions, scores, output, config)
    manifest = json.loads((root / config["manifest"]).read_text())
    probe = root / "data/provenance/study_archive_probe.json"
    archive_probe = json.loads(probe.read_text()) if probe.is_file() else None
    report_path = output / "report.html"
    report_path.write_text(build_report(config, summary, coverage, scores, grouped, cv, coefficients,
                                      figures, manifest, load_config(root, "study"), archive_probe), encoding="utf-8")
    if config["name"] == "pilot" and output_dir is None:
        shutil.copyfile(report_path, root / "report.html")
    return {"output": output, "summary": summary, "coverage": coverage, "metrics": scores,
            "predictions": predictions, "figures": figures, "report": report_path}
