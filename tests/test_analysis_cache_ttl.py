from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from uralla_build.errors import StageError
from uralla_build.preprocess_fast import (
    ANALYSIS_CACHE_MAX_AGE_DAYS,
    _validate_analysis_cache_age,
)


class AnalysisCacheTtlTests(unittest.TestCase):
    def test_cache_max_age_is_30_days(self) -> None:
        self.assertEqual(ANALYSIS_CACHE_MAX_AGE_DAYS, 30)

    def test_cache_younger_than_30_days_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "analysis-manifest.json"
            path.write_text("{}", encoding="utf-8")
            now = 2_000_000_000.0
            age = (30 * 24 * 60 * 60) - 1
            os.utime(path, (now - age, now - age))
            _validate_analysis_cache_age(path, now=now)

    def test_cache_at_30_days_is_expired(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "analysis-manifest.json"
            path.write_text("{}", encoding="utf-8")
            now = 2_000_000_000.0
            age = 30 * 24 * 60 * 60
            os.utime(path, (now - age, now - age))
            with self.assertRaises(StageError):
                _validate_analysis_cache_age(path, now=now)


if __name__ == "__main__":
    unittest.main()
