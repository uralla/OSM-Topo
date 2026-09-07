from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
ROAD_STYLE_FILES = (
    ROOT / "styles" / "uralla" / "lines",
    ROOT / "styles" / "uralla" / "inc" / "road_density",
    ROOT / "styles" / "uralla" / "inc" / "tunnels",
)


def test_highway_rules_do_not_use_per_way_length_gates() -> None:
    violations: list[str] = []
    for path in ROAD_STYLE_FILES:
        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "highway" in line and re.search(r"\blength\s*\(\s*\)", line):
                violations.append(f"{path.relative_to(ROOT)}:{line_number}: {line}")

    assert violations == [], "road length gates remain:\n" + "\n".join(violations)
