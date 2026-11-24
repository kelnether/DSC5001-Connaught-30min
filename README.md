# Connaught Road West and Flyover · 30-Minute-Ahead Detector-Level Mean Speed Forecasting

[简体中文](#简体中文)

A runnable working project for a five-person DSC5001 team. The verified scope covers Connaught Road West and its flyover. Connaught Road Central requires a separate coverage check.

### Forecast target and outputs

The target is the vehicle-count-weighted mean speed (km/h) at one detector in the target five-minute interval. It pools valid 30-second observations from the lanes covered by that detector, weighted by the vehicle count in each observation. Predictions are issued separately for each detector. Traffic flow (vehicles per lane per hour) and occupancy (%) are input features. A forecast issued at 08:00 for a detector covers its 08:25–08:30 mean speed. Forecasts are issued every five minutes.

In `predictions.csv`, `target_speed` is the observed mean speed at that detector and each model column is a prediction for the same detector. `Overall` in `model_metrics.csv` pools errors across the detector-level test rows.

- The offline team handoff is distributed separately. See [team responsibilities](#team-workflow-and-outputs) for the joint writing plan and each member's technical lead.
- The [Jupyter notebook](traffic_analysis.ipynb) includes the complete core workflow, bilingual explanations, and pilot outputs. Keep the project directory intact when reproducing the analysis.
- The [pilot configuration](configs/pilot.toml) uses official observations from 16–18 October 2026, with Sunday held out.
- The [study configuration](configs/study.toml) covers 21 September to 1 November 2026, with four development weeks and two test weeks. Use the study evidence index below to reproduce the experiment.

### Lane analysis and design decision

Raw observations are stored by lane. Lane counts determine coverage, and valid records are pooled by vehicle count into each detector’s five-minute mean. Adding lane count reduced MAE by less than 0.01 km/h on both pilot holdouts. The lane speed gap gave small gains on matched rows and higher MAE on both days in the all-row variant. The primary analysis therefore forecasts detector means. Separate lane forecasts remain outside its scope, and the gap is a candidate sensitivity check for the six-week data.

See `lane_decision` in `results/pilot/summary.json` for sample counts and MAE.

### Course submission guide

- **Proposal.** Supply a question-style title and team table, two to four background sentences, two or three testable questions, data, methods, validation, expected contribution and limits, a four-week schedule, and references. Include the data URL and access date, observation unit, expected sample size, response and predictors. The pilot establishes feasibility. Study sample sizes and final findings depend on the audit and holdout. Remove template guidance and export at least half a page as `Team-XX-Proposal.pdf`. Check the proposal deadline on the course platform.
- **Main Report.** Use at most 10 pages, including the cover. Follow the template order from motivation, data and EDA through validation, interpretable models, overall comparison, predictor interpretation, robustness and conclusions. Answer each question with a formal result, give two or three evidence-backed recommendations, state limits and one next step, and cite `Team-[XX]-Appendix.pdf`. Trace each figure and table to its configuration, command, output and generating code.
- **Timing.** The proposal template lists 29 November 2026 at 23:59 as the final project deadline, with at least one day of buffer. Assign page speakers and rehearse the approximately eight-minute recording.

| Research or audit item | Reproduction and evidence |
|---|---|
| Frozen lane inventory and official archives | `data/provenance/study_archive_manifest.json` records the three ZIP digests; `study_extraction_audit.json` records all snapshot counts and any unparseable documents. `results/study/data_quality.json` includes individual exclusions and the lane inventory frozen before October 5. |
| Pilot choice of horizon | `python tools/compare_horizons.py` regenerates the matched 15/30-minute comparison using the same training and test origin keys. Results are in `results/horizon_comparison/`. |
| RQ1, models and simple benchmarks | `results/study/model_metrics.csv` reports common-fold CV mean and SD, held-out MAE/RMSE/bias, day-block MAE intervals and measured fitting seconds. `paired_model_comparisons.csv` matches row-level losses for the named contrasts. |
| RQ2, joint value of flow and occupancy | Compare the same two Ridge variants in `results/study/summary.json`. Both retain speed, calendar and detector ID. The experiment adds flow and occupancy jointly and resamples target dates for the paired interval. |
| RQ3, subgroup errors | `results/study/errors_by_group.csv` reports sample counts and errors by detector, road group, target time, weekend and day. |
| Interpretation and coverage robustness | `rf_permutation_importance.csv`, `rf_partial_dependence.csv`, `ridge_coefficients.csv` and `figures/` contain held-out diagnostics. `coverage_robustness_metrics.csv` and `coverage_robustness_ablation.json` compare 60% and 70% on their full test samples and on common keys. |
| Development EDA and frozen protocol | `results/study/eda/development/` excludes the holdout. `frozen_protocol.json` records dates, fold sizes, selections and file hashes before holdout scoring. `study_complete.json` is written at the end of the run. |

The three-day pilot is stored under `results/pilot/` and uses fixed parameters. It has separate counts and interpretation. A lead time of 30 minutes is measured to the end of the forecasted five-minute window.

### Quick start

Use Python 3.11 or later. Run from the project root. Installation requires a connection. The bundled pilot runs offline afterward.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[notebook]'
connaught eda --config pilot
connaught run --config pilot --output results/pilot-recheck
python tools/sync_notebook.py --check
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`. After installation, `python -m connaught` is equivalent to `connaught`. The existing `python run_analysis.py` and `python tools/prepare_data.py` entry points also remain available with the dependencies installed.

`eda` builds the panel, coverage files and two figures from development observations by default. The pilot writes to `results/pilot/eda/development/`. Use `--include-holdout` only for all-period descriptive plots after evaluation. `run` fits and evaluates models and writes predictions, metrics and figures. The pilot run can also generate its own HTML analysis page. Pass `--output` to use a separate run directory, or `--root PATH` when working outside the checkout.

In Jupyter or VS Code, select the same environment and run all cells. The notebook imports the package and includes verbatim source snapshots. Set `CONNAUGHT_STAGE=eda` for development EDA, `CONNAUGHT_CONFIG=study` for the study or `CONNAUGHT_OUTPUT` for a separate directory. Regenerate the notebook after edits with `python tools/sync_notebook.py`, then rerun its cells.

Run `python -m unittest discover -s tests` to check the default EDA time boundary.

### Reading the run output

Terminal and notebook output is labelled by the package module. Archive preparation reports ZIP checks and extracted row counts. Coverage and EDA report the input window and generated files. A full run also shows feature eligibility, the chronological split, model parameters, comparable errors, and paths to the analytical output. The notebook sync command reports the generated file or verifies source parity.

### Six-week study

**Verified run (24 November 2026, Hong Kong time).** The three official archives yielded 2,267,922 lane rows over 42 days. The extraction audit logged 1 malformed XML snapshot on September 30. No new lane labels appeared after October 5. The 60% threshold yielded 104,009 usable five-minute speed bins, 32,848 training rows and 35,239 test rows over 14 dates.

- **RQ1.** RF led the six models with MAE 3.542 km/h, a reduction of 21.0% versus Persistence. The two-fold validation, intervals and fit times are in `model_metrics.csv`.
- **RQ2.** Adding flow and occupancy jointly reduced Ridge MAE by 0.076 km/h (95% day-block interval 0.053 to 0.102). On the 4,294 common holdout rows, the reductions were 0.067 at 60% and 0.070 at 70%. The higher threshold leaves only 12.2% of the main test rows and 89 first-fold training rows.
- **RQ3.** Consult the subgroup table with sample counts. AID04104 had no usable development windows and returned in the holdout with 2,083 predictions. The historical baseline falls back to Persistence at this site and the encoder handles its unseen ID without a learned site effect.

`python tools/verify_study.py` checks the available source hashes, forecast window and target alignment, common keys, test metrics and CV summaries. Pass `--archive-dir` to rehash the source ZIPs as well.

The official archive index lists **42 of 42 days** in the proposed window. Two monthly ZIPs and one daily ZIP total approximately 1.94 GB according to the published sizes. The download tool uses `curl` with system certificate verification and caches archives under `.cache/traffic_archives/`. It verifies each source ZIP before reading XML. Monthly archives are downloaded once and snapshots are selected by filename date prefix. Allow space for the downloads, extraction, and results. If the extracted input is already present, run the analysis offline and skip the archive preparation commands.

```bash
connaught prepare --config study --probe
connaught prepare --config study --download
connaught run --config study --coverage-only --output results/study-coverage-review
connaught eda --config study
connaught run --config study
```

Before the final command, review `results/study-coverage-review/daily_coverage.csv` for day-by-day coverage across candidate detectors. If the archive API changes, retrieve the ZIPs named in the error from the [official archive page](https://data.gov.hk/en-data/dataset/hk-td-sm_4-traffic-data-strategic-major-roads), place them in the cache, and retry. For existing archives and a checksum manifest, use `--archive-dir PATH --manifest PATH`.

Hold out the final two weeks for testing and tune on two expanding-window folds within the first four weeks. Apply training cutoffs to target timestamps and test cutoffs to forecast origins. Freeze tuning, time-of-day summaries, missing-data rules, and feature selection before viewing final scores. Verify coverage and the main model for the current corridor before defining a separate configuration for Connaught Road Central.

### Team workflow and outputs

**Shared writing and review.** All five members write the motivation, forecast definition, research questions, principal results, limitations, and recommendations together. Use the same frozen split, prediction keys, figures and metrics throughout. Check the link from each question to its experiment and answer together, cross-review each named section and its source files, and prepare the presentation as a team.

**Individual leads.** Roles follow the submitted Team 100004 Proposal. Each lead prepares the evidence for the sections below and hands it to the next reviewer. The separate handoff highlights these roles beside the relevant sections.

| Member | Individual lead | Evidence and review |
|---|---|---|
| **XIA Tianquan** | Archive retrieval, cleaning and coverage audit | ZIP hashes and exclusion log, frozen lane inventory and daily coverage. Give DENG the site coverage and check 60% vs 70% with ZHANG. |
| **DENG Tianyu** | Research scope, development EDA and historical baseline | Forecast definition, EDA plots, baseline rules and fallbacks. Confirm detector scope with XIA and baseline predictions with LI. |
| **ZHAO Yining** | Ridge, paired flow and occupancy ablation, and coefficients | Two Ridge specifications, coefficient plot and paired MAE interval. Match input columns and scores with ZHANG and LI. |
| **ZHANG Yue** | Random Forest, time validation and robustness | Fold boundaries and tuning, RF interpretation and two thresholds on common rows. Confirm coverage with XIA and model comparisons with ZHAO. |
| **LI Wenhao** | Evaluation, reproducibility and report integration | Overall, subgroup and date tables, independent numerical checks and the source-to-figure index. Coordinate review with all four members. |

The key in `predictions.csv` is `detector_id, origin, target_end`. Each row includes the observed speed, every model forecast, and the historical baseline's fallback level. Evaluation tables break down errors by detector, road type, date, target period, and weekend status. The pilot uses fixed hyperparameters, so `cv_scores.csv` contains only column headers. Day-level resampling intervals are generated when there are enough test dates.

Run the six-week study from the frozen configuration. Its output includes separate development-only EDA and observations, predictions and errors for the reported holdout.

## 简体中文

**干诺道西及西天桥 · 检测点级提前 30 分钟平均车速预测**

DSC5001 五人小组的可运行工作底稿。当前范围覆盖干诺道西及西天桥，干诺道中尚待核验。

### 预测目标与结果口径

预测目标是每个检测点在目标 5 分钟内的车辆数加权平均车速（km/h）。汇总该点覆盖车道的有效 30 秒观测，每条观测以其车辆数加权。每个点独立输出，汇总范围止于单个检测点。流量（辆/车道/小时）和占用率（%）是输入特征。 每隔 5 分钟发出一次预测。例如，08:00 发出的预测对应同一检测点 08:25–08:30 的均速。

`predictions.csv` 中，`target_speed` 是该点在目标时段的实测均速，各模型列是预测均速。`model_metrics.csv` 中的 `Overall` 汇总各检测点预测行的误差。

- 离线交接报告另行分发。五人共写内容和个人主责见[协作与结果表](#协作与结果表)。
- [Jupyter Notebook](traffic_analysis.ipynb) · 全部核心逻辑、中英双语逐节说明及原型运行输出。复现时保留完整项目目录。
- [原型配置](configs/pilot.toml) · 2026-10-16 至 2026-10-18。三天实测，周日留出。
- [六周研究配置](configs/study.toml) · 2026-09-21 至 2026-11-01。四周开发、两周测试。从下方的证据索引查看运行方法与结果。

### 车道方案与取舍

原始记录按车道保存。车道数用于覆盖率检查，各车道有效观测按车辆数合并为检测点的 5 分钟均速。原型两天留出对照中，车道数带来的 MAE 降幅均小于 0.01 km/h。车道速度差在共同样本上的改善很小，在全样本版本中两天的 MAE 均上升。因此主分析以检测点为单位，暂不开展逐车道预测。车道速度差保留为六周数据的候选敏感性分析。

两天对照的样本数和 MAE 见 `results/pilot/summary.json` 的 `lane_decision` 字段。

### 按课程模板准备交稿

本节根据课程提供的 `Team-XX-Proposal-Template.pdf` 与 `Team-XX-Main-Report-Template.pdf` 编排。

- **Proposal**。依次准备问题式标题和成员表、2–4 句背景、2–3 个可检验的研究问题、数据、拟用方法、验证与评价、预期贡献与限制、四周时间表、参考资料。数据段给出来源链接与访问日期、观察单位、预计规模、响应和输入。原型只用于说明流程可行，六周有效样本和正式结论待数据审计与评分。填完占位符、删除指导文字后，导出至少半页的 `Team-XX-Proposal.pdf`。Proposal 自身的交稿时间在课程平台核对。
- **Main Report**。最终展示式报告最多 10 页，包含封面。按「封面 → 动机与 RQ → 数据及清洗 → EDA → 模型与验证 → 可解释模型 → 总体比较 → 变量解释 → 稳健性 → 结论」编排。第 10 页用正式数字回答每个 RQ，给目标使用者 2–3 条有证据的建议，列限制与一项后续工作，并注明 `Team-[XX]-Appendix.pdf`。附录逐项对应图表、运行命令、配置、结果文件和生成代码。
- **时间与录屏**。Proposal 模板列出项目最终截止为 **2026 年 11 月 29 日 23:59**，并要求至少预留一天。为约 8 分钟录屏安排每页讲者，先按模板参考时长排练。

| Proposal 与代码核查项目 | 对应入口和产物 |
|---|---|
| 运输署档案、逐日覆盖和车道防泄漏 | `data/provenance/study_archive_manifest.json` 保留 3 个源 ZIP 哈希，`study_extraction_audit.json` 列明快照数与无法解析的源 XML。正式运行的 `data_quality.json` 汇总逐规则剔除数，并记录 10 月 5 日前冻结的车道清单。 |
| 原型时距选择 | `python tools/compare_horizons.py` 用共同训练起点和共同测试起点重现 15／30 分钟对照，输出在 `results/horizon_comparison/`。 |
| RQ1 基线、OLS、Ridge、随机森林 | `results/study/model_metrics.csv` 含共同开发折的 CV 均值和标准差、留出 MAE／RMSE／偏差、按日抽样的 MAE 区间和实测拟合耗时。配对差另见 `paired_model_comparisons.csv`。 |
| RQ2 流量与占用率联合增益 | `results/study/summary.json` 提供两版 Ridge 的配对改善和按日区间。两版都保留近期车速、日历和点位 ID。每版按同一参数网格和验证折单独选参。 |
| RQ3 分组误差 | `results/study/errors_by_group.csv` 按检测点、道路、目标时段、周末和目标日期提供样本数及误差。 |
| 随机森林解释与覆盖率敏感性 | RF 置换重要性、部分依赖和 Ridge 系数的 CSV、图表都在正式目录。60%／70% 分别重训，`coverage_robustness_metrics.csv` 对照各自留出集和共同预测键，配对差和按日区间见 `coverage_robustness_ablation.json`。 |
| 开发期 EDA 和冻结记录 | `results/study/eda/development/` 的图使用开发期。评分前保存 `frozen_protocol.json` 的切分、参数和哈希，最后生成 `study_complete.json`。 |

三天原型继续保存在 `results/pilot/`，使用固定参数。最终报告使用 `results/study/` 的正式证据，并按课程模板编排。

### 快速运行

Python 3.11 或更高版本。在项目根目录运行下面的命令。安装依赖需要网络，随包的三天原型可离线运行。

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[notebook]'
connaught eda --config pilot
connaught run --config pilot --output results/pilot-recheck
python tools/sync_notebook.py --check
```

Windows PowerShell 用 `.venv\Scripts\Activate.ps1` 激活。已安装项目后，也可用 `python -m connaught` 替代 `connaught`。旧入口 `python run_analysis.py` 和 `python tools/prepare_data.py` 仍可在依赖已安装时使用。

`eda` 默认将观察窗口截在测试起始日之前，输出覆盖率、质量统计、五分钟面板和两张 EDA 图。原型默认写入 `results/pilot/eda/development/`。需要做全期描述时才显式使用 `--include-holdout`。`run` 拟合模型并输出预测、误差、图表和报告，默认写入 `results/pilot/` 或 `results/study/`。两个命令都接受 `--output`，各人可以使用独立目录。若从项目外执行，传入 `--root PATH`。

在 Jupyter 或 VS Code 中选择同一环境，打开 `traffic_analysis.ipynb` 并执行 **Run All**。Notebook 直接导入这些模块，末尾附各源码文件的完整快照。设置 `CONNAUGHT_STAGE=eda` 可只跑开发期 EDA，`CONNAUGHT_CONFIG=study` 选择正式配置，`CONNAUGHT_OUTPUT` 指定输出目录。修改模块后运行 `python tools/sync_notebook.py` 更新快照，然后重新运行 Notebook。

### 如何读运行输出

终端和 Notebook 会按模块显示输入、处理范围、样本数和保存位置。方括号内的模块名对应 `src/connaught/` 中的文件。例如 `[connaught.preprocessing]` 对应 `preprocessing.py`。

| 命令 | 终端输出与保存结果 |
|---|---|
| `connaught prepare --config study --probe` | 查询日期、可用天数和归档索引路径 |
| `connaught prepare --config study --download` | 下载和校验 ZIP、逐日 XML 数和提取行数、车道记录与审计清单路径 |
| `connaught run --config pilot --coverage-only` | 输入及有效记录数、可用点位和时间窗、三份覆盖率及质量文件 |
| `connaught eda --config pilot` | 开发期范围、五分钟面板、覆盖率统计和两张图的路径 |
| `connaught run --config pilot` | 清洗、特征和时间切分、训练的模型和参数、共同样本误差、四张图和 HTML 报告位置 |
| `python tools/sync_notebook.py` / `--check` | 生成的 Notebook 路径或源码一致性核对结果 |

例如完整原型的清洗阶段会显示输入 **181,455** 条车道记录、保留 **157,011** 条有效记录。时间切分会显示 **5,083** 条训练行和 **2,454** 条测试行。模型误差表最后统一显示 MAE、RMSE 和平均偏差。

### 文件组织

```text
connaught_30min_project/
├── README.md
├── pyproject.toml            # Package metadata / 项目元数据、依赖和 connaught 命令
├── requirements.txt          # Legacy dependency install / 兼容旧安装方式
├── configs/                  # Pilot and study TOML / 原型与正式实验配置
├── data/                     # Raw, reference and provenance / 原始车道记录、点位和来源
├── src/connaught/
│   ├── config.py             # Project and configuration / 根目录与配置验证
│   ├── archives.py           # Archive ingestion / 官方归档查询、下载、校验与 XML 提取
│   ├── artifacts.py          # JSON and hashing / JSON 写出与 SHA-256
│   ├── preprocessing.py     # Cleaning and aggregation / 车道清洗、五分钟聚合和覆盖率
│   ├── eda.py               # Development EDA / 开发期数据探索入口
│   ├── features.py          # Features and time splits / 滞后特征、目标构造和时序切分
│   ├── models.py            # Model fitting and tuning / 基线、Ridge、随机森林与选参
│   ├── evaluation.py        # Metrics and paired ablation / 误差、分组和配对消融
│   ├── plotting.py           # EDA and diagnostic figures / EDA 和预测诊断图
│   ├── reporting.py          # Report generation / HTML 报告生成
│   ├── pipeline.py           # Pipeline orchestration / 连接各阶段与输出
│   ├── cli.py                # Command-line interface / prepare、eda、run 子命令
│   └── workflow.py           # Compatibility imports / 原有 Python 导入的兼容层
├── run_analysis.py           # Legacy analysis entry point / 旧版分析入口
├── tools/                    # Archive and notebook tools / 旧版归档入口与 Notebook 同步
├── tests/                    # EDA boundary regression test / 开发期 EDA 时间边界测试
├── traffic_analysis.ipynb    # Shared pipeline and source appendix / 使用同一套模块，附源码
└── results/pilot/             # Bundled pilot results / 随包原型数据质量、模型评估和图表
```

各阶段交接按以下顺序进行。归档工具先生成车道记录和来源清单。清洗得到五分钟面板与覆盖率表。EDA 用开发期图检查缺失和时段模式。特征模块构造预测目标及切分，模型模块输出同一批预测，评估模块计算整体和分组误差，最后生成报告。正式 EDA 与最终测试结果可保存在不同目录，便于分工。

安装项目后可运行 `python -m unittest discover -s tests` 核对默认 EDA 的时间边界。

### 六周正式实验

**实跑核查（2026 年 11 月 24 日，香港时间）。** 三份官方档案覆盖 42 天，提取 2,267,922 条车道记录。9 月 30 日有 1 份源 XML 无法解析，已在提取审计中逐条登记。10 月 5 日后未出现新增车道标签。60% 主门槛保留 104,009 个有效五分钟窗，训练 32,848 行，在 14 天上留出 35,239 行。

- **RQ1。** 随机森林的留出 MAE 为 3.542 km/h，六种方法中最低，比 Persistence 低 21.0%。
- **RQ2。** 两版 Ridge 的配对 MAE 改善为 0.076 km/h，按日分块的 95% 区间为 0.053 至 0.102。在 4,294 个共同留出行上，60% 与 70% 分别改善 0.067 和 0.070 km/h。70% 只保留主测试样本的 12.2%，首折训练仅 89 行。
- **RQ3。** 分组表同时给出点位、时段、日期与样本数。AID04104 开发期没有可用窗口，留出期重新出现，共有 2,083 条预测。历史基线在这个点回退到 Persistence，模型通过未见类别处理进行预测。

`python tools/verify_study.py` 核对源码和输入哈希、逐行时间及目标值、误差复算、样本交集和 CV 汇总。指定 `--archive-dir` 可以同时复查原始 ZIP。

该候选窗口的官方 API 索引已核对到 **42/42 天**。下载由两份月档和一份日档组成，按官方公布大小约 1.94 GB。下载脚本使用 `curl` 并保留系统证书验证。ZIP 缓存在 `.cache/traffic_archives/`，源 ZIP 校验后按 XML 快照提取目标点位。月档只下载一次，按快照文件名前缀选日期。第一次执行前预留缓存、解包过程和模型结果的磁盘空间。随包已有提取数据时可跳过前两条归档命令并离线复跑。

```bash
connaught prepare --config study --probe
connaught prepare --config study --download
connaught run --config study --coverage-only --output results/study-coverage-review
connaught eda --config study
connaught run --config study
```

先读 `results/study-coverage-review/daily_coverage.csv`，确认每个拟纳入点位的逐日覆盖和研究范围，再执行最后一步。若档案接口变更，可在 [DATA.GOV.HK 归档页面](https://data.gov.hk/en-data/dataset/hk-td-sm_4-traffic-data-strategic-major-roads) 下载脚本报错中指定的包，放入缓存后重试。已有日档和校验清单时，可改用 `--archive-dir PATH --manifest PATH` 处理。

六周后两周是最终测试。前四周使用两个扩展窗口选择参数。训练样本按 **目标时间** 卡边界，测试样本按预测起点卡边界。调参、时段统计、缺失规则和特征选择应在打开最终成绩前冻结。建议先提交点位覆盖表和主模型，干诺道中确认有同口径历史数据后另定扩展配置。

### 协作与结果表

**五人共写。** 一起写研究动机、预测口径、三个 RQ 的主结论、局限和建议。共同核对时间切分、共同样本、图表出处和代码索引，并一起准备展示。合稿使用一套正式实验结果；每个结论都能在其他章节找到对应问题、实验安排和实际数字。

**个人主责。** 沿用已提交 Proposal 的五人分工。每位组员先把自己的证据写清楚，再按下表互审。离线交接稿在对应技术章节按姓名高亮主责。

| 组员 | 个人主责 | 交接材料与互审 |
|---|---|---|
| **XIA Tianquan** | 归档提取、清洗、覆盖率审计 | 归档哈希、清洗台账、冻结车道清单、逐日覆盖。把点位覆盖交 DENG，与 ZHANG 核对 60%／70% 口径。 |
| **DENG Tianyu** | 研究范围、开发期 EDA、历史基线 | 预测口径、两张开发期图、基线规则及回退结果。与 XIA 对点位，与 LI 复核基线预测。 |
| **ZHAO Yining** | Ridge、流量与占用率消融、系数解释 | 两版模型、系数图、配对 MAE 差和区间。与 ZHANG、LI 对齐输入和评分口径。 |
| **ZHANG Yue** | 随机森林、时序验证、稳健性 | 切分选参与 RF 解释、两个门槛的共同样本对照。和 XIA 核对覆盖，与 ZHAO 对照模型。 |
| **LI Wenhao** | 评价、复现、合稿与索引 | 总体、分组和日期结果、核查记录、代码与图表索引。向四位主责组员逐条核对，五人一起定稿。 |

`predictions.csv` 的主键是 `detector_id, origin, target_end`。其中保留实测值及全部模型预测。评估表包括整体、点位、道路类型、日期、目标时段和周末状态。历史基线的回退级别写入每条预测。短原型的参数预先固定，`cv_scores.csv` 只有列名。按日重采样区间只在有足够测试日期时生成。

三天原型用于核对工作流与时距方向。正式结果、逐日覆盖和稳健性分析以六周目录为准。
