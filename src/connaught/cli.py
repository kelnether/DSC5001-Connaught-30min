"""命令行入口与子命令。 / Command-line entry point and subcommands."""

import argparse
import json
from pathlib import Path

from .config import load_config, project_root


def _run(args, root, config):
    if args.coverage_only:
        from .preprocessing import audit_coverage
        print(f"Coverage: {audit_coverage(root, config, args.output)}")
        return

    from .pipeline import run
    result = run(root, config, args.output)
    print(result["metrics"].to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    print(f'Report: {result["report"]}')


def _eda(args, root, config):
    from .eda import run_eda
    result = run_eda(root, config, args.output, include_holdout=args.include_holdout)
    print(f'EDA: {result["output"]}')


def _prepare(args, root, config):
    from .archives import download_archives, prepare_lane_subset, probe_archives
    from .artifacts import write_json

    archive_dir = args.archive_dir or root / ".cache/traffic_archives"
    if args.manifest:
        manifest = json.loads(args.manifest.read_text())
    else:
        probe = probe_archives(config)
        destination = root / f"data/provenance/{config['name']}_archive_probe.json"
        write_json(destination, probe)
        available = sum(bool(row.get("snapshot_versions") and row.get("official_package")) for row in probe)
        print(f"Archive metadata: {available}/{len(probe)} days advertised. {destination}")
        if args.probe:
            return
        manifest = download_archives(config, archive_dir, probe)
    prepare_lane_subset(root, config, archive_dir, manifest)


def main(argv=None, *, default_root=None):
    """从项目目录执行指定阶段。 / Execute the selected stage from a project checkout."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    run_parser = commands.add_parser("run", help="Run forecasting, evaluation and report generation.")
    run_parser.add_argument("--coverage-only", action="store_true", help="Audit coverage without fitting models.")
    run_parser.set_defaults(handler=_run)

    eda_parser = commands.add_parser("eda", help="Build the panel and EDA figures without fitting models.")
    eda_parser.add_argument("--include-holdout", action="store_true",
                            help="Include the holdout for descriptive plots after evaluation.")
    eda_parser.set_defaults(handler=_eda)

    prepare_parser = commands.add_parser("prepare", help="Probe, download or import official archives.")
    prepare_parser.add_argument("--archive-dir", type=Path, help="Defaults to .cache/traffic_archives in the project.")
    mode = prepare_parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--probe", action="store_true", help="Check availability without downloading ZIPs.")
    mode.add_argument("--download", action="store_true", help="Download and extract official ZIPs.")
    mode.add_argument("--manifest", type=Path, help="Import local ZIPs verified against a SHA-256 manifest.")
    prepare_parser.set_defaults(handler=_prepare)

    for command in (run_parser, eda_parser, prepare_parser):
        command.add_argument("--root", type=Path, help="Project directory containing configs and data.")
        command.add_argument("--config", default="study" if command is prepare_parser else "pilot",
                             help="pilot, study, or a TOML path")
    for command in (run_parser, eda_parser):
        command.add_argument("--output", help="Write into a separate result directory.")

    args = parser.parse_args(argv)
    root = project_root(args.root or default_root)
    args.handler(args, root, load_config(root, args.config))
