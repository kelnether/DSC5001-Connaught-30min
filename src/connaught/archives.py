"""官方归档查询、下载及车道 XML 提取。 / Discover, download and extract official lane archives."""

from concurrent.futures import ThreadPoolExecutor
import csv
import gzip
import json
from pathlib import Path
import shutil
import subprocess
from urllib.parse import urlencode
import xml.etree.ElementTree as ET
import zipfile

import pandas as pd

from .artifacts import sha256_file, write_json


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
        raise RuntimeError("Online archive retrieval requires curl on PATH.")
    result = subprocess.run([*args, url], capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def fetch_json(url):
    return json.loads(fetch_archive_resource(url))


def probe_archives(config):
    """核对逐日快照数量及官方 ZIP 归档方式。 / Check daily snapshot counts and the available official ZIP packaging."""
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
        return list(pool.map(one_day, archive_dates(config)))


def archive_members(archive, day_prefix=None):
    return sorted(name for name in archive.namelist() if name.lower().endswith(".xml")
                  and (not day_prefix or Path(name).name.startswith(day_prefix + "-")))


def download_archives(config, archive_dir, probe=None):
    """每个官方日档或月档只下载一次并复用。 / Download each advertised daily or monthly ZIP once and reuse it."""
    archive_dir.mkdir(parents=True, exist_ok=True)
    rows = probe if probe is not None else probe_archives(config)
    if [r["day"] for r in rows] != archive_dates(config):
        raise ValueError("Archive probe does not match configuration dates.")
    missing = [r["day"] for r in rows if not r.get("official_package") or not r.get("snapshot_versions")]
    if missing:
        raise ValueError(f"Missing advertised archives for {missing}. Review the probe before downloading.")
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
                temp = path.with_suffix(".part")
                try:
                    resolved = fetch_archive_resource(url, temp).decode("utf-8")
                    if temp.stat().st_size != advertised or not zipfile.is_zipfile(temp):
                        raise ValueError(f"{path.name}: response does not match advertised ZIP.")
                    temp.replace(path)
                except RuntimeError as exc:
                    raise RuntimeError(f"{key}: {exc}. Retrieve the advertised ZIP "
                                       f"through DATA.GOV.HK and place it at {path}.") from exc
                finally:
                    temp.unlink(missing_ok=True)
            if path.stat().st_size != advertised:
                raise ValueError(f"{path.name}: cached size differs from official metadata.")
            with zipfile.ZipFile(path) as archive:
                members = archive_members(archive)
            verified[path] = (resolved, sha256_file(path), members)
        resolved, digest, members = verified[path]
        prefix = day if month else None
        count = sum(not prefix or Path(n).name.startswith(prefix + "-") for n in members)
        if count != row["snapshot_versions"]:
            raise ValueError(f"{day}: archive has {count} matching snapshots; API lists {row['snapshot_versions']}.")
        manifest.append({"day": day, "source_url": SOURCE_XML, "retrieval_url": url,
                         "resolved_url": resolved, "size_bytes": path.stat().st_size,
                         "sha256": digest, "version_count": count,
                         "archive_file": path.name, "member_day_prefix": prefix,
                         "origin": "official API" if resolved else "local archive cache"})
    return manifest


def prepare_lane_subset(root, config, archive_dir, manifest):
    """从每个归档流式读取目标检测器记录并保留快照来源。 / Stream selected detector rows from each archive and preserve snapshot lineage."""
    days = archive_dates(config)
    entries = {r["day"]: r for r in manifest}
    if set(days) != set(entries):
        raise ValueError("Manifest dates must match the configuration.")
    ids = set(pd.read_csv(root / config["detectors"], dtype=str)["detector_id"])
    hashes = {}
    for day in days:
        item = entries[day]
        path = archive_dir / item.get("archive_file", f"{day}.zip")
        if path not in hashes:
            hashes[path] = sha256_file(path)
        if path.stat().st_size != item["size_bytes"] or hashes[path] != item["sha256"]:
            raise ValueError(f"{path}: size or SHA-256 mismatch.")
    out = root / config["input"]
    out.parent.mkdir(parents=True, exist_ok=True)
    temp = out.with_suffix(".part")
    audit = []
    try:
        with gzip.open(temp, "wt", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=DATA_COLUMNS)
            writer.writeheader()
            for day in days:
                totals = {"day": day, "snapshots": 0, "periods": 0, "selected_lane_rows": 0}
                item = entries[day]
                with zipfile.ZipFile(archive_dir / item.get("archive_file", f"{day}.zip")) as archive:
                    for member in archive_members(archive, item.get("member_day_prefix")):
                        try:
                            source = ET.fromstring(archive.read(member))
                            date = source.findtext("date")
                            periods = source.findall("./periods/period")
                            if not date or not periods:
                                raise ValueError("missing XML observation date or periods")
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
                            totals["snapshots"] += 1
                        except (ET.ParseError, ValueError) as exc:
                            raise ValueError(f"{day}/{member}: {exc}") from exc
                if totals["snapshots"] != entries[day]["version_count"]:
                    raise ValueError(f"{day}: XML count differs from manifest.")
                audit.append(totals)
                print(f"{day}: {totals['snapshots']} XML, {totals['selected_lane_rows']:,} selected lane rows")
        temp.replace(out)
    finally:
        temp.unlink(missing_ok=True)
    write_json(root / config["manifest"], manifest)
    write_json(root / config["extraction_audit"], audit)
    return audit
