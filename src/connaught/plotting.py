"""原型 EDA 与预测诊断绘图。 / EDA and forecast diagnostics."""

import pandas as pd

from .evaluation import MODEL_DISPLAY



def _save_figure(plt, fig, folder, name):
    path = folder / f"{name}.png"
    fig.savefig(path, dpi=145, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def save_eda_figures(panel, output):
    """生成覆盖率与小时车速图。 / Render coverage and hourly speed profiles."""
    from matplotlib import use
    use("Agg")
    from matplotlib import pyplot as plt

    folder = output / "figures"
    folder.mkdir(parents=True, exist_ok=True)
    figures = {}

    fig, ax = plt.subplots(figsize=(10, 4))
    sites = panel.groupby(["detector_id", "road_group"], as_index=False).agg(
        expected=("bin_end", "size"), usable=("speed", "count"))
    sites = sites.sort_values(["road_group", "detector_id"])
    ax.bar(sites["detector_id"], 100 * sites["usable"] / sites["expected"],
           color=["#11867e" if g == "Flyover" else "#4561a5" for g in sites["road_group"]])
    ax.set(title="Usable speed bins by detector", ylabel="Usable 5-minute bins (%)", ylim=(0, 105))
    ax.tick_params(axis="x", labelrotation=40)
    ax.grid(axis="y", alpha=.25)
    figures["01_detector_coverage"] = _save_figure(plt, fig, folder, "01_detector_coverage")

    fig, ax = plt.subplots(figsize=(10, 4))
    work = panel.assign(hour=(panel["bin_end"] - pd.Timedelta(seconds=1)).dt.hour)
    for group, part in work.groupby("road_group"):
        profile = part.groupby("hour")["speed"].mean().reindex(range(24))
        ax.plot(profile.index, profile.values, marker="o", markersize=3, label=group)
    ax.set(title="Observed detector-bin speeds by local hour and road type", ylabel="Mean detector-bin speed (km/h)",
           xlabel="Hong Kong time (hour)", xticks=range(0, 24, 2))
    ax.legend(frameon=False)
    ax.grid(alpha=.25)
    figures["02_hourly_profiles"] = _save_figure(plt, fig, folder, "02_hourly_profiles")

    return figures


def save_forecast_figures(pred, scores, output, config):
    """生成模型误差与预测示例图。 / Render model errors and an example forecast."""
    from matplotlib import use
    use("Agg")
    from matplotlib import pyplot as plt

    folder = output / "figures"
    folder.mkdir(parents=True, exist_ok=True)
    figures = {}

    fig, ax = plt.subplots(figsize=(9, 4))
    names = scores["model"].map(MODEL_DISPLAY)
    bars = ax.barh(names, scores["mae"], color=["#737c8b", "#737c8b", "#6495ad", "#11867e", "#4561a5"])
    ax.bar_label(bars, fmt="%.2f", padding=5)
    ax.set(xlabel="Test MAE (km/h) · lower is better", title=f'{config["horizon_minutes"]}-minute detector-speed forecast · shared test rows',
           xlim=(0, max(scores["mae"]) * 1.17))
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=.25)
    figures["03_model_comparison"] = _save_figure(plt, fig, folder, "03_model_comparison")

    site = pred["detector_id"].value_counts().index[0]
    day = sorted(pred.loc[pred["detector_id"].eq(site), "target_day"].unique())[0]
    sub = pred.loc[pred["detector_id"].eq(site) & pred["target_day"].eq(day)].set_index("target_end")
    times = pd.date_range(sub.index.min(), sub.index.max(), freq="5min")
    sub = sub.reindex(times)
    fig, ax = plt.subplots(figsize=(10, 4))
    for field, name, color in [("target_speed", "Observed", "#152839"), ("persistence", "Persistence", "#8b93a3"),
                               ("ridge_full", "Ridge (full)", "#11867e"), ("random_forest", "Random Forest", "#4561a5")]:
        ax.plot(sub.index, sub[field], label=name, color=color, alpha=.86)
    ax.set(title=f"{site} · {day} · five-minute detector mean speed", xlabel="Target end (HKT)", ylabel="Detector mean speed (km/h)")
    ax.legend(ncol=2, frameon=False)
    ax.grid(alpha=.25)
    fig.autofmt_xdate()
    figures["04_forecast_example"] = _save_figure(plt, fig, folder, "04_forecast_example")

    return figures


def save_figures(panel, pred, scores, output, config):
    return {**save_eda_figures(panel, output), **save_forecast_figures(pred, scores, output, config)}
