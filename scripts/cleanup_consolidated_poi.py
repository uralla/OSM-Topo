#!/usr/bin/env python3
"""Apply the already agreed POI consolidation to the physical style and TYP.

One-shot repository migration.  It is not part of the build pipeline; the
companion workflow deletes this file after committing the direct sources.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STYLE = ROOT / "styles" / "uralla"
POINTS = STYLE / "points"
PRIORITY = STYLE / "inc" / "priority_points"
TYP = ROOT / "styles" / "uralla.txt"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n == 1:
        return text.replace(old, new, 1)
    if n == 0 and new and new in text:
        return text  # idempotent rerun
    raise RuntimeError(f"{label}: expected one occurrence, found {n}")


def remove_once(text: str, old: str, label: str) -> str:
    n = text.count(old)
    if n == 1:
        return text.replace(old, "", 1)
    if n == 0:
        return text
    raise RuntimeError(f"{label}: expected at most one occurrence, found {n}")


def regex_remove_once(text: str, pattern: str, label: str) -> str:
    rx = re.compile(pattern, re.MULTILINE | re.DOTALL)
    matches = list(rx.finditer(text))
    if len(matches) == 1:
        m = matches[0]
        return text[: m.start()] + text[m.end() :]
    if not matches:
        return text
    raise RuntimeError(f"{label}: expected at most one block, found {len(matches)}")


def patch_priority() -> None:
    text = PRIORITY.read_text(encoding="utf-8")

    # English fallback strings are now fixed at their real rules in points.
    text = regex_remove_once(
        text,
        r"# Localized fallbacks for otherwise generic English defaults\.\n"
        r"amenity=embassy.*?highway=services.*?\n\n",
        "temporary localized fallback block",
    )

    text = replace_once(
        text,
        "# Grocery group.\n"
        "(shop=bakers | shop=bakery | shop=butcher | shop=convenience | shop=general | shop=organic | shop=supermarket) [0x2e02 resolution 24]",
        "# Grocery group. Supermarkets keep their established farther visibility.\n"
        "shop=supermarket [0x2e02 resolution 22]\n"
        "(shop=bakers | shop=bakery | shop=butcher | shop=convenience | shop=general | shop=organic) [0x2e02 resolution 24]",
        "grocery LOD",
    )
    text = replace_once(
        text,
        "shop=bicycle [0x2f13 resolution 24]",
        "shop=bicycle [0x2f13 resolution 23]",
        "bicycle shop LOD",
    )
    text = replace_once(
        text,
        "# Tourist accommodation / shelters.\n"
        "(tourism=hotel | tourism=hostel | tourism=guest_house | tourism=motel) [0x2b01 resolution 24]\n"
        "amenity=shelter [0x2b05 resolution 24]\n"
        "(tourism=wilderness_hut | tourism=alpine_hut) [0x2b07 resolution 24]",
        "# Tourist accommodation / shelters. Keep useful established LOD while\n"
        "# consolidating the visual Garmin types.\n"
        "tourism=guest_house [0x2b01 resolution 21]\n"
        "(tourism=hotel | tourism=hostel | tourism=motel) [0x2b01 resolution 24]\n"
        "amenity=shelter & mkgmap:area2poi!=true [0x2b05 resolution 23]\n"
        "(tourism=wilderness_hut | tourism=alpine_hut) [0x2b07 resolution 23 default_name 'Избушка']",
        "accommodation LOD",
    )
    text = replace_once(
        text,
        "(leisure=playground | leisure=sports_centre | leisure=pitch | leisure=swimming_pool | leisure=fitness_centre) { delete leisure }",
        "(leisure=playground | leisure=sports_center | leisure=sports_centre | leisure=pitch | leisure=swimming_pool | leisure=fitness_centre) { delete leisure }",
        "sports_center legacy spelling",
    )

    PRIORITY.write_text(text, encoding="utf-8", newline="")


def patch_points() -> None:
    text = POINTS.read_text(encoding="utf-8")

    # Localize the actual fallback definitions rather than masking them upstream.
    text = replace_once(
        text,
        "amenity=embassy & country!=* [0x3003 resolution 24 default_name 'Embassy']",
        "amenity=embassy & country!=* [0x3003 resolution 24 default_name 'Посольство']",
        "embassy fallback",
    )
    text = replace_once(
        text,
        "amenity=telephone [0x2f12 resolution 24 default_name 'Telephone']",
        "amenity=telephone [0x2f12 resolution 24 default_name 'Телефон']",
        "telephone fallback",
    )
    text = replace_once(
        text,
        "amenity=toilets [0x4e00 resolution 24 default_name 'Toilets' ]",
        "amenity=toilets [0x4e00 resolution 24 default_name 'Туалет' ]",
        "toilets fallback",
    )
    text = replace_once(
        text,
        "highway=services & mkgmap:area2poi!=true [0x210f resolution 24 default_name 'Services']",
        "highway=services & mkgmap:area2poi!=true [0x210f resolution 24 default_name 'Сервис']",
        "services fallback",
    )

    # Food: remove all old cuisine-specific active branches. The final rule lives
    # in inc/priority_points and keeps the POI name while using 0x2a00.
    for old, label in [
        ("amenity=cafe [0x2a0e resolution 24]\n", "old cafe class"),
        ("amenity=fast_food & cuisine=grill [0x2a03 resolution 24]\n", "fast food grill"),
        ("amenity=fast_food & cuisine ~ '.*pizza.*' [0x2a0a resolution 24]\n", "fast food pizza"),
        ("amenity=fast_food [0x2a07 resolution 24]\n", "fast food generic"),
        ("amenity=food_court [0x2a13 resolution 24]\n", "food court old class"),
    ]:
        text = remove_once(text, old, label)

    text = regex_remove_once(
        text,
        r"amenity=restaurant & cuisine=american \[0x2a01 resolution 24\]\n"
        r".*?"
        r"amenity=restaurant \[0x2a00 resolution 24\]\n\n",
        "restaurant cuisine block",
    )

    # Fuel: all physical legacy branches are superseded by the single early rule.
    text = regex_remove_once(
        text,
        r"amenity=fuel \[0x2f01 resolution 24\]\n"
        r".*?"
        r"#amenity=fuel \{ name '\$\{name\}' \| '\$\{operator\}' \} \[0x11603 resolution 22-19\]\n\n",
        "legacy fuel block",
    )

    # Duplicates now owned by priority_points.
    for old, label in [
        ("amenity=emergency_phone [0x2f12 resolution 23]\n", "legacy emergency phone"),
        ("amenity=shelter & mkgmap:area2poi!=true [0x2b05 resolution 23]\n", "legacy shelter"),
        ("historic=memorial {name '${inscription}'} [0x6403 resolution 24]\n", "legacy memorial"),
        ("leisure=nature_reserve & name=* [0x6612 resolution 20]\n", "nature reserve centre"),
        ("leisure=pitch & name=* { name '${name} (${sport})' | '${name}' }[0x2c08 resolution 24]\n", "pitch point"),
        ("leisure=playground & name=* [0x2c06 resolution 24]\n", "playground point"),
        ("(leisure=sports_center | leisure=sports_centre) & name=* { name '${name} (${sport})' | '${name}' } [0x2d0b resolution 24]\n", "sports centre point"),
        ("leisure=swimming_pool [0x2d09 resolution 24]\n", "swimming pool point"),
        ("leisure=fitness_centre [0x2d0a resolution 23]\n", "fitness centre point"),
        ("man_made=utility_pole [0x11506 resolution 24]\n", "utility pole point"),
        ("amenity=signpost { name '${label}' } [0x5a00 resolution  24]\n", "legacy signpost"),
        ("traffic_calming=*\t[0x11511 resolution 24]\n", "generic bump point"),
    ]:
        text = remove_once(text, old, label)

    # The whole historical shop matrix is intentionally replaced by the agreed
    # grocery/pharmacy/bicycle/auto/generic groups in priority_points.
    text = regex_remove_once(
        text,
        r"shop=bakers \[0x2e02 resolution 24\]\n"
        r".*?"
        r"shop=\* & shop!=no & shop!=none \[0x2e00 resolution 24\]\n\n",
        "legacy shop matrix",
    )

    # Separate tourist huts from generic buildings; remove the old combined rule.
    text = regex_remove_once(
        text,
        r"tourism=wilderness_hut[ \t]*\n"
        r"\| tourism=alpine_hut[ \t]*\n"
        r"\| building=yes & mkgmap:area2poi!=true[ \t]*\n"
        r"\| building=true & mkgmap:area2poi!=true[ \t]*\n"
        r"\s*\{name .*?\[0x2b07 resolution 24 continue with_actions\] #\n\n",
        "combined hut/building rule",
    )

    # Caravan sites are removed; camp_site stays on the shared Garmin types.
    text = regex_remove_once(
        text,
        r"tourism=caravan_site \{name .*?\[0x4a01 resolution 23-23 continue\] #\n"
        r"tourism=caravan_site \{name .*?\[0x2b03 resolution 24\]\n",
        "caravan site rules",
    )

    # Accommodation classes now come from priority_points. chalet remains untouched
    # because it is still explicitly CHECK in the final review.
    text = remove_once(text, "tourism=guest_house [0x2b02 resolution 21]\n", "guest house old type")
    text = remove_once(text, "tourism=hostel [0x2b02 resolution 24]\n", "hostel old type")
    text = regex_remove_once(
        text,
        r"tourism=hotel \| tourism=motel[ \t]*\n"
        r"\{ name .*?\} \[0x2b01 resolution 24\]\n",
        "hotel/motel old rule",
    )
    text = remove_once(
        text,
        "tourism=wilderness_hut [0x2b07 resolution 23 default_name 'Избушка']\n",
        "wilderness hut old LOD",
    )

    POINTS.write_text(text, encoding="utf-8", newline="")


def detect_typ_encoding(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        raw.decode("cp1251")
        return "cp1251"


def section_pattern(kind: str) -> re.Pattern[str]:
    return re.compile(rf"(?ims)^\[{re.escape(kind)}\][ \t]*\r?\n.*?^\[end\][ \t]*(?:\r?\n)?")


def point_code(block: str) -> str | None:
    tm = re.search(r"(?im)^Type=0x([0-9a-f]+)\b", block)
    sm = re.search(r"(?im)^SubType=0x([0-9a-f]+)\b", block)
    if not tm:
        return None
    typ = tm.group(1).lower().lstrip("0") or "0"
    if not sm:
        return "0x" + typ
    sub = sm.group(1).lower().zfill(2)
    return "0x" + typ + sub


def active_style_type_codes() -> set[str]:
    codes: set[str] = set()
    files = [p for p in STYLE.rglob("*") if p.is_file()]
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        active_lines = []
        for line in text.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            # mkgmap comments occupy whole lines in this style; stripping an inline
            # comment is conservative for numeric type reference discovery.
            active_lines.append(line.split("#", 1)[0])
        active = "\n".join(active_lines)
        for code in re.findall(r"\[(0x[0-9a-fA-F]+)\b", active):
            raw = code[2:].lower().lstrip("0") or "0"
            codes.add("0x" + raw)
    return codes


def patch_typ() -> None:
    raw = TYP.read_bytes()
    enc = detect_typ_encoding(raw)
    text = raw.decode(enc)

    # This POI cleanup must not alter any line/polygon graphics, especially the
    # visually verified piers and the just-fixed tunnel/marina/rail slots.
    line_before = [m.group(0) for m in section_pattern("_line").finditer(text)]
    polygon_before = [m.group(0) for m in section_pattern("_polygon").finditer(text)]

    active = active_style_type_codes()

    # Only semantically approved consolidation/removal candidates. A candidate is
    # deleted iff no ACTIVE style rule references it after patch_points().
    candidates = {
        # cuisine/restaurant duplicate icons
        *(f"0x2a{i:02x}" for i in range(1, 0x18)),
        # old shop duplicate icons; keep 2e00, 2e02, 2e05 and new 2e0d
        "0x2e01", "0x2e03", "0x2e04", "0x2e06", "0x2e07",
        "0x2e08", "0x2e09", "0x2e0a", "0x2e0b", "0x2e0c",
        # old vehicle-shop icons; active non-shop uses automatically protect any
        # that are still legitimately used (e.g. 2f02/2f0d if present).
        "0x2f02", "0x2f07", "0x2f09", "0x2f0a", "0x2f0d", "0x2f10",
        # fuel duplicates / HGV diesel
        "0x2f16", "0x11603",
        # explicitly removed visual point classes
        "0x11506", "0x11511", "0x6612",
    }

    removed: list[str] = []
    skipped_active: list[str] = []
    matches = list(section_pattern("_point").finditer(text))
    for m in reversed(matches):
        code = point_code(m.group(0))
        if code not in candidates:
            continue
        canonical = "0x" + (code[2:].lstrip("0") or "0")
        if canonical in active:
            skipped_active.append(code)
            continue
        text = text[: m.start()] + text[m.end() :]
        removed.append(code)

    if [m.group(0) for m in section_pattern("_line").finditer(text)] != line_before:
        raise RuntimeError("a line TYP section changed during POI cleanup")
    if [m.group(0) for m in section_pattern("_polygon").finditer(text)] != polygon_before:
        raise RuntimeError("a polygon TYP section changed during POI cleanup")

    # Explicit removals must really be gone unless another active rule proved they
    # are still needed. Fuel HGV/duplicate and bump/utility are expected orphans.
    for required in ("0x2f16", "0x11603", "0x11506", "0x11511"):
        canonical = "0x" + (required[2:].lstrip("0") or "0")
        if canonical not in active:
            for m in section_pattern("_point").finditer(text):
                if point_code(m.group(0)) == required:
                    raise RuntimeError(f"orphan point TYP still present: {required}")

    TYP.write_bytes(text.encode(enc))
    print(f"TYP encoding preserved: {enc}")
    print("Removed orphan point TYP:", " ".join(sorted(removed)) or "none")
    print("Kept because still actively referenced:", " ".join(sorted(set(skipped_active))) or "none")


def verify_style_cleanup() -> None:
    p = POINTS.read_text(encoding="utf-8")
    forbidden = [
        "amenity=fuel [0x2f01",
        "fuel:HGV_diesel=yes [0x2f16",
        "waterway=fuel [0x11603",
        "amenity=restaurant & cuisine=",
        "amenity=fast_food & cuisine=",
        "shop=bakers [0x2e02",
        "man_made=utility_pole [0x11506",
        "tourism=caravan_site",
        "traffic_calming=*\t[0x11511",
        "leisure=nature_reserve & name=* [0x6612",
    ]
    leftovers = [s for s in forbidden if s in p]
    if leftovers:
        raise RuntimeError(f"legacy active rules remain: {leftovers}")


def main() -> None:
    patch_priority()
    patch_points()
    verify_style_cleanup()
    patch_typ()
    print("Consolidated POI cleanup completed")


if __name__ == "__main__":
    main()
