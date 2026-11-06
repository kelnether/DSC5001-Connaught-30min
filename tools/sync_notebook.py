"""同步 Notebook 的运行入口与源码附录。 / Sync notebook entry points and its source appendix."""

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

INTRO = """# 干诺道西及西天桥 · 提前 30 分钟的检测点平均车速预测

**Connaught Road West and Flyover · 30-Minute-Ahead Detector Mean Speed Forecast**

在解压后的项目目录打开 Notebook，选择安装了项目依赖的内核，然后 Run All。运行单元直接调用本项目的 Python 模块。末尾源码附录逐文件保留完整实现，便于阅读、核对和交接。

预测目标为同一检测点在预测起点后第 30 分钟结束的 5 分钟加权平均车速。原始数据按车道存储，车道数用于覆盖率检查，速度差试验留作六周数据的候选敏感性分析。默认运行随包附带的三天原型。正式数据准备好后可设置 `CONNAUGHT_CONFIG=study`。

Open this notebook in the extracted project, select the Python environment with project dependencies, and choose Run All. The executable cells call the same modules as the CLI. The source appendix includes each complete package file for inspection and handover.

The target is the vehicle-weighted mean speed in the five-minute bin ending 30 minutes after the forecast origin at the same detector. Lane records support coverage checks and aggregation. The lane speed gap remains a candidate sensitivity analysis. The bundled three-day pilot runs by default. Set `CONNAUGHT_CONFIG=study` after preparing the study data.

- `CONNAUGHT_STAGE=eda` · 只运行开发期 EDA / Run development-only EDA.
- `CONNAUGHT_OUTPUT` · 指定独立输出目录 / Choose a separate output directory.
- `CONNAUGHT_PROJECT_ROOT` · 从项目外启动内核时指定目录 / Locate the project when the kernel starts elsewhere.
"""

SETUP = '''import os
from pathlib import Path
import sys

base = Path(os.environ.get("CONNAUGHT_PROJECT_ROOT") or Path.cwd()).resolve()
root = next((path for path in (base, *base.parents)
             if (path / "src/connaught/pipeline.py").is_file()
             and (path / "configs/pilot.toml").is_file()), None)
if root is None:
    raise FileNotFoundError("Open the notebook in the project or set CONNAUGHT_PROJECT_ROOT.")
sys.path.insert(0, str(root / "src"))

from connaught.config import load_config
from connaught.eda import run_eda
from connaught.pipeline import run

config = load_config(root, os.environ.get("CONNAUGHT_CONFIG", "pilot"))
output_dir = os.environ.get("CONNAUGHT_OUTPUT")
stage = os.environ.get("CONNAUGHT_STAGE", "run")
'''

RUN = '''if stage == "eda":
    result = run_eda(root, config, output_dir)
elif stage == "run":
    result = run(root, config, output_dir)
else:
    raise ValueError("CONNAUGHT_STAGE must be run or eda.")
print(f"{stage} · {config['name']} · {result['output']}")
'''

RESULTS = '''from IPython.display import Image, display

if "metrics" in result:
    display(result["metrics"].round(4))
    print("Ablation:", result["summary"]["ablation"])
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
        markdown("setup-notes", "## 1. 加载配置 / Load configuration"),
        code_cell("setup", SETUP),
        markdown("run-notes", "## 2. 运行共用流程 / Run the shared pipeline"),
        code_cell("run", RUN),
        markdown("result-notes", "## 3. 查看覆盖率、结果和图表 / Review coverage, results and figures"),
        code_cell("results", RESULTS),
        markdown("source-notes", "## 4. 源码附录 / Package source\n\n"
                 "这些是项目模块的逐字副本。修改源文件后，运行 "
                 "`python tools/sync_notebook.py` 重新生成本文件。\n\n"
                 "These are verbatim module snapshots. Edit the package files and regenerate the notebook."),
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
    parser.add_argument("--check", action="store_true")
    expected = build_notebook()
    if parser.parse_args().check:
        actual = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
        if (source_signature(actual) != source_signature(expected) or
                any(actual["metadata"].get(key) != expected["metadata"][key]
                    for key in ("canonical_sources", "core_sha256"))):
            raise SystemExit("Notebook source is stale. Run python tools/sync_notebook.py.")
        print(f'Notebook matches {len(expected["metadata"]["canonical_sources"])} source files and all run cells.')
        return
    NOTEBOOK.write_text(json.dumps(expected, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
