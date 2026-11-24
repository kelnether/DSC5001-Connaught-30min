"""Discover, download and extract official lane archives. / 官方归档查询、下载及车道 XML 提取。"""

from concurrent.futures import ThreadPoolExecutor
import csv
import gzip
import json
import logging
from pathlib import Path
import shutil
import subprocess
from urllib.parse import urlencode
import xml.etree.ElementTree as ET
import zipfile

import pandas as pd

from .artifacts import sha256_file, write_json

logger = logging.getLogger(__name__)


SOURCE_XML = "https://resource.data.one.gov.hk/td/traffic-detectors/rawSpeedVol-all.xml"
ARCHIVE_API = "https://app.data.gov.hk/v1/historical-archive/"
DATA_COLUMNS = [
    "date", "period_from", "period_to", "detector_id", "direction", "lane_id",
    "speed", "volume", "occupancy", "speed_sd", "valid", "snapshot", "archive_day",
]


def archive_dates(config):
    return pd.date_range(config["start"], config["end_exclusive"], inclusive="left", freq="D").strftime("%Y%m%d").tolist()


def archive_url(endpoint, **params):
    return ARCHIVE_API + endpoint + "?" + urlencode({"url": SOURCE_XML, **params})


def fetch_archive_resource(url, destination=None):
    args = ["curl", "--fail", "--location", "--silent", "--show-error",
            "--connect-timeout", "20", "--max-time", "1800" if destination else "45",
            "--user-agent", "DSC5001-Connaught-Research/0.1"]
    if destination:
        args += ["--output", str(destination), "--write-out", "%{url_effective}"]
    if not shutil.which("curl"):
        raise RuntimeError("Online archive retrieval requires curl on PATH. / 在线获取归档需要 curl。")
    result = subprocess.run([*args, url], capture_output=True, check=False)
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Archive request failed. / 归档请求失败。 {detail}")
    return result.stdout


def fetch_json(url):
    return json.loads(fetch_archive_resource(url))


def probe_archives(config):
    """Check daily snapshot counts and the available official ZIP packaging. / 核对逐日快照数量及官方 ZIP 归档方式。"""
    days = archive_dates(config)
    logger.info("Querying official snapshot and ZIP metadata for %d days. / 查询官方快照与 ZIP 元数据。", len(days))

    def one_day(day):
        try:
            body = fetch_json(archive_url("list-file-versions", start=day, end=day))
            packages = body.get("data-files", [])
            bundle = next((f for f in packages if f.get("period") == "D" and f.get("timestamp") == day), None)
            if bundle is None:
                bundle = next((f for f in packages if f.get("period") == "M" and
                               str(f.get("timestamp", ""))[:6] == day[:6]), None)
            return {"day": day, "snapshot_versions": body.get("version-count"),
                    "official_package": bundle}
        except (OSError, ValueError, RuntimeError) as exc:
            return {"day": day, "error": str(exc)}

    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(one_day, days))


def archive_members(archive, day_prefix=None):
    return sorted(name for name in archive.namelist() if name.lower().endswith(".xml")
                  and (not day_prefix or Path(name).name.startswith(day_prefix + "-")))


def download_archives(config, archive_dir, probe=None):
    """Download each advertised daily or monthly ZIP once and reuse it. / 每个官方日档或月档只下载一次并复用。"""
    archive_dir.mkdir(parents=True, exist_ok=True)
    rows = probe if probe is not None else probe_archives(config)
    if [r["day"] for r in rows] != archive_dates(config):
        raise ValueError("Archive probe dates differ from configured dates. / 归档查询日期与配置不符。")
    missing = [r["day"] for r in rows if not r.get("official_package") or not r.get("snapshot_versions")]
    if missing:
        raise ValueError(f"Missing advertised archives for {missing}. Check the probe before downloading. / 部分日期缺少归档，下载前请核对查询结果。")
    verified = {}
    manifest = []
    for row in rows:
        day, bundle = row["day"], row["official_package"]
        key = bundle["timestamp"]
        month = bundle["period"] == "M"
        url = archive_url("get-file", time=key)
        path = archive_dir / (f"{key[:6]}-monthly.zip" if month else f"{day}.zip")
        if path not in verified:
            resolved = None
            advertised = int(bundle["size"])
            if not path.is_file():
                logger.info("Downloading %s (%s bytes). / 正在下载归档。", path.name, f"{advertised:,}")
                temp = path.with_suffix(".part")
                try:
                    resolved = fetch_archive_resource(url, temp).decode("utf-8")
                    if temp.stat().st_size != advertised or not zipfile.is_zipfile(temp):
                        raise ValueError(f"{path.name}: response differs from advertised ZIP. / 下载文件与官方公布的 ZIP 不符。")
                    temp.replace(path)
                except RuntimeError as exc:
                    raise RuntimeError(f"{key}: {exc}. Retrieve the advertised ZIP "
                                       f"through DATA.GOV.HK and place it at {path}. / 请从 DATA.GOV.HK 下载归档并放到上述路径。") from exc
                finally:
                    temp.unlink(missing_ok=True)
            if path.stat().st_size != advertised:
                raise ValueError(f"{path.name}: cached size differs from official metadata. / 缓存大小与官方元数据不符。")
            with zipfile.ZipFile(path) as archive:
                members = archive_members(archive)
            verified[path] = (resolved, sha256_file(path), members)
            logger.info("Verified ZIP size and computed SHA-256 for %s (%s XML files). / 已核对 ZIP 大小并计算 SHA-256。", path, f"{len(members):,}")
        resolved, digest, members = verified[path]
        prefix = day if month else None
        count = sum(not prefix or Path(n).name.startswith(prefix + "-") for n in members)
        if count != row["snapshot_versions"]:
            raise ValueError(f"{day}: archive has {count} matching snapshots; API lists {row['snapshot_versions']}. / XML 数量与官方接口记录不符。")
        manifest.append({"day": day, "source_url": SOURCE_XML, "retrieval_url": url,
                         "resolved_url": resolved, "size_bytes": path.stat().st_size,
                         "sha256": digest, "version_count": count,
                         "archive_file": path.name, "member_day_prefix": prefix,
                         "origin": "official API" if resolved else "local archive cache"})
    return manifest


