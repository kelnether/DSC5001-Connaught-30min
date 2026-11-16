"""独立运行开发期数据探索。 / Run development-period exploratory data analysis."""

import logging
from pathlib import Path

from .artifacts import write_json
from .plotting import save_eda_figures
from .preprocessing import build_panel, write_coverage_outputs

logger = logging.getLogger(__name__)


def write_eda_outputs(panel, coverage, quality, output):
    """保存覆盖率、质量统计和五分钟面板。 / Save coverage, quality and the five-minute panel."""
    write_coverage_outputs(panel, coverage, quality, output)
    panel.to_csv(output / "five_minute_panel.csv.gz", index=False,
                 compression={"method": "gzip", "mtime": 0})
    logger.info("已保存五分钟面板（含车速、流量和占用率）：%s", output / "five_minute_panel.csv.gz")


def run_eda(root, config, output_dir=None, *, include_holdout=False):
    """默认只读取开发期观测。 / Restrict the EDA window to development by default."""
    scope = "all" if include_holdout else "development"
    eda_config = dict(config)
    if not include_holdout:
        eda_config["end_exclusive"] = config["test_start"]

    output = (Path(output_dir).resolve() if output_dir
              else root / config["output"] / "eda" / scope)
    output.mkdir(parents=True, exist_ok=True)
    logger.info("探索性分析范围：%s，%s 至 %s（右端不含）。",
                "全期" if include_holdout else "开发期", eda_config["start"], eda_config["end_exclusive"])
    panel, coverage, quality = build_panel(root, eda_config)
    write_eda_outputs(panel, coverage, quality, output)
    write_json(output / "eda_scope.json", {
        "scope": scope,
        "start": eda_config["start"],
        "end_exclusive": eda_config["end_exclusive"],
    })
    figures = save_eda_figures(panel, output)
    logger.info("EDA 完成：%d 张图，分析范围记录在 %s。", len(figures), output / "eda_scope.json")
    return {"output": output, "coverage": coverage, "figures": figures}
