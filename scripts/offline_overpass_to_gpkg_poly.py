#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
offline_overpass_to_gpkg.py

Offline execution of a useful subset of Overpass QL against a local .osm.pbf.

Designed for queries commonly prepared in JOSM, e.g.:

[out:xml][timeout:120];
(
  nwr["place"];
  way["highway"~"^(motorway|trunk|primary|secondary)$"];
  nwr["tourism"="viewpoint"];
);
out body;
>;
out skel qt;

Supported:
  node / way / relation / n / w / r / nw / nr / wr / nwr
  ["key"]
  ["key"="value"]
  ["key"!="value"]
  simple regex alternation such as:
      ["highway"~"^(primary|secondary|tertiary)$"]
      ["highway"~"primary|secondary|tertiary"]
  global [bbox:south,west,north,east]
  one common selector bbox: (...)(south,west,north,east)

Ignored because osmium resolves references itself:
  out ...
  >;
  >>;

Not supported:
  area / geocodeArea
  around
  poly
  newer / changed
  if:
  foreach
  difference/minus blocks
  arbitrary regular expressions
  recursion semantics beyond normal referenced-object inclusion

Dependencies:
  python3
  osmium-tool
  gdal-bin (ogr2ogr, ogrinfo)

Usage:
  ./offline_overpass_to_gpkg_poly.py query.overpass
  ./offline_overpass_to_gpkg_poly.py query.overpass --poly region.poly
  ./offline_overpass_to_gpkg_poly.py query.overpass russia-latest.osm.pbf result.gpkg --poly region.poly

Defaults:
  input PBF:  russia-latest.osm.pbf
  output:     <query filename>.gpkg
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

DEFAULT_FIELDS = [
    "name", "name:ru", "name:en", "official_name", "short_name", "alt_name",
    "ref", "operator", "brand", "wikidata", "wikipedia",
    "population", "capital", "admin_level"
]

TYPE_MAP = {
    "node": "n", "n": "n",
    "way": "w", "w": "w",
    "relation": "r", "rel": "r", "r": "r",
    "nw": "nw", "wn": "nw",
    "nr": "nr", "rn": "nr",
    "wr": "wr", "rw": "wr",
    "nwr": "nwr", "nrw": "nwr", "wnr": "nwr",
    "wrn": "nwr", "rnw": "nwr", "rwn": "nwr",
}

@dataclass
class TagFilter:
    key: str
    op: str       # exists, =, !=
    values: Optional[List[str]] = None

@dataclass
class Selector:
    types: str
    filters: List[TagFilter]
    bbox: Optional[Tuple[float, float, float, float]] = None


def die(msg: str, code: int = 2) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def run(cmd: List[str], *, quiet: bool = False) -> None:
    if not quiet:
        print("+", " ".join(shlex.quote(x) for x in cmd))
    subprocess.run(cmd, check=True)


def check_dependencies() -> None:
    missing = []
    for cmd in ("osmium", "ogr2ogr"):
        if shutil.which(cmd) is None:
            missing.append(cmd)
    if missing:
        print("Не найдены:", ", ".join(missing), file=sys.stderr)
        print("Debian/Ubuntu/WSL:", file=sys.stderr)
        print("  sudo apt install osmium-tool gdal-bin", file=sys.stderr)
        sys.exit(2)


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//[^\n\r]*", "", text)
    return text


def parse_simple_regex(pattern: str) -> List[str]:
    """
    Convert only exact/simple alternation regex into a list of literal values.
    Accepted examples:
      primary|secondary
      ^(primary|secondary)$
      ^primary|secondary$   (treated conservatively as alternation)
      (primary|secondary|tertiary)
    """
    p = pattern.strip()
    if p.startswith("^"):
        p = p[1:]
    if p.endswith("$"):
        p = p[:-1]
    if p.startswith("(") and p.endswith(")"):
        p = p[1:-1]

    # no real regex metacharacters except alternation
    if re.search(r"[\[\]{}+?*\\.]", p):
        raise ValueError(pattern)

    vals = [v.strip() for v in p.split("|")]
    if not vals or any(not v for v in vals):
        raise ValueError(pattern)
    return vals


