"""Manifest loading and static product identity validation."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path, PurePosixPath
import re
from typing import Any

import yaml

from .errors import ManifestError, ValidationIssue


PRODUCT_KEY_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAP_ID_RE = re.compile(r"^[0-9]{8}$")
REQUIRED_IDENTITY = (
    "family_id",
    "product_id",
    "overview_mapnumber",
    "first_tile_mapid",
    "last_reserved_mapid",
)
REQUIRED_NAMES = ("family", "series", "overview", "description", "output_img")


def load_manifest(path: str | Path) -> dict[str, Any]:
    """Load a YAML manifest and require a mapping at the document root."""

    manifest_path = Path(path)
    try:
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ManifestError(f"cannot read {manifest_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ManifestError(f"invalid YAML in {manifest_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ManifestError(f"manifest root must be a mapping: {manifest_path}")
    return raw


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _safe_project_path(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts


def _id_string(value: object) -> str | None:
    return value if isinstance(value, str) and MAP_ID_RE.fullmatch(value) else None


def _safe_file_component(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and value not in {".", ".."}
        and "/" not in value
        and "\\" not in value
        and "\x00" not in value
    )


def _valid_non_negative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _valid_interval(value: object) -> bool:
    return value is None or (
        isinstance(value, int) and not isinstance(value, bool) and value > 0
    )


def validate_manifest(data: Mapping[str, Any]) -> list[ValidationIssue]:
    """Validate schema-critical fields and all reserved ID blocks."""

    issues: list[ValidationIssue] = []
    if data.get("schema_version") != 1:
        issues.append(ValidationIssue("schema_version", "must be integer 1"))

    defaults = _mapping(data.get("defaults"))
    sources = _mapping(data.get("sources"))
    products = _mapping(data.get("products"))
    if defaults is None:
        issues.append(ValidationIssue("defaults", "must be a mapping"))
        defaults = {}
    if sources is None:
        issues.append(ValidationIssue("sources", "must be a mapping"))
        sources = {}
    if products is None or not products:
        issues.append(ValidationIssue("products", "must be a non-empty mapping"))
        return issues

    if "enabled" in defaults and not isinstance(defaults.get("enabled"), bool):
        issues.append(ValidationIssue("defaults.enabled", "must be a boolean"))
    if "priority" in defaults and not _valid_non_negative_int(defaults.get("priority")):
        issues.append(ValidationIssue("defaults.priority", "must be a non-negative integer"))
    if "update_interval_days" in defaults and not _valid_interval(
        defaults.get("update_interval_days")
    ):
        issues.append(
            ValidationIssue(
                "defaults.update_interval_days", "must be null or a positive integer"
            )
        )

    for source_key, source_value in sources.items():
        location = f"sources.{source_key}"
        if not PRODUCT_KEY_RE.fullmatch(str(source_key)):
            issues.append(ValidationIssue(location, "invalid source key"))
        source = _mapping(source_value)
        if source is None:
            issues.append(ValidationIssue(location, "must be a mapping"))
        elif not _safe_project_path(source.get("path")):
            issues.append(ValidationIssue(f"{location}.path", "must be a safe relative path"))

    preprocessor = _mapping(defaults.get("preprocessor"))
    if "preprocessor" in defaults and preprocessor is None:
        issues.append(ValidationIssue("defaults.preprocessor", "must be a mapping"))
    elif preprocessor is not None:
        if not _safe_project_path(preprocessor.get("blacklist")):
            issues.append(
                ValidationIssue(
                    "defaults.preprocessor.blacklist", "must be a safe relative path"
                )
            )
        source_profiles = _mapping(preprocessor.get("source_profiles"))
        if source_profiles is None:
            issues.append(
                ValidationIssue(
                    "defaults.preprocessor.source_profiles", "must be a mapping"
                )
            )
        else:
            for source_key, profiles in source_profiles.items():
                location = f"defaults.preprocessor.source_profiles.{source_key}"
                if source_key not in sources:
                    issues.append(ValidationIssue(location, "references an unknown source"))
                if not isinstance(profiles, list) or not profiles or any(
                    not isinstance(profile, str) or not profile for profile in profiles
                ):
                    issues.append(
                        ValidationIssue(
                            location, "must be a non-empty list of profile names"
                        )
                    )

    seen_fid_pid: dict[tuple[int, int], str] = {}
    seen_overview: dict[str, str] = {}
    seen_first: dict[str, str] = {}
    seen_output_img: dict[str, str] = {}
    blocks: list[tuple[int, int, str]] = []

    for product_key, product_value in products.items():
        key = str(product_key)
        location = f"products.{key}"
        if not PRODUCT_KEY_RE.fullmatch(key):
            issues.append(ValidationIssue(location, "invalid product key"))
        product = _mapping(product_value)
        if product is None:
            issues.append(ValidationIssue(location, "must be a mapping"))
            continue

        if "extract" in product and not isinstance(product.get("extract"), bool):
            issues.append(ValidationIssue(f"{location}.extract", "must be a boolean"))

        if "enabled" in product and not isinstance(product.get("enabled"), bool):
            issues.append(ValidationIssue(f"{location}.enabled", "must be a boolean"))
        if "priority" in product and not _valid_non_negative_int(product.get("priority")):
            issues.append(
                ValidationIssue(f"{location}.priority", "must be a non-negative integer")
            )
        if "update_interval_days" in product and not _valid_interval(
            product.get("update_interval_days")
        ):
            issues.append(
                ValidationIssue(
                    f"{location}.update_interval_days", "must be null or a positive integer"
                )
            )

        source_key = product.get("source")
        if source_key not in sources:
            issues.append(ValidationIssue(f"{location}.source", f"unknown source {source_key!r}"))

        for field in ("polygon",):
            if not _safe_project_path(product.get(field)):
                issues.append(ValidationIssue(f"{location}.{field}", "must be a safe relative path"))
        for field in ("elevation", "geonames"):
            value = product.get(field)
            if value is not None and not _safe_project_path(value):
                issues.append(ValidationIssue(f"{location}.{field}", "must be null or a safe relative path"))

        identity = _mapping(product.get("identity"))
        if identity is None:
            issues.append(ValidationIssue(f"{location}.identity", "must be a mapping"))
            continue
        for field in REQUIRED_IDENTITY:
            if field not in identity:
                issues.append(ValidationIssue(f"{location}.identity.{field}", "is required"))

        try:
            fid = int(identity.get("family_id"))
            pid = int(identity.get("product_id"))
        except (TypeError, ValueError):
            issues.append(ValidationIssue(f"{location}.identity", "family_id and product_id must be integers"))
            continue
        if not 1 <= fid <= 65535:
            issues.append(ValidationIssue(f"{location}.identity.family_id", "must be in 1..65535"))
        if not 1 <= pid <= 65535:
            issues.append(ValidationIssue(f"{location}.identity.product_id", "must be in 1..65535"))

        fid_pid = (fid, pid)
        if previous := seen_fid_pid.get(fid_pid):
            issues.append(ValidationIssue(f"{location}.identity", f"FID/PID duplicates {previous}"))
        else:
            seen_fid_pid[fid_pid] = key

        overview = _id_string(identity.get("overview_mapnumber"))
        first = _id_string(identity.get("first_tile_mapid"))
        last = _id_string(identity.get("last_reserved_mapid"))
        for field, value in (
            ("overview_mapnumber", overview),
            ("first_tile_mapid", first),
            ("last_reserved_mapid", last),
        ):
            if value is None:
                issues.append(ValidationIssue(f"{location}.identity.{field}", "must be a quoted eight-digit string"))
        if overview is None or first is None or last is None:
            continue

        if previous := seen_overview.get(overview):
            issues.append(ValidationIssue(f"{location}.identity.overview_mapnumber", f"duplicates {previous}"))
        else:
            seen_overview[overview] = key
        if previous := seen_first.get(first):
            issues.append(ValidationIssue(f"{location}.identity.first_tile_mapid", f"duplicates {previous}"))
        else:
            seen_first[first] = key

        overview_number, first_number, last_number = map(int, (overview, first, last))
        if first_number != overview_number + 1:
            issues.append(ValidationIssue(f"{location}.identity", "first_tile_mapid must equal overview_mapnumber + 1"))
        if first_number > last_number:
            issues.append(ValidationIssue(f"{location}.identity", "first_tile_mapid exceeds last_reserved_mapid"))
        blocks.append((overview_number, last_number, key))

        names = _mapping(product.get("names"))
        if names is None:
            issues.append(ValidationIssue(f"{location}.names", "must be a mapping"))
        else:
            for field in REQUIRED_NAMES:
                if not isinstance(names.get(field), str) or not names[field].strip():
                    issues.append(ValidationIssue(f"{location}.names.{field}", "must be a non-empty string"))
            family = names.get("family")
            if not _safe_file_component(family):
                issues.append(
                    ValidationIssue(
                        f"{location}.names.family", "must be a safe filename component"
                    )
                )
            output_img = names.get("output_img")
            if not _safe_file_component(output_img) or not str(output_img).lower().endswith(
                ".img"
            ):
                issues.append(
                    ValidationIssue(
                        f"{location}.names.output_img",
                        "must be a safe filename ending in .img",
                    )
                )
            else:
                folded = str(output_img).casefold()
                if previous := seen_output_img.get(folded):
                    issues.append(
                        ValidationIssue(
                            f"{location}.names.output_img", f"duplicates {previous}"
                        )
                    )
                else:
                    seen_output_img[folded] = key

        web = _mapping(product.get("web"))
        if "web" in product and web is None:
            issues.append(ValidationIssue(f"{location}.web", "must be a mapping"))
        elif web is not None:
            visible = web.get("visible", False)
            if not isinstance(visible, bool):
                issues.append(ValidationIssue(f"{location}.web.visible", "must be a boolean"))
            title = web.get("title")
            if title is not None and (not isinstance(title, str) or not title.strip()):
                issues.append(ValidationIssue(f"{location}.web.title", "must be a non-empty string"))
            if visible is True and (not isinstance(title, str) or not title.strip()):
                issues.append(
                    ValidationIssue(
                        f"{location}.web.title", "is required when web.visible is true"
                    )
                )
            order = web.get("order")
            if order is not None and not _valid_non_negative_int(order):
                issues.append(
                    ValidationIssue(
                        f"{location}.web.order", "must be a non-negative integer"
                    )
                )

        splitter = _mapping(product.get("splitter"))
        if splitter is None:
            issues.append(ValidationIssue(f"{location}.splitter", "must be a mapping"))
        else:
            max_nodes = splitter.get("max_nodes")
            if not isinstance(max_nodes, int) or max_nodes <= 0:
                issues.append(ValidationIssue(f"{location}.splitter.max_nodes", "must be a positive integer"))
            max_threads = splitter.get("max_threads")
            if max_threads is not None and (
                not isinstance(max_threads, int)
                or isinstance(max_threads, bool)
                or max_threads <= 0
            ):
                issues.append(
                    ValidationIssue(
                        f"{location}.splitter.max_threads", "must be a positive integer"
                    )
                )

        mkgmap = _mapping(product.get("mkgmap", {}))
        if mkgmap is None:
            issues.append(ValidationIssue(f"{location}.mkgmap", "must be a mapping"))
        else:
            dem_dists = mkgmap.get("dem_dists")
            if dem_dists is not None and (
                not isinstance(dem_dists, int)
                or isinstance(dem_dists, bool)
                or dem_dists <= 0
            ):
                issues.append(
                    ValidationIssue(
                        f"{location}.mkgmap.dem_dists", "must be a positive integer"
                    )
                )
            if "dem_poly" in mkgmap and not isinstance(mkgmap.get("dem_poly"), bool):
                issues.append(
                    ValidationIssue(f"{location}.mkgmap.dem_poly", "must be a boolean")
                )

    ordered = sorted(blocks)
    for current, following in zip(ordered, ordered[1:]):
        if following[0] <= current[1]:
            issues.append(
                ValidationIssue(
                    f"products.{following[2]}.identity",
                    f"reserved block overlaps {current[2]}",
                )
            )
    return issues
