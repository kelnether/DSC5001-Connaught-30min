"""Verify analytical outputs against their row keys and provenance. / 用逐行键和来源清单核对结果。"""

import argparse
from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from connaught.artifacts import sha256_file, write_json

KEY = ["detector_id", "origin", "target_end"]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify_variant(result, planned, config):
    panel = pd.read_csv(result / "five_minute_panel.csv.gz", parse_dates=["bin_end"])
    predictions = pd.read_csv(result / "predictions.csv", parse_dates=["origin", "target_end"])
    metrics = pd.read_csv(result / "model_metrics.csv")
    cv = pd.read_csv(result / "cv_scores.csv")
    assert len(predictions) == planned["test_n"]
    assert not predictions.duplicated(KEY).any()
    assert predictions["origin"].ge(pd.Timestamp(config["test_start"])).all()
    assert predictions["target_end"].le(pd.Timestamp(config["end_exclusive"])).all()
    assert predictions["target_end"].sub(predictions["origin"]).eq(pd.Timedelta(minutes=config["horizon_minutes"])).all()
    expected = panel[["detector_id", "bin_end", "speed"]].rename(columns={"bin_end": "target_end"})
    paired_target = predictions.merge(expected, on=["detector_id", "target_end"], validate="one_to_one")
    assert len(paired_target) == len(predictions)
    np.testing.assert_allclose(paired_target["target_speed"], paired_target["speed_y"])
    assert pd.Timestamp(planned["last_train_target"]) <= predictions["origin"].min()
    assert all(pd.Timestamp(row["last_training_target"]) <= pd.Timestamp(row["first_validation_origin"])
               for row in planned["validation"])
    comparison = metrics.set_index("model")["mae"]
    assert set(metrics["cv_folds"]) == {len(config["validation"])}
    assert metrics["n"].eq(len(predictions)).all()
    assert len(set(predictions["target_day"])) == planned["test_days"]
    for result_row in metrics.itertuples():
        delta = predictions[result_row.model].sub(predictions["target_speed"])
        np.testing.assert_allclose([delta.abs().mean(), np.sqrt(delta.pow(2).mean()), delta.mean()],
                                   [result_row.mae, result_row.rmse, result_row.bias])
        selected = cv[cv["model"].eq(result_row.model)]
        if result_row.model in planned["selected_parameters"] and pd.notna(result_row.parameter):
            selected = selected[selected["parameter"].eq(result_row.parameter)]
        np.testing.assert_allclose([selected["mae"].mean(), selected["mae"].std()],
                                   [result_row.cv_mae_mean, result_row.cv_mae_sd])
    summary = read_json(result / "summary.json")
    gain = comparison["ridge_speed_only"] - comparison["ridge_full"]
    np.testing.assert_allclose(gain, summary["ablation"]["full_mae_improvement_kmh"])
    return predictions


def verify(output, archives=None):
    frozen = read_json(output / "frozen_protocol.json")
    config = frozen["configuration"]
    marker = read_json(output / "study_complete.json")
    manifest_path = ROOT / config["manifest"]
    manifest = read_json(manifest_path)
    audit = read_json(ROOT / config["extraction_audit"])
    assert sha256_file(ROOT / config["input"]) == frozen["data_sha256"]
    assert sha256_file(manifest_path) == frozen["archive_manifest_sha256"]
    for name, digest in frozen["source_sha256"].items():
        assert sha256_file(ROOT / "src" / "connaught" / name) == digest, name
    assert [entry["day"] for entry in manifest] == [entry["day"] for entry in audit]
    assert [entry["version_count"] for entry in manifest] == [entry["snapshots"] for entry in audit]
    if archives is not None:
        unique_archives = {item["archive_file"]: item for item in manifest}
        for name, item in unique_archives.items():
            path = archives / name
            assert (path.stat().st_size, sha256_file(path)) == (item["size_bytes"], item["sha256"])
    main = verify_variant(output, frozen["thresholds"][0], config)
    alternative = verify_variant(output / "coverage_alternative", frozen["thresholds"][1], config)
    shared = main[KEY].merge(alternative[KEY], on=KEY, validate="one_to_one")
    saved = pd.read_csv(output / "coverage_common_keys.csv", parse_dates=["origin", "target_end"])
    assert len(shared) == len(saved) == marker["shared_coverage_test_rows"]
    pd.testing.assert_frame_equal(shared.sort_values(KEY).reset_index(drop=True),
                                  saved.sort_values(KEY).reset_index(drop=True))
    assert len(pd.read_csv(output / "rf_permutation_importance.csv")) == 9
    assert set(pd.read_csv(output / "rf_partial_dependence.csv")["feature"]) == {"occupancy", "flow_per_lane_hour"}
    assert all((output / path).stat().st_size > 0 for path in marker["figures"].values())
    counts = {
        "archive_days": len(audit), "archive_snapshots": sum(row["snapshots"] for row in audit),
        "invalid_snapshots": sum(len(row.get("invalid_snapshots", [])) for row in audit),
        "extracted_lane_rows": sum(row["selected_lane_rows"] for row in audit),
        "primary_test_rows": len(main), "alternative_test_rows": len(alternative),
        "shared_test_rows": len(shared), "source_archives_rehashed": archives is not None,
        "labels_verified_against_panel_and_metrics_recomputed": True,
        "frozen_parameters_and_cv_summary_verified": True,
    }
    write_json(output / "verification.json", counts)
    print(json.dumps(counts, indent=2))
    print("Verification passed. / 正式实验核查通过。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "study")
    parser.add_argument("--archive-dir", type=Path)
    args = parser.parse_args()
    verify(args.output, args.archive_dir)