FILTER_RE = re.compile(
    r"""\[
        \s*"(?P<key>[^"]+)"\s*
        (?:
          (?P<op>!~|~|!=|=)\s*"(?P<value>(?:[^"\\]|\\.)*)"\s*
        )?
    \]""",
    re.X
)

SELECTOR_RE = re.compile(
    r"""(?P<type>\bnwr\b|\bnw\b|\bnr\b|\bwr\b|\bnode\b|\bway\b|\brelation\b|\brel\b|\bn\b|\bw\b|\br\b)
        (?P<filters>(?:\s*\[[^\]]+\])+)
        \s*(?P<bbox>\(\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*\))?
        \s*;""",
    re.X | re.I
)


def parse_bbox(s: str) -> Tuple[float, float, float, float]:
    nums = [float(x.strip()) for x in s.strip()[1:-1].split(",")]
    if len(nums) != 4:
        raise ValueError("bbox")
    south, west, north, east = nums
    if not (-90 <= south <= 90 and -90 <= north <= 90 and
            -180 <= west <= 180 and -180 <= east <= 180):
        raise ValueError("bbox values")
    return south, west, north, east


def parse_query(text: str) -> Tuple[List[Selector], Optional[Tuple[float, float, float, float]], List[str]]:
    text = strip_comments(text)

    unsupported_tokens = [
        r"\baround\s*:",
        r"\bgeocodeArea\b",
        r"\barea\s*\(",
        r"\bpoly\s*:",
        r"\bnewer\s*:",
        r"\bchanged\s*:",
        r"\bif\s*:",
        r"\bforeach\b",
        r"\bcomplete\b",
    ]
    for pat in unsupported_tokens:
        if re.search(pat, text, flags=re.I):
            die(f"Запрос содержит пока неподдерживаемую Overpass-конструкцию: {pat}")

    global_bbox = None
    m = re.search(
        r"\[\s*bbox\s*:\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]",
        text, flags=re.I
    )
    if m:
        global_bbox = tuple(float(x) for x in m.groups())  # south, west, north, east

    selectors: List[Selector] = []
    fields: List[str] = []

    for sm in SELECTOR_RE.finditer(text):
        typ = TYPE_MAP[sm.group("type").lower()]
        raw_filters = sm.group("filters")
        filters: List[TagFilter] = []

        pos = 0
        for fm in FILTER_RE.finditer(raw_filters):
            gap = raw_filters[pos:fm.start()].strip()
            if gap:
                die(f"Не удалось разобрать фильтр около: {gap}")
            pos = fm.end()

            key = fm.group("key")
            op = fm.group("op")
            value = fm.group("value")

            if key not in fields and "*" not in key:
                fields.append(key)

            if op is None:
                filters.append(TagFilter(key, "exists"))
            elif op == "=":
                filters.append(TagFilter(key, "=", [value]))
            elif op == "!=":
                filters.append(TagFilter(key, "!=", [value]))
            elif op in ("~", "!~"):
                try:
                    vals = parse_simple_regex(value)
                except ValueError:
                    die(
                        f'Регулярное выражение "{value}" слишком сложное для безопасного '
                        f'офлайн-перевода. Используй простой список через |, например '
                        f'["highway"~"primary|secondary|tertiary"].'
                    )
                filters.append(TagFilter(key, "!=" if op == "!~" else "=", vals))
            else:
                die(f"Неизвестный оператор: {op}")

        tail = raw_filters[pos:].strip()
        if tail:
            die(f"Не удалось разобрать часть фильтра: {tail}")

        bbox = parse_bbox(sm.group("bbox")) if sm.group("bbox") else None
        selectors.append(Selector(typ, filters, bbox))

    if not selectors:
        die("В запросе не найдено ни одного поддерживаемого селектора node/way/relation/nwr с тегами.")

    # Find suspicious selector-like statements which were not parsed.
    cleaned = SELECTOR_RE.sub("", text)
    cleaned = re.sub(r"\[[^\]]+\]\s*;?", "", cleaned)  # settings
    cleaned = re.sub(r"\bout\b[^;]*;", "", cleaned, flags=re.I)
    cleaned = re.sub(r">>?\s*;", "", cleaned)
    cleaned = re.sub(r"[();\s]", "", cleaned)
    if cleaned:
        print("WARNING: часть Overpass-текста не влияет на локальную выборку:", file=sys.stderr)
        print(" ", cleaned[:500], file=sys.stderr)

    # selector bboxes: all must be identical; then use as pre-extract bbox
    selector_bboxes = [s.bbox for s in selectors if s.bbox is not None]
    if selector_bboxes:
        first = selector_bboxes[0]
        if any(b != first for b in selector_bboxes[1:]):
            die("Разные bbox у разных селекторов пока не поддерживаются.")
        if global_bbox and global_bbox != first:
            die("Одновременно заданы разные global bbox и selector bbox.")
        global_bbox = first

    return selectors, global_bbox, fields


