"""核对开发期 EDA 的数据边界。 / Check the development EDA data boundary."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd

from connaught.config import load_config
from connaught.eda import run_eda


class DevelopmentEDATest(unittest.TestCase):
    def test_holdout_observations_are_excluded_by_default(self):
        root = Path(__file__).resolve().parents[1]
        config = load_config(root)
        with TemporaryDirectory() as directory:
            result = run_eda(root, config, directory)
            panel = pd.read_csv(result["output"] / "five_minute_panel.csv.gz", parse_dates=["bin_end"])
            holdout = pd.Timestamp(config["test_start"])
            # 分界点收尾的时间箱属于此前五分钟。 / The bin ending at the boundary belongs to the prior interval.
            self.assertEqual(panel["bin_end"].max(), holdout)
            self.assertTrue((panel["bin_end"] - pd.Timedelta(seconds=1) < holdout).all())
