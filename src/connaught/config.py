"""加载和验证实验配置。 / Load and validate experiment configuration."""

from pathlib import Path
import tomllib

import pandas as pd


def project_root(directory=None):
    """从项目根目录或任意子目录定位项目。 / Find the project from its root or any child directory."""
    base = Path(directory or Path.cwd()).resolve()
    for path in (base, *base.parents):
        if (path / "configs/pilot.toml").is_file():
            return path
    raise FileNotFoundError("Run from the extracted project directory or pass its path with --root.")


def load_config(root, name="pilot"):
    cfg_path = Path(name)
    if cfg_path.suffix != ".toml":
        cfg_path = Path("configs") / f"{name}.toml"
    path = root / cfg_path
    with path.open("rb") as stream:
        config = tomllib.load(stream)
    start, cut, end = (pd.Timestamp(config[key]) for key in ("start", "test_start", "end_exclusive"))
    if not start < cut < end:
        raise ValueError("Require start < test_start < end_exclusive.")
    if config["bin_minutes"] != 5 or config["horizon_minutes"] not in (15, 30, 60):
        raise ValueError("This workflow uses 5-minute bins and a 15/30/60-minute horizon.")
    if not 0 < config["min_coverage"] <= 1:
        raise ValueError("min_coverage must be in (0, 1].")
    if not config["ridge_alphas"] or not config["forest_leaf_sizes"]:
        raise ValueError("Model candidate lists cannot be empty.")
    for fold in config.get("validation", []):
        if not start < pd.Timestamp(fold["start"]) < pd.Timestamp(fold["end"]) <= cut:
            raise ValueError("Validation periods must lie inside the development period.")
    return config
