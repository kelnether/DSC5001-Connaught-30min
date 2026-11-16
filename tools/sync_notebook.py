"""Sync notebook entry points and its source appendix. / 同步 Notebook 的运行入口与源码附录。"""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "traffic_analysis.ipynb"
MODULES = (
    "config", "artifacts", "archives", "preprocessing", "eda", "features",
    "models", "evaluation", "plotting", "reporting", "pipeline",
    "cli", "__main__", "__init__", "workflow",
)

INTRO = """# Connaught Road West and Flyover · 30-Minute-Ahead Detector Mean Speed Forecast

**干诺道西及西天桥 · 提前 30 分钟的检测点平均车速预测**

Open this notebook in the extracted project, select the Python environment with project dependencies, and choose Run All. The executable cells call the same modules as the CLI. The source appendix includes each complete package file for inspection and handover.

The target is the vehicle-weighted mean speed in the five-minute bin ending 30 minutes after the forecast origin at the same detector. Lane records support coverage checks and aggregation. The lane speed gap remains a candidate sensitivity analysis. The bundled three-day pilot runs by default. Set `CONNAUGHT_CONFIG=study` after preparing the study data.

在解压后的项目目录打开 Notebook，选择安装了项目依赖的内核，然后 Run All。运行单元直接调用本项目的 Python 模块。末尾源码附录逐文件保留完整实现，便于阅读、核对和交接。

预测目标为同一检测点在预测起点后第 30 分钟结束的 5 分钟加权平均车速。原始数据按车道存储，车道数用于覆盖率检查，速度差试验留作六周数据的候选敏感性分析。默认运行随包附带的三天原型。正式数据准备好后可设置 `CONNAUGHT_CONFIG=study`。

- `CONNAUGHT_STAGE=eda` · Run development-only EDA. / 只运行开发期 EDA。
- `CONNAUGHT_OUTPUT` · Choose a separate output directory. / 指定独立输出目录。
- `CONNAUGHT_PROJECT_ROOT` · Locate the project when the kernel starts elsewhere. / 从项目外启动内核时指定目录。
"""

SETUP = '''import os
from pathlib import Path
import sys

base = Path(os.environ.get("CONNAUGHT_PROJECT_ROOT") or Path.cwd()).resolve()
root = next((path for path in (base, *base.parents)
             if (path / "src/connaught/pipeline.py").is_file()
             and (path / "configs/pilot.toml").is_file()), None)
if root is None:
    raise FileNotFoundError("Open the notebook in the project or set CONNAUGHT_PROJECT_ROOT."
                            " / 请在项目目录打开 Notebook，或设置 CONNAUGHT_PROJECT_ROOT。")
sys.path.insert(0, str(root / "src"))

from connaught.config import load_config
from connaught.cli import configure_console
from connaught.eda import run_eda
from connaught.pipeline import run

config = load_config(root, os.environ.get("CONNAUGHT_CONFIG", "pilot"))
output_dir = os.environ.get("CONNAUGHT_OUTPUT")
stage = os.environ.get("CONNAUGHT_STAGE", "run")
print(f"Config / 配置: {config['name']} · Stage / 阶段: {stage} · Project / 项目: {root}")
'''

RUN = '''configure_console()
if stage == "eda":
    result = run_eda(root, config, output_dir)
elif stage == "run":
    result = run(root, config, output_dir)
else:
    raise ValueError("CONNAUGHT_STAGE must be run or eda. / CONNAUGHT_STAGE 必须是 run 或 eda。")
print(f"Results / 结果: {result['output']}")
'''

RESULTS = '''from IPython.display import Image, display

if "metrics" in result:
    print("Model errors on shared test rows (km/h) / 共同测试样本的模型误差（km/h）")
    display(result["metrics"].round(4))
    print("Paired ablation / 配对消融:", result["summary"]["ablation"])
print("Detector coverage / 检测点覆盖率")
display(result["coverage"].round(4))
for path in result["figures"].values():
    display(Image(filename=str(path)))
'''


def markdown(id_, text, metadata=None):
    return {"cell_type": "markdown", "id": id_, "metadata": metadata or {}, "source": text}


def code_cell(id_, text):
    return {"cell_type": "code", "id": id_, "metadata": {}, "source": text,
            "execution_count": None, "outputs": []}


def build_notebook():
    cells = [
        markdown("intro", INTRO),
        markdown("setup-notes", "## 1. Load configuration / 加载配置"),
        code_cell("setup", SETUP),
        markdown("run-notes", "## 2. Run the shared pipeline / 运行共用流程"),
        code_cell("run", RUN),
        markdown("result-notes", "## 3. Review coverage, results and figures / 查看覆盖率、结果和图表"),
        code_cell("results", RESULTS),
        markdown("source-notes", "## 4. Package source / 源码附录\n\n"
                 "These are verbatim source snapshots. After editing the source, run "
                 "`python tools/sync_notebook.py` to regenerate the notebook.\n\n"
                 "这些是项目源码的逐字副本。修改源文件后，运行 "
                 "`python tools/sync_notebook.py` 重新生成本文件。"),
    ]
    hashes = {}
    paths = [f"src/connaught/{name}.py" for name in MODULES]
    paths.extend(["run_analysis.py", "tools/prepare_data.py"])
    for index, relative in enumerate(paths, 1):
        contents = (ROOT / relative).read_text(encoding="utf-8")
        hashes[relative] = hashlib.sha256(contents.encode()).hexdigest()
        cells.append(markdown(f"source-{index}", f"### `{relative}`\n\n````python\n{contents}````\n",
                              {"canonical_source": relative}))

    metadata = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
        "canonical_sources": hashes,
        "core_sha256": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
    }
    return {"cells": cells, "metadata": metadata, "nbformat": 4, "nbformat_minor": 5}


def source_signature(notebook):
    return [(cell["id"], cell["cell_type"], cell["metadata"].get("canonical_source"),
             "".join(cell["source"])) for cell in notebook["cells"]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="Verify the source snapshots and code cells. / 核对源码快照及代码单元。")
    expected = build_notebook()
    if parser.parse_args().check:
        actual = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
        if (source_signature(actual) != source_signature(expected) or
                any(actual["metadata"].get(key) != expected["metadata"][key]
                    for key in ("canonical_sources", "core_sha256"))):
            raise SystemExit("Notebook source is out of date. Run python tools/sync_notebook.py."
                             " / Notebook 源码待同步，请运行 python tools/sync_notebook.py。")
        print(f'Notebook matches {len(expected["metadata"]["canonical_sources"])} source files and all run cells.'
              ' / Notebook 源码快照和运行单元一致。')
        return
    NOTEBOOK.write_text(json.dumps(expected, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f'Generated {NOTEBOOK} with {len(expected["metadata"]["canonical_sources"])} source snapshots.'
          ' / 已生成 Notebook 及源码快照。')


if __name__ == "__main__":
    main()
