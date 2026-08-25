"""Validation of splitter areas.list and template.args outputs."""

from __future__ import annotations

from pathlib import Path
import re

from .errors import ValidationIssue


AREA_RE = re.compile(r"^\s*([0-9]{1,8}):\s")
MAPNAME_RE = re.compile(r"^\s*mapname:\s*([0-9]{1,8})\s*$")
INPUT_RE = re.compile(r"^\s*input-file:\s*([0-9]{1,8})\.[^\s]+\s*$")


def _read_ids(path: Path, pattern: re.Pattern[str]) -> list[int]:
    ids: list[int] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if match := pattern.match(line):
            ids.append(int(match.group(1)))
    return ids


def read_area_ids(path: str | Path) -> list[int]:
    """Return map IDs in a splitter areas.list file."""

    return _read_ids(Path(path), AREA_RE)


def read_template_ids(path: str | Path) -> tuple[list[int], list[int]]:
    """Return mapname and input-file IDs from splitter template.args."""

    template = Path(path)
    return _read_ids(template, MAPNAME_RE), _read_ids(template, INPUT_RE)


def validate_generated_range(
    product_key: str,
    identity: dict[str, object],
    areas_path: str | Path,
    template_path: str | Path | None = None,
) -> tuple[list[ValidationIssue], dict[str, int | str]]:
    """Validate generated tile IDs against one manifest product block."""

    issues: list[ValidationIssue] = []
    area_file = Path(areas_path)
    location = f"products.{product_key}.generated"
    try:
        ids = read_area_ids(area_file)
    except OSError as exc:
        return [ValidationIssue(location, f"cannot read areas.list: {exc}")], {}
    if not ids:
        return [ValidationIssue(location, "areas.list contains no map IDs")], {}

    overview = int(str(identity["overview_mapnumber"]))
    first_reserved = int(str(identity["first_tile_mapid"]))
    last_reserved = int(str(identity["last_reserved_mapid"]))
    unique_ids = sorted(set(ids))
    if len(unique_ids) != len(ids):
        issues.append(ValidationIssue(location, "areas.list contains duplicate map IDs"))
    if unique_ids[0] != first_reserved:
        issues.append(ValidationIssue(location, f"first generated ID is {unique_ids[0]:08d}, expected {first_reserved:08d}"))
    if unique_ids[-1] > last_reserved:
        issues.append(ValidationIssue(location, f"last generated ID {unique_ids[-1]:08d} exceeds {last_reserved:08d}"))
    if overview in unique_ids:
        issues.append(ValidationIssue(location, "overview ID appears in normal tiles"))
    expected = list(range(unique_ids[0], unique_ids[-1] + 1))
    if unique_ids != expected:
        issues.append(ValidationIssue(location, "generated tile IDs are not contiguous"))

    if template_path is not None:
        try:
            mapnames, inputs = read_template_ids(template_path)
        except OSError as exc:
            issues.append(ValidationIssue(location, f"cannot read template.args: {exc}"))
        else:
            if mapnames and sorted(set(mapnames)) != unique_ids:
                issues.append(ValidationIssue(location, "template mapname IDs differ from areas.list"))
            if inputs and sorted(set(inputs)) != unique_ids:
                issues.append(ValidationIssue(location, "template input-file IDs differ from areas.list"))

    report: dict[str, int | str] = {
        "product": product_key,
        "tile_count": len(unique_ids),
        "first_tile_mapid": f"{unique_ids[0]:08d}",
        "last_tile_mapid": f"{unique_ids[-1]:08d}",
        "remaining_capacity": last_reserved - unique_ids[-1],
    }
    return issues, report

