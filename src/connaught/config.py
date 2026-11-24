"""Load and validate experiment configuration. / 加载和验证实验配置。"""

from pathlib import Path
import tomllib

import pandas as pd


def project_root(directory=None):
    """Find the project from its root or any child directory. / 从项目根目录或任意子目录定位项目。"""
    base = Path(directory or Path.cwd()).resolve()
    for path in (base, *base.parents):
        if (path / "configs/pilot.toml").is_file():
            return path
    raise FileNotFoundError("Run from the extracted project directory or pass its path with --root. / 请在解压后的项目目录运行，或用 --root 指定目录。")


def load_config(root, name="pilot"):
    cfg_path = Path(name)
    if cfg_path.suffix != ".toml":
        cfg_path = Path("configs") / f"{name}.toml"
    path = root / cfg_path
    with path.open("rb") as stream:
        config = tomllib.load(stream)
    start, cut, end = (pd.Timestamp(config[key]) for key in ("start", "test_start", "end_exclusive"))
    if not start < cut < end:
        raise ValueError("Require start < test_start < end_exclusive. / 起始、测试起点及结束时间必须严格递增。")
    if config["bin_minutes"] != 5 or config["horizon_minutes"] not in (15, 30, 60):
        raise ValueError("Use 5-minute bins and a 15-, 30- or 60-minute horizon. / 请使用五分钟时间箱和 15、30 或 60 分钟预测时距。")
    if not 0 < config["min_coverage"] <= 1:
        raise ValueError("min_coverage must be in (0, 1]. / 覆盖率门槛必须大于 0 且不超过 1。")
    if not config["ridge_alphas"] or not config["forest_leaf_sizes"]:
        raise ValueError("Model candidate lists cannot be empty. / 模型候选参数列表不能为空。")
    for fold in config.get("validation", []):
        if not start < pd.Timestamp(fold["start"]) < pd.Timestamp(fold["end"]) <= cut:
            raise ValueError("Validation periods must lie inside the development period. / 验证时段必须位于开发期。")
    if config.get("analysis") == "study":
        folds = config.get("validation", [])
        first_fold = min((pd.Timestamp(f["start"]) for f in folds), default=cut)
        inventory_cutoff = pd.Timestamp(config["lane_inventory_cutoff"])
        if not folds or not start < inventory_cutoff <= first_fold:
            raise ValueError("Freeze the lane inventory before validation. / 验证前必须冻结车道清单。")
        if not config["min_coverage"] < config["alternative_coverage"] <= 1:
            raise ValueError("Set a higher alternative coverage threshold. / 替代覆盖率门槛须高于主门槛。")
    return config
