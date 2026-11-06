"""兼容原有 workflow 导入。 / Preserve the original workflow import surface."""

from .archives import (
    ARCHIVE_API, DATA_COLUMNS, SOURCE_XML, archive_dates, archive_members, archive_url,
    download_archives, fetch_archive_resource, fetch_json, prepare_lane_subset, probe_archives,
)
from .artifacts import sha256_file, write_json
from .config import load_config, project_root
from .evaluation import MODEL_DISPLAY, MODEL_NAMES, evaluate, paired_ablation, score_table
from .features import FULL_FEATURES, SPEED_FEATURES, make_examples, split_at
from .models import build_model, choose_parameters, historical_baseline, predict_all
from .pipeline import run
from .plotting import save_figures
from .preprocessing import audit_coverage, build_panel, daily_coverage
from .reporting import (
    LANE_PILOT, build_lane_decision, build_main_report_guide, build_proposal, build_report,
    build_team_guide, format_table, term,
)

__all__ = [
    "ARCHIVE_API", "DATA_COLUMNS", "SOURCE_XML", "archive_dates", "archive_members", "archive_url",
    "download_archives", "fetch_archive_resource", "fetch_json", "prepare_lane_subset", "probe_archives",
    "sha256_file", "write_json", "load_config", "project_root", "MODEL_DISPLAY", "MODEL_NAMES",
    "evaluate", "paired_ablation", "score_table", "FULL_FEATURES", "SPEED_FEATURES", "make_examples",
    "split_at", "build_model", "choose_parameters", "historical_baseline", "predict_all", "run",
    "save_figures", "audit_coverage", "build_panel", "daily_coverage", "LANE_PILOT",
    "build_lane_decision", "build_main_report_guide", "build_proposal", "build_report", "build_team_guide",
    "format_table", "term",
]
