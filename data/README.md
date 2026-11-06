# 数据说明

预测目标是每个检测点在目标 5 分钟内的车辆数加权平均车速（km/h）。汇总该点覆盖车道的有效 30 秒观测，每条观测以其车辆数加权。每个点独立输出，汇总范围止于单个检测点。流量（辆/车道/小时）和占用率（%）是输入特征。

原始记录按车道保存。生成的 5 分钟面板以 `detector_id, bin_end` 为键，`speed` 为该点实测均速。预测表以 `detector_id, origin, target_end` 为键。

- `reference/detectors.csv` 来自运输署官方点位表的干诺道西及西天桥记录，保留官方点位 ID、地名、经纬度及位置表方向。目录方向字段与道路文字方向存在口径差别，不用于推断同方向上下游。
- `raw/pilot/lane_observations.csv.gz` 保留源 XML 的观测日期、区间、点位、车道、数值、有效标记、快照路径和归档日期。可能包含日档内午夜前的记录，清洗时按 XML 观测时间筛选。
- `provenance/pilot_archive_manifest.json` 是三个源 ZIP 的官方 URL、字节数、SHA-256 及 XML 数。提取程序首先核对归档 SHA-256，再读取 XML。
- `provenance/pilot_extraction_audit.json` 记录逐档案 XML、观测区间和提取行数。车道子集的 SHA-256 见 `results/pilot/summary.json`。
- `provenance/study_archive_probe.json` 保存候选正式窗口的官方元数据响应摘要。索引含快照版本数与归档包大小。它还没有经过干诺道逐日覆盖审计。

## 车道字段如何使用

原始记录按车道保存。车道数用于覆盖率检查，各车道有效观测按车辆数合并为检测点的 5 分钟均速。原型两天留出对照中，车道数带来的 MAE 降幅均小于 0.01 km/h。车道速度差在共同样本上的改善很小，在全样本版本中两天的 MAE 均上升。因此主分析以检测点为单位，暂不开展逐车道预测。车道速度差保留为六周数据的候选敏感性分析。

车道标签以每点原始数据为准，覆盖率分母按点计算。比较车道速度差时，至少需要两条有车且各自满足记录门槛的车道。

数据来源为 [香港运输署主要道路交通数据](https://data.gov.hk/en-data/dataset/hk-td-sm_4-traffic-data-strategic-major-roads)。字段与单位见 [官方数据字典](https://static.data.gov.hk/td/traffic-data-strategic-major-roads/dataspec/dataspec-traffic-data-strategic-major-roads.pdf)。

## English

The target is the vehicle-count-weighted mean speed (km/h) at one detector in the target five-minute interval. It pools valid 30-second observations from the lanes covered by that detector, weighted by the vehicle count in each observation. Predictions are issued separately for each detector. Traffic flow (vehicles per lane per hour) and occupancy (%) are input features.

The raw file stores lane observations. The five-minute panel is keyed by `detector_id, bin_end`, with the observed detector mean in `speed`. The prediction table is keyed by `detector_id, origin, target_end`.

- `reference/detectors.csv` selects Connaught Road West and flyover entries from the official Transport Department detector table. It retains detector IDs, place names, coordinates, and the directions listed in the source table. The directory direction labels differ from the wording in the location descriptions, so upstream and downstream relationships require separate verification.
- `raw/pilot/lane_observations.csv.gz` preserves XML observation dates, intervals, detector and lane IDs, readings, validity flags, snapshot paths, and archive dates. A daily archive may contain observations from before midnight. Cleaning filters by the timestamp in the XML.
- `provenance/pilot_archive_manifest.json` records official URLs, byte counts, SHA-256 hashes, and XML snapshot counts for the three source ZIPs. Extraction checks each archive's hash before reading the XML.
- `provenance/pilot_extraction_audit.json` records snapshot counts, time coverage, and extracted row counts for each archive. The hash of the lane subset appears in `results/pilot/summary.json`.
- `provenance/study_archive_probe.json` records the official metadata for the proposed six-week window, including snapshot version counts and archive sizes. Day-by-day coverage for the selected detectors still needs to be audited.

### How lane fields are used

Raw observations are stored by lane. Lane counts determine coverage, and valid records are pooled by vehicle count into each detector’s five-minute mean. Adding lane count reduced MAE by less than 0.01 km/h on both pilot holdouts. The lane speed gap gave small gains on matched rows and higher MAE on both days in the all-row variant. The primary analysis therefore forecasts detector means. Separate lane forecasts remain outside its scope, and the gap is a candidate sensitivity check for the six-week data.

Source and field definitions are available from the [Hong Kong Transport Department dataset](https://data.gov.hk/en-data/dataset/hk-td-sm_4-traffic-data-strategic-major-roads) and its [official data dictionary](https://static.data.gov.hk/td/traffic-data-strategic-major-roads/dataspec/dataspec-traffic-data-strategic-major-roads.pdf).
