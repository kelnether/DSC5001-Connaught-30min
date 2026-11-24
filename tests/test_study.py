"""Guard against study leakage and wrong resampling units. / 防止正式实验的车道泄漏和抽样单位错误。"""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

import numpy as np
import pandas as pd

from connaught.archives import prepare_lane_subset
from connaught.artifacts import sha256_file
from connaught.preprocessing import build_panel
from connaught.study_diagnostics import bootstrap_mae


class StudyTest(unittest.TestCase):
    def test_unreadable_xml_stays_in_audit_without_partial_rows(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sites.csv").write_text("detector_id\nA\n")
            archive = root / "20261001.zip"
            with ZipFile(archive, "w") as package:
                package.writestr("broken.xml", "<root><date")
                package.writestr(
                    "valid.xml",
                    "<root><date>2026-10-01</date><periods><period><period_from>00:00:00</period_from>"
                    "<period_to>00:00:30</period_to><detectors><detector><detector_id>A</detector_id>"
                    "<lanes><lane><lane_id>known</lane_id><speed>50</speed><volume>1</volume><occupancy>5</occupancy>"
                    "<valid>Y</valid></lane></lanes></detector></detectors></period></periods></root>",
                )
            manifest = [{"day": "20261001", "size_bytes": archive.stat().st_size,
                         "version_count": 2, "sha256": sha256_file(archive)}]
            config = {"input": "rows.csv.gz", "detectors": "sites.csv", "start": "2026-10-01",
                      "end_exclusive": "2026-10-02", "manifest": "manifest.json", "extraction_audit": "audit.json"}
            with self.assertRaisesRegex(ValueError, "broken.xml"):
                prepare_lane_subset(root, config, root, manifest)
            self.assertFalse((root / "rows.csv.gz").exists())
            audit = prepare_lane_subset(root, {**config, "skip_invalid_snapshots": True}, root, manifest)
            self.assertEqual(audit[0]["snapshots"], 2)
            self.assertEqual(audit[0]["invalid_snapshots"][0]["member"], "broken.xml")
            self.assertEqual(pd.read_csv(root / "rows.csv.gz")["speed"].tolist(), [50])

    def test_later_lane_cannot_change_early_window(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            pd.DataFrame({"detector_id": ["A"], "road_group": ["Surface"]}).to_csv(root / "sites.csv", index=False)
            rows = []
            for day in (1, 2):
                for second in range(0, 300, 30):
                    start = pd.Timestamp(f"2026-10-0{day}") + pd.Timedelta(seconds=second)
                    for lane in (["known"] if day == 1 else ["known", "new"]):
                        rows.append({"date": str(start.date()), "period_from": start.strftime("%H:%M:%S"),
                                     "period_to": (start + pd.Timedelta(seconds=30)).strftime("%H:%M:%S"),
                                     "detector_id": "A", "lane_id": lane, "speed": 50 if lane == "known" else 100,
                                     "volume": 2, "occupancy": 10, "valid": "Y", "snapshot": "s1", "archive_day": str(day)})
            pd.DataFrame(rows).to_csv(root / "raw.csv", index=False)
            config = {"input": "raw.csv", "detectors": "sites.csv", "start": "2026-10-01",
                      "end_exclusive": "2026-10-03", "lane_inventory_cutoff": "2026-10-02", "min_coverage": .60}
            panel, _, quality = build_panel(root, config)
            usable = panel[panel["speed"].notna()]
            np.testing.assert_array_equal(usable["speed"], [50, 50])
            np.testing.assert_array_equal(usable["coverage"], [1., 1.])
            self.assertEqual(quality["lane_inventory"]["later_only_valid_rows_excluded"], 10)

    def test_day_bootstrap_constant_errors_and_minimum_days(self):
        days = pd.date_range("2026-10-01", periods=7).repeat([1, 3, 7, 1, 2, 5, 2])
        pred = pd.DataFrame({"target_day": days, "target_speed": 50, "a": 52, "b": 49})
        interval = bootstrap_mae(pred, ("a", "b"), seed=42)
        np.testing.assert_allclose(interval[["mae_ci_low", "mae_ci_high"]], [[2, 2], [1, 1]])
        too_short = bootstrap_mae(pred[pred["target_day"].lt(days[-1])], ("a", "b"), seed=42)
        self.assertTrue(too_short["mae_ci_low"].isna().all())


if __name__ == "__main__":
    unittest.main()
