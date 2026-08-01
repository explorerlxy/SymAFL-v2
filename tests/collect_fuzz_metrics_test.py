#!/usr/bin/env python3
"""Unit tests for scripts/collect-fuzz-metrics.py."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "collect-fuzz-metrics.py"


def load_module():
    spec = importlib.util.spec_from_file_location("collect_fuzz_metrics", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CollectFuzzMetricsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_module()

    def write(self, directory: Path, name: str, text: str) -> Path:
        path = directory / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_pcbt_primary_is_test_throughput(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            stats = self.write(tmp_path, "fuzzer_stats", """\
start_time        : 1000
last_update       : 1030
execs_done        : 3000
execs_per_sec     : 95.0
paths_total       : 4
unique_crashes    : 0
unique_hangs      : 0
""")
            log = self.write(tmp_path, "afl.log", """\
[pcbt] traces=10 nodes=8 depth=3 conflicts=0 failed=0 timeouts=0 memerr=0 screened=20 admitted=5 vetoed=15 saturated=0 selfcheck_fail=0 single_pass=2 single_pass_overflow=1
""")
            result = self.mod.collect(stats, log, {"mode": "pcbt"})
            self.assertTrue(result["complete"])
            self.assertEqual(result["elapsed_seconds"], 30)
            self.assertEqual(result["afl_execution_throughput_per_sec"], 100.0)
            self.assertEqual(result["test_units"], 20)
            self.assertEqual(result["test_throughput_per_sec"], 20 / 30)
            self.assertEqual(result["primary_throughput_metric"],
                             "test_throughput_per_sec")
            self.assertEqual(result["afl"]["execs_done"], 3000)
            self.assertEqual(result["pcbt"]["vetoed"], 15)
            self.assertEqual(result["pcbt"]["admitted"], 5)
            self.assertEqual(result["admitted_vs_execs_delta"], 5 - 3000)

    def test_baseline_falls_back_to_exec_throughput(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            stats = self.write(tmp_path, "fuzzer_stats", """\
start_time        : 10
last_update       : 20
execs_done        : 100
execs_per_sec     : 9.5
""")
            result = self.mod.collect(stats, None, {"mode": "afl"})
            self.assertTrue(result["complete"])
            self.assertEqual(result["test_throughput_per_sec"], 10.0)
            self.assertEqual(result["primary_throughput_metric"],
                             "afl_execution_throughput_per_sec")

    def test_missing_stats_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result = self.mod.collect(tmp_path / "missing", None, {"mode": "afl"})
            self.assertFalse(result["complete"])
            self.assertIn("missing fuzzer_stats", result["problems"])

    def test_non_positive_elapsed_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            stats = self.write(tmp_path, "fuzzer_stats", """\
start_time        : 50
last_update       : 50
execs_done        : 10
""")
            result = self.mod.collect(stats, None, {"mode": "afl"})
            self.assertFalse(result["complete"])
            self.assertIn("non-positive fuzzer_stats elapsed time",
                          result["problems"])


if __name__ == "__main__":
    unittest.main()
