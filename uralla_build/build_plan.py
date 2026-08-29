"""Translate one manifest product into explicit shell-free build stages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
import sys
from typing import Any, Mapping

from .errors import StageError
from .host import HostConfig, data_path, repo_path
from .pipeline import PipelineStage


SAFE_COMPONENT_RE = re.compile(r"^[^/\\\x00]+$")


@dataclass(frozen=True, slots=True)
class ProductBuildPlan:
    product: str
    build_id: str
    stages: tuple[PipelineStage, ...]
    img_source: str
    gmapi_source: str
    stable_areas: str | None
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "product": self.product,
            "build_id": self.build_id,
            "stages": [
                {
                    "name": stage.name,
                    "command": list(stage.command),
                    "expected_outputs": list(stage.expected_outputs),
                    "prepare_directories": list(stage.prepare_directories),
                    "environment": dict(stage.environment),
                    "resume_key": stage.resume_key,
                }
                for stage in self.stages
            ],
            "publication": {
                "img_source": self.img_source,
                "gmapi_source": self.gmapi_source,
            },
            "stable_areas": self.stable_areas,
            "warnings": list(self.warnings),
        }


def _mapping(value: object, location: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise StageError(f"{location} must be a mapping")
    return value


def _text(value: object, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise StageError(f"{location} must be a non-empty string")
    return value


def _component(value: object, location: str) -> str:
    text = _text(value, location)
    if not SAFE_COMPONENT_RE.fullmatch(text) or text in {".", ".."}:
        raise StageError(f"{location} must be a safe filename component")
    return text


def _tool_jar(lock: Mapping[str, object], host: HostConfig, name: str) -> Path:
    tool = _mapping(lock.get(name), f"tools.{name}")
    install_dir = _text(tool.get("install_dir"), f"tools.{name}.install_dir")
    jar = _text(tool.get("jar"), f"tools.{name}.jar")
    return (host.paths.tools_root / install_dir / jar).resolve()


def _bool_option(value: object) -> str:
    return "true" if bool(value) else "false"


def plan_product_build(
    manifest: Mapping[str, object],
    host: HostConfig,
    tools_lock: Mapping[str, object],
    *,
    product_key: str,
    build_id: str,
    repo_root: str | Path,
    manifest_path: str | Path,
    build_date: date | None = None,
) -> ProductBuildPlan:
    """Create deterministic argv stages without checking large input files."""

    repo = Path(repo_root).resolve()
    _component(build_id, "build_id")
    defaults = _mapping(manifest.get("defaults"), "defaults")
    products = _mapping(manifest.get("products"), "products")
    sources = _mapping(manifest.get("sources"), "sources")
    product = _mapping(products.get(product_key), f"products.{product_key}")
    if not product.get("enabled", defaults.get("enabled", True)):
        raise StageError(f"product {product_key!r} is disabled")
    source_key = _text(product.get("source"), f"products.{product_key}.source")
    source = _mapping(sources.get(source_key), f"sources.{source_key}")
    source_path = data_path(
        host, _text(source.get("path"), f"sources.{source_key}.path")
    )
    polygon = data_path(
        host, _text(product.get("polygon"), f"products.{product_key}.polygon")
    )
    transform = repo_path(
        repo,
        _text(defaults.get("transform_places"), "defaults.transform_places"),
    )
    sea = data_path(host, _text(defaults.get("sea"), "defaults.sea"))
    bounds = data_path(host, _text(defaults.get("bounds"), "defaults.bounds"))
    style = repo_path(repo, _text(defaults.get("style"), "defaults.style"))
    typ = repo_path(repo, _text(defaults.get("typ"), "defaults.typ"))
    typ_source = typ.with_suffix(".txt")
    mkgmap_args = repo_path(
        repo, _text(defaults.get("mkgmap_args"), "defaults.mkgmap_args")
    )
    identity = _mapping(product.get("identity"), f"products.{product_key}.identity")
    names = _mapping(product.get("names"), f"products.{product_key}.names")
    splitter = _mapping(product.get("splitter"), f"products.{product_key}.splitter")
    mkgmap = _mapping(product.get("mkgmap", {}), f"products.{product_key}.mkgmap")
    defaults_splitter = _mapping(defaults.get("splitter"), "defaults.splitter")
    areas = _mapping(defaults.get("areas"), "defaults.areas")

    family_name = _component(names.get("family"), f"products.{product_key}.names.family")
    output_img = _component(
        names.get("output_img"), f"products.{product_key}.names.output_img"
    )
    if not output_img.lower().endswith(".img"):
        raise StageError(f"products.{product_key}.names.output_img must end in .img")

    build_root = host.paths.work_root / "builds" / build_id
    stages: list[PipelineStage] = []
    if product.get("extract", True):
        extract_output = build_root / "extract" / "source.osm.pbf"
        stages.append(
            PipelineStage(
                "extract",
                (
                    "osmium",
                    "extract",
                    "-O",
                    "--progress",
                    "--strategy=simple",
                    f"--polygon={polygon}",
                    str(source_path),
                    "-o",
                    "source.osm.pbf",
                ),
                ("source.osm.pbf",),
            )
        )
        transform_input = extract_output
    else:
        transform_input = source_path

    transformed = build_root / "transform" / "transformed.osm.pbf"
    stages.append(
        PipelineStage(
            "transform",
            (
                "osmosis",
                "--read-pbf-fast",
                f"file={transform_input}",
                "--tag-transform",
                f"file={transform}",
                "--write-pbf",
                "file=transformed.osm.pbf",
                "omitmetadata=true",
            ),
            ("transformed.osm.pbf",),
        )
    )

    warnings: list[str] = []
    preprocessor = _mapping(defaults.get("preprocessor", {}), "defaults.preprocessor")
    source_profiles = _mapping(
        preprocessor.get("source_profiles", {}),
        "defaults.preprocessor.source_profiles",
    )
    raw_profiles = source_profiles.get(source_key, [])
    if not isinstance(raw_profiles, list) or any(
        not isinstance(profile, str) or not profile for profile in raw_profiles
    ):
        raise StageError(
            f"defaults.preprocessor.source_profiles.{source_key} must be a list"
        )
    profiles = ["landmarks"]
    for profile in raw_profiles:
        profile_text = str(profile)
        if profile_text not in profiles:
            profiles.append(profile_text)

    blacklist = repo_path(
        repo,
        _text(preprocessor.get("blacklist"), "defaults.preprocessor.blacklist"),
    )
    elevation_value = product.get("elevation")

    # Split OSM before semantic preprocessing so independent tiles can use all CPU cores.
    splitter_input = transformed

    areas_root = repo_path(repo, _text(areas.get("root"), "defaults.areas.root"))
    stable_areas = areas_root / product_key / "areas.list"
    splitter_command = [
        "java",
        "-jar",
        str(_tool_jar(tools_lock, host, "splitter")),
        str(splitter_input),
        f"--description={_text(names.get('description'), f'products.{product_key}.names.description')}",
        f"--polygon-file={polygon}",
        f"--precomp-sea={sea}",
        f"--keep-complete={_bool_option(defaults_splitter.get('keep_complete', True))}",
        f"--mapid={_text(identity.get('first_tile_mapid'), f'products.{product_key}.identity.first_tile_mapid')}",
        f"--max-nodes={splitter.get('max_nodes')}",
        f"--output={_text(defaults_splitter.get('output'), 'defaults.splitter.output')}",
        f"--wanted-admin-level={defaults_splitter.get('wanted_admin_level')}",
        "--output-dir=tiles",
    ]
    max_threads = splitter.get("max_threads")
    if max_threads is not None:
        splitter_command.append(f"--max-threads={max_threads}")
    geonames = product.get("geonames")
    if geonames is not None:
        splitter_command.append(
            f"--geonames-file={data_path(host, _text(geonames, f'products.{product_key}.geonames'))}"
        )
    if stable_areas.is_file():
        splitter_command.append(f"--split-file={stable_areas}")
    stages.append(
        PipelineStage(
            "splitter",
            tuple(splitter_command),
            ("tiles",),
            ("tiles",),
        )
    )

    tiles = build_root / "splitter" / "tiles"
    stages.append(
        PipelineStage(
            "validate-areas",
            (
                sys.executable,
                "-m",
                "uralla_build",
                "--manifest",
                str(Path(manifest_path).resolve()),
                "validate-areas",
                product_key,
                str(tiles / "areas.list"),
                "--template",
                str(tiles / "template.args"),
            ),
            environment=(("PYTHONPATH", str(repo)),),
        )
    )

    elevation_tiles: Path | None = None
    if elevation_value is not None:
        elevation = data_path(
            host,
            _text(elevation_value, f"products.{product_key}.elevation"),
        )
        elevation_tiles = build_root / "splitter-elevation" / "tiles"
        stages.append(
            PipelineStage(
                "splitter-elevation",
                (
                    "java",
                    "-jar",
                    str(_tool_jar(tools_lock, host, "splitter")),
                    str(elevation),
                    f"--split-file={tiles / 'areas.list'}",
                    f"--output={_text(defaults_splitter.get('output'), 'defaults.splitter.output')}",
                    "--output-dir=tiles",
                ),
                ("tiles",),
                ("tiles",),
            )
        )

    prepared_tiles = build_root / "prepare-tiles" / "tiles"
    prepare_command = [
        sys.executable,
        "-m",
        "uralla_build.tile_preprocess",
        "--input-dir",
        str(tiles),
        "--template",
        str(tiles / "template.args"),
        "--output-dir",
        "tiles",
        "--config",
        str(blacklist),
        "--report",
        "report.json",
    ]
    for profile in profiles:
        prepare_command.extend(("--profile", profile))
    preprocess_workers = splitter.get("max_threads")
    if preprocess_workers is not None:
        prepare_command.extend(("--workers", str(preprocess_workers)))
    if elevation_tiles is not None:
        prepare_command.extend(("--elevation-dir", str(elevation_tiles)))
    stages.append(
        PipelineStage(
            "prepare-tiles",
            tuple(prepare_command),
            ("tiles", "report.json"),
            ("tiles",),
            environment=(("PYTHONPATH", str(repo)),),
        )
    )

    if "ru-political-parties" in profiles:
        warnings.append(
            "parallel tile preprocessing: landmarks + Russian political blacklist"
        )
    else:
        warnings.append("parallel tile preprocessing: static peak + river landmarks")

    tiles = prepared_tiles

    garmin = build_root / "mkgmap" / "garmin"
    mkgmap_command = [
        "java",
        "-jar",
        str(_tool_jar(tools_lock, host, "mkgmap")),
        "-c",
        str(mkgmap_args),
        f"--style-file={style}",
        f"--family-id={identity.get('family_id')}",
        f"--product-id={identity.get('product_id')}",
        f"--family-name={family_name}",
        f"--series-name={_text(names.get('series'), f'products.{product_key}.names.series')}",
        f"--overview-mapname={_text(names.get('overview'), f'products.{product_key}.names.overview')}",
        f"--overview-mapnumber={_text(identity.get('overview_mapnumber'), f'products.{product_key}.identity.overview_mapnumber')}",
        f"--code-page={defaults.get('code_page')}",
        "--gmapi",
        "--gmapsupp",
        f"--bounds={bounds}",
        f"--precomp-sea={sea}",
        "--output-dir=garmin",
        f"--dem={host.paths.dem_root}",
    ]
    dem_dists = mkgmap.get("dem_dists")
    if dem_dists is not None:
        mkgmap_command.append(f"--dem-dists={dem_dists}")
    if mkgmap.get("dem_poly", False):
        mkgmap_command.append(f"--dem-poly={polygon}")
    mkgmap_command.extend(
        (
            "-c",
            str(tiles / "template.args"),
            f"--description={_text(names.get('description'), f'products.{product_key}.names.description')} ({(build_date or date.today()).isoformat()})",
            str(typ_source),
        )
    )
    gmapi = garmin / f"{family_name}.gmap"
    stages.append(
        PipelineStage(
            "mkgmap",
            tuple(mkgmap_command),
            ("garmin/gmapsupp.img", f"garmin/{family_name}.gmap"),
            ("garmin",),
        )
    )

    return ProductBuildPlan(
        product_key,
        build_id,
        tuple(stages),
        str(garmin / "gmapsupp.img"),
        str(gmapi),
        str(stable_areas) if stable_areas.is_file() else None,
        tuple(warnings),
    )