def osmium_expr(types: str, f: TagFilter) -> str:
    prefix = types + "/"
    if f.op == "exists":
        return prefix + f.key
    vals = ",".join(f.values or [])
    if f.op == "=":
        return f"{prefix}{f.key}={vals}"
    if f.op == "!=":
        return f"{prefix}{f.key}!={vals}"
    raise AssertionError(f.op)


def make_osmconf(path: Path, keys: List[str]) -> None:
    # Preserve order, query fields first, then useful common fields.
    seen = set()
    attrs = []
    for k in keys + DEFAULT_FIELDS:
        if k and "*" not in k and k not in seen:
            seen.add(k)
            attrs.append(k)

    attr_line = ",".join(attrs)

    sections = ["points", "lines", "multipolygons", "multilinestrings", "other_relations"]
    parts = [
        "attribute_name_laundering=yes",
        "report_all_nodes=yes",
        "",
    ]
    for sec in sections:
        parts.extend([
            f"[{sec}]",
            "osm_id=yes",
            "osm_version=no",
            "osm_timestamp=no",
            "osm_uid=no",
            "osm_user=no",
            "osm_changeset=no",
            f"attributes={attr_line}",
            "unsignificant=",
            "ignore=",
            "other_tags=no",
            "",
        ])

    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Выполняет распространённый поднабор Overpass QL локально по OSM PBF и создаёт GeoPackage."
    )
    ap.add_argument("query", help="Файл запроса Overpass QL (.overpass/.txt)")
    ap.add_argument("pbf", nargs="?", default="russia-latest.osm.pbf", help="Локальный .osm.pbf")
    ap.add_argument("gpkg", nargs="?", help="Выходной .gpkg")
    ap.add_argument(
        "--poly",
        help=(
            "Ограничить обработку polygon-файлом. "
            "Основной вариант — Osmosis .poly; osmium также понимает GeoJSON/OSM polygon-файлы."
        ),
    )
    ap.add_argument("--keep-pbf", action="store_true", help="Сохранить промежуточный отфильтрованный PBF рядом с GPKG")
    args = ap.parse_args()

    check_dependencies()

    query_path = Path(args.query).expanduser().resolve()
    pbf_path = Path(args.pbf).expanduser().resolve()
    gpkg_path = Path(args.gpkg).expanduser().resolve() if args.gpkg else query_path.with_suffix(".gpkg")
    poly_path = Path(args.poly).expanduser().resolve() if args.poly else None

    if not query_path.is_file():
        die(f"Не найден файл запроса: {query_path}")
    if not pbf_path.is_file():
        die(f"Не найден PBF: {pbf_path}")
    if poly_path is not None and not poly_path.is_file():
        die(f"Не найден polygon-файл: {poly_path}")

    text = query_path.read_text(encoding="utf-8-sig")
    selectors, bbox, fields = parse_query(text)

    print("=" * 78)
    print("OFFLINE OVERPASS → GPKG")
    print("=" * 78)
    print("Query :", query_path)
    print("PBF   :", pbf_path)
    print("GPKG  :", gpkg_path)
    if poly_path:
        print("Poly  :", poly_path)
    if bbox:
        print("BBox  :", bbox, "(south, west, north, east)")
    print()
    print("Разобрано селекторов:", len(selectors))
    for i, s in enumerate(selectors, 1):
        print(f"  {i:02d}. {s.types}: " + " AND ".join(osmium_expr(s.types, f) for f in s.filters))

    with tempfile.TemporaryDirectory(prefix="offline-overpass-") as td:
        td = Path(td)

        source = pbf_path

        print("\n[1] Географическое ограничение...")

        if poly_path:
            poly_pbf = td / "poly.osm.pbf"
            print("  Вырезаю polygon:", poly_path)
            run([
                "osmium", "extract",
                "--polygon", str(poly_path),
                "--strategy", "complete_ways",
                "--overwrite",
                "-o", str(poly_pbf),
                str(source),
            ])
            source = poly_pbf
        else:
            print("  Polygon не задан.")

        if bbox:
            south, west, north, east = bbox
            bbox_pbf = td / "bbox.osm.pbf"
            print("  Дополнительно вырезаю bbox:", bbox)
            # osmium extract order is left,bottom,right,top = west,south,east,north
            run([
                "osmium", "extract",
                "--bbox", f"{west},{south},{east},{north}",
                "--strategy", "complete_ways",
                "--overwrite",
                "-o", str(bbox_pbf),
                str(source),
            ])
            source = bbox_pbf
        elif not poly_path:
            print("  BBox тоже нет — работаем по всему PBF.")

        selector_outputs = []

        print("\n[2] Выполняю селекторы...")
        for idx, sel in enumerate(selectors, 1):
            current = source
            stage_files = []

            for j, f in enumerate(sel.filters, 1):
                out = td / f"sel_{idx:03d}_{j:02d}.osm.pbf"
                expr = osmium_expr(sel.types, f)
                run([
                    "osmium", "tags-filter",
                    "--overwrite",
                    "-o", str(out),
                    str(current),
                    expr,
                ])
                current = out
                stage_files.append(out)

            selector_outputs.append(current)

        merged = td / "selected.osm.pbf"
        print("\n[3] Объединяю результаты селекторов...")
        if len(selector_outputs) == 1:
            shutil.copy2(selector_outputs[0], merged)
        else:
            run([
                "osmium", "merge",
                "--overwrite",
                "-o", str(merged),
                *[str(x) for x in selector_outputs],
            ])

        osmconf = td / "osmconf.ini"
        make_osmconf(osmconf, fields)

        if gpkg_path.exists():
            gpkg_path.unlink()

        print("\n[4] Конвертирую в GeoPackage...")
        run([
            "ogr2ogr",
            "-f", "GPKG",
            str(gpkg_path),
            str(merged),
            "-oo", f"CONFIG_FILE={osmconf}",
            "-lco", "SPATIAL_INDEX=YES",
            "-progress",
        ])

        if args.keep_pbf:
            kept = gpkg_path.with_suffix(".filtered.osm.pbf")
            shutil.copy2(merged, kept)
            print("Filtered PBF:", kept)

    print("\nГотово:", gpkg_path)
    print("\nПоля из запроса вынесены в отдельные столбцы; other_tags отключён.")
    print("Слои GPKG зависят от результата и обычно включают points, lines, multipolygons, multilinestrings.")

    if shutil.which("ogrinfo"):
        print("\nСодержимое GPKG:")
        subprocess.run(["ogrinfo", "-ro", "-so", str(gpkg_path)], check=False)


if __name__ == "__main__":
    main()
