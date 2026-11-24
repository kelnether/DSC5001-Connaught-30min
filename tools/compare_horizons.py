"""Reproduce the proposal's matched 15- and 30-minute pilot. / 复现 Proposal 的时距选择对照。"""

import argparse
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from connaught.artifacts import write_json
from connaught.cli import configure_console
from connaught.config import load_config
from connaught.evaluation import evaluate
from connaught.features import FULL_FEATURES, make_examples, split_at
from connaught.models import build_model
from connaught.preprocessing import build_panel


def run(output):
    config = load_config(ROOT, "pilot")
    panel, _, quality = build_panel(ROOT, config)
    key = ["detector_id", "origin"]
    splits = {}
    for horizon in (15, 30):
        examples = make_examples(panel, {**config, "horizon_minutes": horizon})
        train, test = split_at(examples, config["test_start"], config["end_exclusive"])
        splits[horizon] = [table.set_index(key, drop=False) for table in (train, test)]
        if any(not table.index.is_unique for table in splits[horizon]):
            raise ValueError("Forecast origins must be unique per detector. / 各点位内的预测起点必须唯一。")
    train_keys, test_keys = (a.index.intersection(b.index) for a, b in zip(splits[15], splits[30], strict=True))
    columns = [*FULL_FEATURES, "detector_id"]
    scores = []
    rows = []
    alpha = config["ridge_alphas"][0]
    for horizon, (train, test) in splits.items():
        train, test = train.loc[train_keys], test.loc[test_keys]
        model = build_model("ridge", alpha, FULL_FEATURES, config)
        model.fit(train[columns], train["target_speed"])
        table = test[[*key, "target_end", "target_speed"]].copy()
        table["persistence"] = test["speed"]
        table["ridge_full"] = model.predict(test[columns])
        baseline = evaluate(table["target_speed"], table["persistence"])["mae"]
        ridge = evaluate(table["target_speed"], table["ridge_full"])["mae"]
        scores.append({"horizon_minutes": horizon, "train_n": len(train), "test_n": len(test),
                       "persistence_mae": baseline, "ridge_mae": ridge, "gain_pct": 100 * (1 - ridge / baseline)})
        rows.append(table.assign(horizon_minutes=horizon))
    output.mkdir(parents=True, exist_ok=True)
    metrics = pd.DataFrame(scores)
    metrics.to_csv(output / "model_metrics.csv", index=False)
    pd.concat(rows, ignore_index=True).to_csv(output / "predictions.csv", index=False)
    write_json(output / "summary.json", {"input_sha256": quality["sha256"], "alpha": alpha,
                "matched_key": key, "split": config["test_start"], "analysis": "pilot horizon choice"})
    print(metrics.to_string(index=False, float_format=lambda value: f"{value:.4f}"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "horizon_comparison")
    configure_console()
    run(parser.parse_args().output)
