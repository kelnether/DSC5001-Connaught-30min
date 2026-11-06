"""独立运行开发期数据探索。 / Run development-period exploratory data analysis."""

from pathlib import Path

from .artifacts import write_json
from .plotting import save_eda_figures
from .preprocessing import build_panel, write_coverage_outputs


def write_eda_outputs(panel, coverage, quality, output):
    """保存覆盖率、质量统计和五分钟面板。 / Save coverage, quality and the five-minute panel."""
    write_coverage_outputs(panel, coverage, quality, output)
    panel.to_csv(output / "five_minute_panel.csv.gz", index=False,
                 compression={"method": "gzip", "mtime": 0})


def run_eda(root, config, output_dir=None, *, include_holdout=False):
    """默认只读取开发期观测。 / Restrict the EDA window to development by default."""
    scope = "all" if include_holdout else "development"
    eda_config = dict(config)
    if not include_holdout:
        eda_config["end_exclusive"] = config["test_start"]

    output = (Path(output_dir).resolve() if output_dir
              else root / config["output"] / "eda" / scope)
    output.mkdir(parents=True, exist_ok=True)
    panel, coverage, quality = build_panel(root, eda_config)
    write_eda_outputs(panel, coverage, quality, output)
    write_json(output / "eda_scope.json", {
        "scope": scope,
        "start": eda_config["start"],
        "end_exclusive": eda_config["end_exclusive"],
    })
    return {"output": output, "coverage": coverage, "figures": save_eda_figures(panel, output)}
