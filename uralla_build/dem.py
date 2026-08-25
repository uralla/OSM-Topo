"""Select portable HGT subsets from active elevation product polygons."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import re
from typing import Iterable, Mapping, Sequence

from .errors import ManifestError


HGT_RE = re.compile(r"^(?P<lat>[NS])(?P<lat_num>\d{2})(?P<lon>[EW])(?P<lon_num>\d{3})\.hgt$", re.I)
EPSILON = 1e-12


Point = tuple[float, float]
Rect = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class Ring:
    points: tuple[Point, ...]
    bounds: Rect


@dataclass(frozen=True, slots=True)
class PolygonPart:
    outer: Ring
    holes: tuple[Ring, ...]


@dataclass(frozen=True, slots=True)
class InventoryFile:
    path: str
    size: int
    latitude: int
    longitude: int


@dataclass(frozen=True, slots=True)
class ProductDemStats:
    product: str
    polygon: str
    intersecting_tiles: int
    available_files: int
    available_bytes: int
    intersecting_tiles_without_file: int


@dataclass(frozen=True, slots=True)
class DemSelection:
    elevation_products: tuple[str, ...]
    polygons: tuple[str, ...]
    inventory_files: int
    inventory_bytes: int
    inventory_hgt_files: int
    inventory_hgt_bytes: int
    exact_tiles: int
    exact_files: tuple[str, ...]
    exact_bytes: int
    halo: int
    selected_files: tuple[str, ...]
    selected_bytes: int
    intersecting_tiles_without_file: tuple[str, ...]
    product_stats: tuple[ProductDemStats, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def parse_hgt_name(path: str) -> tuple[int, int] | None:
    match = HGT_RE.fullmatch(Path(path).name)
    if match is None:
        return None
    latitude = int(match.group("lat_num")) * (1 if match.group("lat").upper() == "N" else -1)
    longitude = int(match.group("lon_num")) * (1 if match.group("lon").upper() == "E" else -1)
    return latitude, longitude


def format_hgt_name(latitude: int, longitude: int) -> str:
    canonical_lon = ((longitude + 180) % 360) - 180
    lat_prefix = "N" if latitude >= 0 else "S"
    lon_prefix = "E" if canonical_lon >= 0 else "W"
    return f"{lat_prefix}{abs(latitude):02d}{lon_prefix}{abs(canonical_lon):03d}.hgt"


def read_inventory(path: str | Path) -> tuple[list[tuple[str, int]], dict[tuple[int, int], InventoryFile]]:
    all_files: list[tuple[str, int]] = []
    hgt_files: dict[tuple[int, int], InventoryFile] = {}
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ManifestError(f"cannot read DEM inventory {path}: {exc}") from exc
    for number, line in enumerate(lines, 1):
        try:
            relative, raw_size = line.rsplit("\t", 1)
            size = int(raw_size)
        except (ValueError, TypeError) as exc:
            raise ManifestError(f"invalid DEM inventory line {number}: {line!r}") from exc
        if not relative or size < 0:
            raise ManifestError(f"invalid DEM inventory line {number}: {line!r}")
        all_files.append((relative, size))
        tile = parse_hgt_name(relative)
        if tile is None:
            continue
        if tile in hgt_files:
            raise ManifestError(
                f"duplicate HGT tile {format_hgt_name(*tile)}: "
                f"{hgt_files[tile].path!r} and {relative!r}"
            )
        hgt_files[tile] = InventoryFile(relative, size, tile[0], tile[1])
    return all_files, hgt_files


def _ring(points: Sequence[Point]) -> Ring:
    if len(points) < 3:
        raise ManifestError("polygon ring must have at least three points")
    unwrapped: list[Point] = [points[0]]
    for longitude, latitude in points[1:]:
        previous = unwrapped[-1][0]
        while longitude - previous > 180:
            longitude -= 360
        while longitude - previous < -180:
            longitude += 360
        unwrapped.append((longitude, latitude))
    if unwrapped[0] != unwrapped[-1]:
        unwrapped.append(unwrapped[0])
    xs = [point[0] for point in unwrapped]
    ys = [point[1] for point in unwrapped]
    return Ring(tuple(unwrapped), (min(xs), min(ys), max(xs), max(ys)))


def _shift_ring(ring: Ring, reference_x: float) -> Ring:
    center = (ring.bounds[0] + ring.bounds[2]) / 2
    shift = round((reference_x - center) / 360) * 360
    if shift == 0:
        return ring
    points = tuple((x + shift, y) for x, y in ring.points)
    return Ring(points, (ring.bounds[0] + shift, ring.bounds[1], ring.bounds[2] + shift, ring.bounds[3]))


def read_poly(path: str | Path) -> tuple[PolygonPart, ...]:
    try:
        lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise ManifestError(f"cannot read polygon {path}: {exc}") from exc
    if not lines:
        raise ManifestError(f"empty polygon file: {path}")
    parts: list[tuple[Ring, list[Ring]]] = []
    current_points: list[Point] | None = None
    current_hole = False

    def finish_ring() -> None:
        nonlocal current_points
        if current_points is None:
            return
        parsed = _ring(current_points)
        if current_hole:
            if not parts:
                raise ManifestError(f"orphan polygon hole in {path}")
            reference = (parts[-1][0].bounds[0] + parts[-1][0].bounds[2]) / 2
            parts[-1][1].append(_shift_ring(parsed, reference))
        else:
            parts.append((parsed, []))
        current_points = None

    for raw in lines[1:]:
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped == "END":
            finish_ring()
            continue
        fields = stripped.split()
        try:
            point = (float(fields[0]), float(fields[1]))
        except (ValueError, IndexError):
            finish_ring()
            current_hole = stripped.startswith("!")
            current_points = []
        else:
            if current_points is None:
                raise ManifestError(f"coordinate outside a ring in {path}: {stripped!r}")
            current_points.append(point)
    finish_ring()
    if not parts:
        raise ManifestError(f"polygon has no outer rings: {path}")
    return tuple(PolygonPart(outer, tuple(holes)) for outer, holes in parts)


def _point_on_segment(point: Point, start: Point, end: Point) -> bool:
    px, py = point
    ax, ay = start
    bx, by = end
    cross = (px - ax) * (by - ay) - (py - ay) * (bx - ax)
    if abs(cross) > EPSILON:
        return False
    return (
        min(ax, bx) - EPSILON <= px <= max(ax, bx) + EPSILON
        and min(ay, by) - EPSILON <= py <= max(ay, by) + EPSILON
    )


def _point_in_ring(point: Point, ring: Ring) -> bool:
    x, y = point
    inside = False
    for start, end in zip(ring.points, ring.points[1:]):
        if _point_on_segment(point, start, end):
            return True
        x1, y1 = start
        x2, y2 = end
        if (y1 > y) != (y2 > y):
            crossing = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing:
                inside = not inside
    return inside


def _orientation(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    values = (_orientation(a, b, c), _orientation(a, b, d), _orientation(c, d, a), _orientation(c, d, b))
    if values[0] * values[1] < 0 and values[2] * values[3] < 0:
        return True
    return (
        (abs(values[0]) <= EPSILON and _point_on_segment(c, a, b))
        or (abs(values[1]) <= EPSILON and _point_on_segment(d, a, b))
        or (abs(values[2]) <= EPSILON and _point_on_segment(a, c, d))
        or (abs(values[3]) <= EPSILON and _point_on_segment(b, c, d))
    )


def _rect_corners(rect: Rect) -> tuple[Point, Point, Point, Point]:
    left, bottom, right, top = rect
    return ((left, bottom), (right, bottom), (right, top), (left, top))


def _ring_boundary_intersects_rect(ring: Ring, rect: Rect) -> bool:
    left, bottom, right, top = rect
    edges = (
        ((left, bottom), (right, bottom)),
        ((right, bottom), (right, top)),
        ((right, top), (left, top)),
        ((left, top), (left, bottom)),
    )
    for start, end in zip(ring.points, ring.points[1:]):
        if max(start[0], end[0]) < left or min(start[0], end[0]) > right:
            continue
        if max(start[1], end[1]) < bottom or min(start[1], end[1]) > top:
            continue
        if any(_segments_intersect(start, end, edge[0], edge[1]) for edge in edges):
            return True
    return False


def _ring_intersects_rect(ring: Ring, rect: Rect) -> bool:
    left, bottom, right, top = rect
    min_x, min_y, max_x, max_y = ring.bounds
    if max_x <= left or min_x >= right or max_y <= bottom or min_y >= top:
        return False
    corners = _rect_corners(rect)
    if any(_point_in_ring(corner, ring) for corner in corners):
        return True
    if any(left <= x <= right and bottom <= y <= top for x, y in ring.points):
        return True
    return _ring_boundary_intersects_rect(ring, rect)


def _part_intersects_rect(part: PolygonPart, rect: Rect) -> bool:
    if not _ring_intersects_rect(part.outer, rect):
        return False
    corners = _rect_corners(rect)
    for hole in part.holes:
        if all(_point_in_ring(corner, hole) for corner in corners) and not _ring_boundary_intersects_rect(hole, rect):
            return False
    return True


def tiles_for_polygon(parts: Sequence[PolygonPart]) -> set[tuple[int, int]]:
    selected: set[tuple[int, int]] = set()
    for part in parts:
        min_x, min_y, max_x, max_y = part.outer.bounds
        for latitude in range(max(-90, math.floor(min_y)), min(90, math.ceil(max_y))):
            for unwrapped_lon in range(math.floor(min_x), math.ceil(max_x)):
                rect = (unwrapped_lon, latitude, unwrapped_lon + 1, latitude + 1)
                if _part_intersects_rect(part, rect):
                    longitude = ((unwrapped_lon + 180) % 360) - 180
                    selected.add((latitude, longitude))
    return selected


def _active_elevation_products(manifest: Mapping[str, object]) -> list[tuple[str, str]]:
    defaults = manifest.get("defaults")
    products = manifest.get("products")
    if not isinstance(defaults, Mapping) or not isinstance(products, Mapping):
        raise ManifestError("manifest defaults/products must be mappings")
    default_enabled = defaults.get("enabled", True)
    selected: list[tuple[str, str]] = []
    for key, raw in products.items():
        if not isinstance(raw, Mapping):
            continue
        if not raw.get("enabled", default_enabled) or raw.get("elevation") is None:
            continue
        polygon = raw.get("polygon")
        if not isinstance(polygon, str):
            raise ManifestError(f"products.{key}.polygon must be a path")
        selected.append((str(key), polygon))
    return selected


def select_dem_files(
    manifest: Mapping[str, object],
    inventory_path: str | Path,
    repo_root: str | Path,
    *,
    halo: int = 1,
) -> DemSelection:
    if halo < 0:
        raise ManifestError("DEM halo must be non-negative")
    all_files, inventory = read_inventory(inventory_path)
    products = _active_elevation_products(manifest)
    polygon_paths = sorted({polygon for _, polygon in products})
    exact_tiles: set[tuple[int, int]] = set()
    product_stats: list[ProductDemStats] = []
    root = Path(repo_root)
    polygon_tiles = {
        polygon: tiles_for_polygon(read_poly(root / polygon)) for polygon in polygon_paths
    }
    for product, polygon in products:
        tiles = polygon_tiles[polygon]
        exact_tiles.update(tiles)
        available = [inventory[tile] for tile in tiles if tile in inventory]
        product_stats.append(
            ProductDemStats(
                product=product,
                polygon=polygon,
                intersecting_tiles=len(tiles),
                available_files=len(available),
                available_bytes=sum(item.size for item in available),
                intersecting_tiles_without_file=sum(tile not in inventory for tile in tiles),
            )
        )

    exact_inventory = sorted(
        (inventory[tile] for tile in exact_tiles if tile in inventory), key=lambda item: item.path
    )
    selected_tiles: set[tuple[int, int]] = set()
    for latitude, longitude in exact_tiles:
        for lat_offset in range(-halo, halo + 1):
            candidate_lat = latitude + lat_offset
            if not -90 <= candidate_lat < 90:
                continue
            for lon_offset in range(-halo, halo + 1):
                candidate_lon = ((longitude + lon_offset + 180) % 360) - 180
                selected_tiles.add((candidate_lat, candidate_lon))
    selected_inventory = sorted(
        (inventory[tile] for tile in selected_tiles if tile in inventory), key=lambda item: item.path
    )
    missing = tuple(sorted(format_hgt_name(*tile) for tile in exact_tiles if tile not in inventory))
    return DemSelection(
        elevation_products=tuple(key for key, _ in products),
        polygons=tuple(polygon_paths),
        inventory_files=len(all_files),
        inventory_bytes=sum(size for _, size in all_files),
        inventory_hgt_files=len(inventory),
        inventory_hgt_bytes=sum(item.size for item in inventory.values()),
        exact_tiles=len(exact_tiles),
        exact_files=tuple(item.path for item in exact_inventory),
        exact_bytes=sum(item.size for item in exact_inventory),
        halo=halo,
        selected_files=tuple(item.path for item in selected_inventory),
        selected_bytes=sum(item.size for item in selected_inventory),
        intersecting_tiles_without_file=missing,
        product_stats=tuple(product_stats),
    )


def write_selection(
    selection: DemSelection,
    output: str | Path,
    exact_output: str | Path,
    report: str | Path,
) -> None:
    for target, paths in (
        (Path(output), selection.selected_files),
        (Path(exact_output), selection.exact_files),
    ):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("".join(f"{path}\n" for path in paths), encoding="utf-8")
    report_path = Path(report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_payload = selection.to_dict()
    report_payload["exact_files_count"] = len(selection.exact_files)
    report_payload["selected_files_count"] = len(selection.selected_files)
    del report_payload["exact_files"]
    del report_payload["selected_files"]
    report_path.write_text(
        json.dumps(report_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