def prepare_lane_subset(root, config, archive_dir, manifest):
    """Stream selected detector rows from each archive and preserve snapshot lineage. / 从每个归档流式读取目标检测器记录并保留快照来源。"""
    days = archive_dates(config)
    entries = {r["day"]: r for r in manifest}
    if set(days) != set(entries):
        raise ValueError("Manifest dates must match the configuration. / 清单日期必须与配置一致。")
    ids = set(pd.read_csv(root / config["detectors"], dtype=str)["detector_id"])
    logger.info("Verifying %d days of local archives and extracting lane records for %d detectors. / 校验本地档案并提取目标点位的车道记录。", len(days), len(ids))
    hashes = {}
    for day in days:
        item = entries[day]
        path = archive_dir / item.get("archive_file", f"{day}.zip")
        if path not in hashes:
            hashes[path] = sha256_file(path)
        if path.stat().st_size != item["size_bytes"] or hashes[path] != item["sha256"]:
            raise ValueError(f"{path}: size or SHA-256 mismatch. / 文件大小或 SHA-256 不符。")
    out = root / config["input"]
    out.parent.mkdir(parents=True, exist_ok=True)
    temp = out.with_suffix(".part")
    audit = []
    skip_invalid = config.get("skip_invalid_snapshots", False)
    try:
        with gzip.open(temp, "wt", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=DATA_COLUMNS)
            writer.writeheader()
            for day in days:
                totals = {"day": day, "snapshots": 0, "periods": 0, "selected_lane_rows": 0}
                if skip_invalid:
                    totals["invalid_snapshots"] = []
                item = entries[day]
                with zipfile.ZipFile(archive_dir / item.get("archive_file", f"{day}.zip")) as archive:
                    for member in archive_members(archive, item.get("member_day_prefix")):
                        totals["snapshots"] += 1
                        try:
                            source = ET.fromstring(archive.read(member))
                            date = source.findtext("date")
                            periods = source.findall("./periods/period")
                            if not date or not periods:
                                raise ValueError("Missing XML observation date or periods. / XML 缺少观测日期或时段。")
                        except (ET.ParseError, ValueError) as exc:
                            if not skip_invalid:
                                raise ValueError(f"Invalid XML in {day}/{member}. / XML 格式无效。 {exc}") from exc
                            totals["invalid_snapshots"].append({"member": member, "error": str(exc)})
                            logger.warning("Excluded unreadable source snapshot %s. / 已登记并排除无法解析的源快照。", member)
                            continue
                        for period in periods:
                            start, end = (period.findtext(k) for k in ("period_from", "period_to"))
                            for detector in period.findall("./detectors/detector"):
                                key = detector.findtext("detector_id")
                                if key not in ids:
                                    continue
                                for lane in detector.findall("./lanes/lane"):
                                    row = {k: lane.findtext(k) for k in ("lane_id", "speed", "volume", "occupancy", "valid")}
                                    row.update(date=date, period_from=start, period_to=end,
                                               detector_id=key, direction=detector.findtext("direction"),
                                               speed_sd=lane.findtext("s.d.") or lane.findtext("sd"),
                                               snapshot=member, archive_day=day)
                                    writer.writerow(row)
                                    totals["selected_lane_rows"] += 1
                        totals["periods"] += len(periods)
                if totals["snapshots"] != entries[day]["version_count"]:
                    raise ValueError(f"{day}: XML count differs from manifest. / XML 数量与清单不符。")
                audit.append(totals)
                parsed = totals["snapshots"] - len(totals.get("invalid_snapshots", []))
                logger.info("%s: parsed %s/%s XML files and extracted %s lane records. / 已读取当日 XML 并提取车道记录。",
                            day, f"{parsed:,}", f"{totals['snapshots']:,}", f"{totals['selected_lane_rows']:,}")
        temp.replace(out)
    finally:
        temp.unlink(missing_ok=True)
    write_json(root / config["manifest"], manifest)
    write_json(root / config["extraction_audit"], audit)
    logger.info("Saved %s lane records to %s. / 已保存车道记录。", f"{sum(day['selected_lane_rows'] for day in audit):,}", out)
    logger.info("Saved archive manifest and extraction audit to %s and %s. / 已保存归档清单及提取审计。",
                root / config["manifest"], root / config["extraction_audit"])
    return audit
