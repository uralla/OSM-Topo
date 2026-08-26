from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
TYP = ROOT / "styles" / "uralla.txt"


class TypNightModeTests(unittest.TestCase):
    def test_direct_typ_has_no_explicit_night_only_fields(self) -> None:
        raw = TYP.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("cp1251")

        self.assertIsNone(re.search(r"(?im)^\s*NightXpm\s*=", text))
        self.assertIsNone(re.search(r"(?im)^\s*NightcustomColor\s*[:=]", text))
        self.assertIsNone(
            re.search(r"(?im)^\s*CustomColor\s*=\s*DayAndNight\s*$", text)
        )


if __name__ == "__main__":
    unittest.main()
