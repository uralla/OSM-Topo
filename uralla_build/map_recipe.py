"""Fingerprint the parts of the repository that affect generated Garmin map content."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

from .manifest import load_manifest

_RECIPE_CODE_FILES = (
    "uralla_build/analysis_bundle.py",
    "uralla_build/area_poi_analysis.py",
    "uralla_build/area_pois.py",
    "uralla_build/build_plan.py",
    "uralla_build/kite.py",
    "uralla_build/poi_context.py",
    "uralla_build/poi_context_analysis.py",
    "uralla_build/poi_lod.py",
    "uralla_build/preprocess_fast.py",
    "uralla_build/preprocess_pipeline.py",
    "uralla_build/preprocessor.py",
    "uralla_build/river_landmarks.py",
    "uralla_build/road_density.py",
    "uralla_build/road_density_analysis.py",
    "uralla_build/sanatorium_labels.py",
    "uralla_build/semantic_apply.py",
)
_RECIPE_CONFIG_FILES = (
    "config/preprocessor-blacklist.yaml",
    "config/tools.lock.yaml",
    "styles/uralla.args",
    "styles/uralla.txt",
)
_IGNORED_PRODUCT_FIELDS = frozenset({"enabled", "priority", "update_interval_days", "web"})
_IGNORED_DEFAULT_FIELDS = frozenset({"enabled", "priority", "update_interval_days"})


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _hash_file(digest: "hashlib._Hash", repo: Path, relative: str) -> None:
    path = repo / relative
    digest.update(relative.encode("utf-8"))
    digest.update(b"\0")
    if not path.is_file():
        digest.update(b"<missing>\0")
        return
    digest.update(path.read_bytes())
    digest.update(b"\0")


def _hash_style_tree(digest: "hashlib._Hash", repo: Path) -> None:
    root = repo / "styles" / "uralla"
    if not root.is_dir():
        digest.update(b"styles/uralla\0<missing>\0")
        return
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(repo).as_posix()
        _hash_file(digest, repo, relative)


def _filtered_mapping(value: object, ignored: frozenset[str]) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): raw for key, raw in value.items() if str(key) not in ignored}


def map_recipe_fingerprint(
    manifest: Mapping[str, object],
    product: str,
    *,
    repo_root: str | Path | None = None,
) -> str:
    """Return a deterministic SHA-256 for map-affecting code, style and product config."""

    repo = Path(repo_root).resolve() if repo_root is not None else _repo_root()
    products = manifest.get("products")
    if not isinstance(products, Mapping) or not isinstance(products.get(product), Mapping):
        raise KeyError(f"unknown product: {product}")
    defaults = _filtered_mapping(manifest.get("defaults"), _IGNORED_DEFAULT_FIELDS)
    raw_product = _filtered_mapping(products[product], _IGNORED_PRODUCT_FIELDS)
    source_key = raw_product.get("source")
    sources = manifest.get("sources")
    source = (
        dict(sources.get(source_key, {}))
        if isinstance(sources, Mapping) and isinstance(source_key, str) and isinstance(sources.get(source_key), Mapping)
        else {}
    )

    digest = hashlib.sha256()
    payload = {
        "recipe_schema": 1,
        "defaults": defaults,
        "product": raw_product,
        "source": source,
    }
    digest.update(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    digest.update(b"\0")
    for relative in _RECIPE_CODE_FILES + _RECIPE_CONFIG_FILES:
        _hash_file(digest, repo, relative)
    _hash_style_tree(digest, repo)
    return digest.hexdigest()


def map_recipe_from_manifest_file(product: str, manifest_path: str | Path) -> str:
    path = Path(manifest_path).resolve()
    manifest = load_manifest(path)
    return map_recipe_fingerprint(manifest, product, repo_root=path.parent.parent)
