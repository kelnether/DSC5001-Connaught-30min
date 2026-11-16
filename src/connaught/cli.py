"""Command-line entry point and subcommands. / 命令行入口与子命令。"""

import argparse
import json
import logging
from pathlib import Path
import sys

from .config import load_config, project_root

logger = logging.getLogger(__name__)


def configure_console():
    """Show package progress in a terminal or notebook. / 在终端或 Notebook 输出各阶段日志。"""
    package_logger = logging.getLogger("connaught")
    for handler in package_logger.handlers[:]:
        if handler.get_name() == "connaught-console":
            package_logger.removeHandler(handler)
            handler.close()
    handler = logging.StreamHandler(sys.stdout)
    handler.set_name("connaught-console")
    handler.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
    package_logger.addHandler(handler)
    package_logger.setLevel(logging.INFO)
    package_logger.propagate = False


def _run(args, root, config):
    if args.coverage_only:
        from .preprocessing import audit_coverage
        logger.info("Running the coverage audit. / 正在审计覆盖率。")
        audit_coverage(root, config, args.output)
        return

    from .pipeline import run
    result = run(root, config, args.output)
    print("\nModel errors on shared test rows (MAE, RMSE and bias in km/h) / 共同测试样本的模型误差（km/h）", flush=True)
    print(result["metrics"].to_string(index=False, float_format=lambda value: f"{value:.4f}"))


def _eda(args, root, config):
    from .eda import run_eda
    run_eda(root, config, args.output, include_holdout=args.include_holdout)


def _prepare(args, root, config):
    from .archives import download_archives, prepare_lane_subset, probe_archives
    from .artifacts import write_json

    archive_dir = args.archive_dir or root / ".cache/traffic_archives"
    if args.manifest:
        logger.info("Importing local ZIPs from %s using archive directory %s. / 按清单从归档目录导入本地 ZIP。", args.manifest, archive_dir)
        manifest = json.loads(args.manifest.read_text())
    else:
        probe = probe_archives(config)
        destination = root / f"data/provenance/{config['name']}_archive_probe.json"
        write_json(destination, probe)
        available = sum(bool(row.get("snapshot_versions") and row.get("official_package")) for row in probe)
        logger.info("Archive metadata available for %d/%d days. Saved probe to %s. / 已保存归档元数据查询结果。", available, len(probe), destination)
        if args.probe:
            return
        manifest = download_archives(config, archive_dir, probe)
    prepare_lane_subset(root, config, archive_dir, manifest)


def main(argv=None, *, default_root=None):
    """Execute the selected stage from a project checkout. / 从项目目录执行指定阶段。"""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    run_parser = commands.add_parser("run", help="Run forecasts, evaluation and reporting. / 运行预测、评估并生成报告。")
    run_parser.add_argument("--coverage-only", action="store_true", help="Audit coverage without fitting models. / 仅审计覆盖率。")
    run_parser.set_defaults(handler=_run)

    eda_parser = commands.add_parser("eda", help="Build the panel and EDA figures. / 生成面板数据和 EDA 图。")
    eda_parser.add_argument("--include-holdout", action="store_true",
                            help="Include the holdout in descriptive plots. / 将留出期纳入描述性绘图。")
    eda_parser.set_defaults(handler=_eda)

    prepare_parser = commands.add_parser("prepare", help="Probe, download or import archives. / 查询、下载或导入归档。")
    prepare_parser.add_argument("--archive-dir", type=Path, help="Default: .cache/traffic_archives. / 默认使用项目中的归档缓存目录。")
    mode = prepare_parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--probe", action="store_true", help="Check archive availability. / 查询归档是否可用。")
    mode.add_argument("--download", action="store_true", help="Download and extract official ZIPs. / 下载并提取官方 ZIP。")
    mode.add_argument("--manifest", type=Path, help="Verify and import local ZIPs using a manifest. / 按清单校验并导入本地 ZIP。")
    prepare_parser.set_defaults(handler=_prepare)

    for command in (run_parser, eda_parser, prepare_parser):
        command.add_argument("--root", type=Path, help="Project directory with configs and data. / 含配置及数据的项目目录。")
        command.add_argument("--config", default="study" if command is prepare_parser else "pilot",
                             help="pilot, study, or a TOML path. / 原型、正式实验或 TOML 配置路径。")
    for command in (run_parser, eda_parser):
        command.add_argument("--output", help="Write to a separate result directory. / 指定独立结果目录。")

    args = parser.parse_args(argv)
    configure_console()
    root = project_root(args.root or default_root)
    config = load_config(root, args.config)
    logger.info("Starting %s with config %s, from %s to %s (end excluded). / 开始运行，观察窗口右端不含。",
                args.command, config["name"], config["start"], config["end_exclusive"])
    args.handler(args, root, config)
