# 干诺道西及西天桥 · 检测点级提前 30 分钟平均车速预测

[English](#english)

DSC5001 五人小组的可运行工作底稿。当前范围覆盖干诺道西及西天桥。

## 预测目标与结果口径

预测目标是每个检测点在目标 5 分钟内的车辆数加权平均车速（km/h）。汇总该点覆盖车道的有效 30 秒观测，每条观测以其车辆数加权。每个点独立输出，汇总范围止于单个检测点。流量（辆/车道/小时）和占用率（%）是输入特征。 每隔 5 分钟发出一次预测。例如，08:00 发出的预测对应同一检测点 08:25–08:30 的均速。

`predictions.csv` 中，`target_speed` 是该点在目标时段的实测均速，各模型列是预测均速。`model_metrics.csv` 中的 `Overall` 汇总各检测点预测行的误差。

- 中文团队报告（附关键英文术语）、车道试验及 Proposal 讨论稿可在本地运行原型后打开生成的 `report.html`。
- [Jupyter Notebook](traffic_analysis.ipynb) · 全部核心逻辑、中英双语逐节说明及原型运行输出。复现时保留完整项目目录。
- [原型配置](configs/pilot.toml) · 2026-10-16 至 2026-10-18。三天实测，周日留出。
- [六周研究配置](configs/study.toml) · 2026-09-21 至 2026-11-01。四周开发、两周测试，正式模型有待完整归档实跑。

## 车道方案与取舍

原始记录按车道保存。车道数用于覆盖率检查，各车道有效观测按车辆数合并为检测点的 5 分钟均速。原型两天留出对照中，车道数带来的 MAE 降幅均小于 0.01 km/h。车道速度差在共同样本上的改善很小，在全样本版本中两天的 MAE 均上升。因此主分析以检测点为单位，暂不开展逐车道预测。车道速度差保留为六周数据的候选敏感性分析。

两天对照的样本数和 MAE 见 `results/pilot/summary.json` 的 `lane_decision` 字段。

## 按课程模板准备交稿

本节根据课程提供的 `Team-XX-Proposal-Template.pdf` 与 `Team-XX-Main-Report-Template.pdf` 编排。

- **Proposal**。依次准备问题式标题和成员表、2–4 句背景、2–3 个可检验的研究问题、数据、拟用方法、验证与评价、预期贡献与限制、四周时间表、参考资料。数据段给出来源链接与访问日期、观察单位、预计规模、响应和输入。原型只用于说明流程可行，六周有效样本和正式结论待数据审计与评分。填完占位符、删除指导文字后，导出至少半页的 `Team-XX-Proposal.pdf`。Proposal 自身的交稿时间在课程平台核对。
- **Main Report**。最终展示式报告最多 10 页，包含封面。按「封面 → 动机与 RQ → 数据及清洗 → EDA → 模型与验证 → 可解释模型 → 总体比较 → 变量解释 → 稳健性 → 结论」编排。第 10 页用正式数字回答每个 RQ，给目标使用者 2–3 条有证据的建议，列限制与一项后续工作，并注明 `Team-[XX]-Appendix.pdf`。附录逐项对应图表、运行命令、配置、结果文件和生成代码。
- **时间与录屏**。Proposal 模板列出项目最终截止为 **2026 年 11 月 29 日 23:59**，并要求至少预留一天。为约 8 分钟录屏安排每页讲者，先按模板参考时长排练。

| 交稿前要核对的证据 | 现有项目材料 | 正式版待补 |
|---|---|---|
| 清洗、样本规模与 EDA（第 3–4 页） | `data_quality.json`、`daily_coverage.csv`、覆盖率图和小时车速图 | 逐规则删除计数、六周有效样本、2–3 张带建模结论的开发期图 |
| 模型阶梯与可解释结果（第 5–6 页） | Persistence、历史中位数、Ridge、随机森林、`ridge_coefficients.csv` | OLS 对照、日期轴上的两折扩展窗口、带正负号的 Ridge 系数图 |
| 完整模型比较（第 7 页） | `cv_scores.csv`、`model_metrics.csv`、`predictions.csv` | 共同开发折的 CV 均值 ± 标准差、逐模型测试 95% bootstrap 区间、拟合耗时 |
| 变量解释和稳健性（第 8–9 页） | Ridge 系数、`errors_by_group.csv`、车道试验 | 置换重要性和部分依赖图，正式子群与替代清洗规则对照，记录留存、误差及结论变化 |
| 结论和代码（第 10 页） | 原型研究问题与复现流程 | 正式 RQ 数字、建议、限制和逐项可复现代码附录 |

上表中的原型结果文件在 `results/pilot/`，正式实验输出在 `results/study/`。原型的 `cv_scores.csv` 没有验证折数据。现有按日重采样只计算两版 Ridge 的配对差值区间，逐模型测试区间要单独计算。备选覆盖率可从 70% 开始讨论，在开发期锁定，并同时报告各口径和共同样本。

运行原型后打开生成的 `report.html`，从目录进入「Main Report 逐页计划」。

## 快速运行

Python 3.11 或更高版本。在项目根目录运行下面的命令。安装依赖需要网络，随包的三天原型可离线运行。

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[notebook]'
connaught eda --config pilot
connaught run --config pilot
python tools/sync_notebook.py --check
```

Windows PowerShell 用 `.venv\Scripts\Activate.ps1` 激活。已安装项目后，也可用 `python -m connaught` 替代 `connaught`。旧入口 `python run_analysis.py` 和 `python tools/prepare_data.py` 仍可在依赖已安装时使用。

`eda` 默认将观察窗口截在测试起始日之前，输出覆盖率、质量统计、五分钟面板和两张 EDA 图。原型默认写入 `results/pilot/eda/development/`。需要做全期描述时才显式使用 `--include-holdout`。`run` 拟合模型并输出预测、误差、图表和报告，默认写入 `results/pilot/` 或 `results/study/`。两个命令都接受 `--output`，各人可以使用独立目录。若从项目外执行，传入 `--root PATH`。

在 Jupyter 或 VS Code 中选择同一环境，打开 `traffic_analysis.ipynb` 并执行 **Run All**。Notebook 直接导入这些模块，末尾附各源码文件的完整快照。设置 `CONNAUGHT_STAGE=eda` 可只跑开发期 EDA，`CONNAUGHT_CONFIG=study` 选择正式配置，`CONNAUGHT_OUTPUT` 指定输出目录。修改模块后运行 `python tools/sync_notebook.py` 更新快照，然后重新运行 Notebook。

## 文件组织

```text
DSC5001-Connaught-30min/
├── README.md
├── pyproject.toml            # 项目元数据、依赖和 connaught 命令 / Package metadata
├── requirements.txt          # 兼容旧安装方式 / Legacy dependency install
├── configs/                  # 原型与正式实验配置 / Pilot and study TOML
├── data/                     # 原始车道记录、点位和来源 / Raw, reference and provenance
├── src/connaught/
│   ├── config.py             # 根目录与配置验证 / Project and configuration
│   ├── archives.py           # 官方归档查询、下载、校验与 XML 提取 / Archive ingestion
│   ├── artifacts.py          # JSON 写出与 SHA-256 / JSON and hashing
│   ├── preprocessing.py     # 车道清洗、五分钟聚合和覆盖率 / Cleaning and aggregation
│   ├── eda.py               # 开发期数据探索入口 / Development EDA
│   ├── features.py          # 滞后特征、目标构造和时序切分 / Features and time splits
│   ├── models.py            # 基线、Ridge、随机森林与选参 / Model fitting and tuning
│   ├── evaluation.py        # 误差、分组和配对消融 / Metrics and paired ablation
│   ├── plotting.py           # EDA 和预测诊断图 / EDA and diagnostic figures
│   ├── reporting.py          # HTML 报告生成 / Report generation
│   ├── pipeline.py           # 连接各阶段与输出 / Pipeline orchestration
│   ├── cli.py                # prepare、eda、run 子命令 / Command-line interface
│   └── workflow.py           # 原有 Python 导入的兼容层 / Compatibility imports
├── run_analysis.py           # 旧版分析入口 / Legacy analysis entry point
├── tools/                    # 旧版归档入口与 Notebook 同步 / Archive and notebook tools
├── tests/                    # 开发期 EDA 时间边界测试 / EDA boundary regression test
├── traffic_analysis.ipynb    # 使用同一套模块，附源码 / Shared pipeline and source appendix
└── results/pilot/             # 随包原型数据质量、模型评估和图表 / Bundled pilot results
```

各阶段交接按以下顺序进行。归档工具先生成车道记录和来源清单。清洗得到五分钟面板与覆盖率表。EDA 用开发期图检查缺失和时段模式。特征模块构造预测目标及切分，模型模块输出同一批预测，评估模块计算整体和分组误差，最后生成报告。正式 EDA 与最终测试结果可保存在不同目录，便于分工。

安装项目后可运行 `python -m unittest discover -s tests` 核对默认 EDA 的时间边界。

## 六周扩展

该候选窗口的官方 API 索引已核对到 **42/42 天**。下载由两份月档和一份日档组成，按官方公布大小约 1.94 GB。下载脚本使用 `curl` 并保留系统证书验证。ZIP 缓存在 `.cache/traffic_archives/`，源 ZIP 校验后按 XML 快照提取目标点位。月档只下载一次，按快照文件名前缀选日期。第一次执行前预留缓存、解包过程和模型结果的磁盘空间。

```bash
connaught prepare --config study --probe
connaught prepare --config study --download
connaught run --config study --coverage-only
connaught eda --config study
connaught run --config study
```

先读 `results/study/daily_coverage.csv`，确认每个拟纳入点位的逐日覆盖和研究范围，再执行最后一步。若档案接口变更，可在 [DATA.GOV.HK 归档页面](https://data.gov.hk/en-data/dataset/hk-td-sm_4-traffic-data-strategic-major-roads) 下载脚本报错中指定的包，放入缓存后重试。已有日档和校验清单时，可改用 `--archive-dir PATH --manifest PATH` 处理。

六周后两周是最终测试。前四周使用两个扩展窗口选择参数。训练样本按 **目标时间** 卡边界，测试样本按预测起点卡边界。调参、时段统计、缺失规则和特征选择应在打开最终成绩前冻结。建议先提交点位覆盖表和主模型，干诺道中确认有同口径历史数据后另定扩展配置。

## 协作与结果表

1. 数据同学维护来源清单与窗口配置。所有观察时间以 XML 内时间为准，采用香港时间。
2. 点位和 EDA 同学维护 ID、道路类型与方向口径。天桥和地面分开，不用分组误差推断道路类型的因果影响。
3. 基线与 Ridge 同学核对输入、历史回退和特征消融。随机森林同学在开发折比较叶节点规模。评估同学核对最终行键、统一 MAE 和报告。
4. 修改核心代码后运行 `python tools/sync_notebook.py` 并重新执行 Notebook。同步检查 `--check` 可以发现两个入口的代码漂移。

`predictions.csv` 的主键是 `detector_id, origin, target_end`。其中保留实测值及全部模型预测。评估表包括整体、点位、道路类型、日期、目标时段和周末状态。历史基线的回退级别写入每条预测。短原型的参数预先固定，`cv_scores.csv` 只有列名。按日重采样区间只在有足够测试日期时生成。

正式实证留待六周数据实际解包和覆盖审计。报告中的三天结果用于核对工作流及给出初步量级。

## English

**Connaught Road West and Flyover · 30-Minute-Ahead Detector-Level Mean Speed Forecasting**

A runnable working project for a five-person DSC5001 team. The verified scope covers Connaught Road West and its flyover. Connaught Road Central requires a separate coverage check.

### Forecast target and outputs

The target is the vehicle-count-weighted mean speed (km/h) at one detector in the target five-minute interval. It pools valid 30-second observations from the lanes covered by that detector, weighted by the vehicle count in each observation. Predictions are issued separately for each detector. Traffic flow (vehicles per lane per hour) and occupancy (%) are input features. A forecast issued at 08:00 for a detector covers its 08:25–08:30 mean speed. Forecasts are issued every five minutes.

In `predictions.csv`, `target_speed` is the observed mean speed at that detector and each model column is a prediction for the same detector. `Overall` in `model_metrics.csv` pools errors across the detector-level test rows.

- Generate the Chinese team report with key English terms, lane trial summary and proposal draft locally by running the pilot and opening the resulting `results/pilot/report.html`.
- The [Jupyter notebook](traffic_analysis.ipynb) includes the complete core workflow, bilingual explanations, and pilot outputs. Keep the project directory intact when reproducing the analysis.
- The [pilot configuration](configs/pilot.toml) uses official observations from 16–18 October 2026, with Sunday held out.
- The [study configuration](configs/study.toml) covers 21 September to 1 November 2026, with four development weeks and two test weeks. The full analysis remains pending.

### Lane analysis and design decision

Raw observations are stored by lane. Lane counts determine coverage, and valid records are pooled by vehicle count into each detector’s five-minute mean. Adding lane count reduced MAE by less than 0.01 km/h on both pilot holdouts. The lane speed gap gave small gains on matched rows and higher MAE on both days in the all-row variant. The primary analysis therefore forecasts detector means. Separate lane forecasts remain outside its scope, and the gap is a candidate sensitivity check for the six-week data.

See `lane_decision` in `results/pilot/summary.json` for sample counts and MAE.

### Course submission guide

- **Proposal.** Supply a question-style title and team table, two to four background sentences, two or three testable questions, data, methods, validation, expected contribution and limits, a four-week schedule, and references. Include the data URL and access date, observation unit, expected sample size, response and predictors. The pilot establishes feasibility. Study sample sizes and final findings depend on the audit and holdout. Remove template guidance and export at least half a page as `Team-XX-Proposal.pdf`. Check the proposal deadline on the course platform.
- **Main Report.** Use at most 10 pages, including the cover. Follow the template order from motivation, data and EDA through validation, interpretable models, overall comparison, predictor interpretation, robustness and conclusions. Answer each question with a formal result, give two or three evidence-backed recommendations, state limits and one next step, and cite `Team-[XX]-Appendix.pdf`. Trace each figure and table to its configuration, command, output and generating code.
- **Timing.** The proposal template lists 29 November 2026 at 23:59 as the final project deadline, with at least one day of buffer. Assign page speakers and rehearse the approximately eight-minute recording.

| Pages | Available materials | Work needed for final submission |
|---|---|---|
| 3–4, data and EDA | Data-quality and daily-coverage files, coverage and hourly speed plots | Rule-by-rule removal counts, six-week usable sample and two or three development-period figures tied to modelling decisions |
| 5–6, models and coefficients | Two benchmarks, Ridge, random forest and Ridge coefficients | OLS comparison, expanding-fold timeline and signed coefficient plot |
| 7, model comparison | CV, metrics and predictions files | Common-fold CV mean ± SD, per-model 95% test bootstrap intervals and fit times |
| 8–9, interpretation and robustness | Ridge coefficients, subgroup errors and lane trial | Permutation importance, partial dependence, at least one subgroup check and one alternate cleaning rule with retention and errors |
| 10, conclusions and code | Pilot questions and reproduction workflow | Formal answers, recommendations, limitations and a traceable code appendix |

Pilot files are under `results/pilot/` and study outputs under `results/study/`. The pilot CV file has no fold results. The existing day-block interval is for the paired difference between Ridge variants. Per-model test intervals require a separate calculation.

Run the pilot and open the generated report for the page-by-page plan.

### Quick start

Use Python 3.11 or later. Run from the project root. Installation requires a connection. The bundled pilot runs offline afterward.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[notebook]'
connaught eda --config pilot
connaught run --config pilot
python tools/sync_notebook.py --check
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`. After installation, `python -m connaught` is equivalent to `connaught`. The existing `python run_analysis.py` and `python tools/prepare_data.py` entry points also remain available with the dependencies installed.

`eda` builds the panel, coverage files and two figures from development observations by default. The pilot writes to `results/pilot/eda/development/`. Use `--include-holdout` only for all-period descriptive plots after evaluation. `run` fits and evaluates models and writes predictions, metrics, figures and the report. Pass `--output` to use a separate run directory, or `--root PATH` when working outside the checkout.

In Jupyter or VS Code, select the same environment and run all cells. The notebook imports the package and includes verbatim source snapshots. Set `CONNAUGHT_STAGE=eda` for development EDA, `CONNAUGHT_CONFIG=study` for the study or `CONNAUGHT_OUTPUT` for a separate directory. Regenerate the notebook after edits with `python tools/sync_notebook.py`, then rerun its cells.

Run `python -m unittest discover -s tests` to check the default EDA time boundary.

### Six-week study

The official archive index listed **42 of 42 days** in the proposed window. Two monthly ZIPs and one daily ZIP total approximately 1.94 GB according to the published sizes. The download tool uses `curl` with system certificate verification and caches archives under `.cache/traffic_archives/`. It verifies each source ZIP before reading XML. Monthly archives are downloaded once and snapshots are selected by filename date prefix. Allow space for the downloads, extraction, and results.

```bash
connaught prepare --config study --probe
connaught prepare --config study --download
connaught run --config study --coverage-only
connaught eda --config study
connaught run --config study
```

Before the final command, review `results/study/daily_coverage.csv` for day-by-day coverage across candidate detectors. If the archive API changes, retrieve the ZIPs named in the error from the [official archive page](https://data.gov.hk/en-data/dataset/hk-td-sm_4-traffic-data-strategic-major-roads), place them in the cache, and retry. For existing archives and a checksum manifest, use `--archive-dir PATH --manifest PATH`.

Hold out the final two weeks for testing and tune on two expanding-window folds within the first four weeks. Apply training cutoffs to target timestamps and test cutoffs to forecast origins. Freeze tuning, time-of-day summaries, missing-data rules, and feature selection before viewing final scores. Verify coverage and the main model for the current corridor before defining a separate configuration for Connaught Road Central.

### Team workflow and outputs

1. The data owner maintains provenance and experiment windows. Use observation timestamps from the XML in Hong Kong time.
2. The detector and EDA owner maintains detector IDs, roadway types, and direction definitions. Evaluate flyover and surface-road detectors separately. Group errors describe differences in predictive accuracy.
3. The baselines and Ridge owner checks model inputs, historical fallback levels, and feature ablation. The random forest owner compares leaf sizes on development folds. The evaluation owner checks test row keys, MAE, and the report.
4. After editing the canonical workflow, run `python tools/sync_notebook.py` and execute the notebook again. The `--check` option detects source drift.

The key in `predictions.csv` is `detector_id, origin, target_end`. Each row includes the observed speed, every model forecast, and the historical baseline's fallback level. Evaluation tables break down errors by detector, road type, date, target period, and weekend status. The pilot uses fixed hyperparameters, so `cv_scores.csv` contains only column headers. Day-level resampling intervals are generated when there are enough test dates.

The three-day pilot checks the workflow and gives an initial estimate of error. The six-week study requires archive extraction and a detector coverage audit.
