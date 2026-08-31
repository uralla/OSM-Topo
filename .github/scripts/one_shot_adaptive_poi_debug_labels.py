from pathlib import Path


def with_debug_label(line: str, tier: str) -> str:
    marker = " [0x"
    assert marker in line, line
    assert "{ name " not in line, line
    return line.replace(
        marker,
        f" {{ name '${{name}} [{tier}]' | '[{tier}]' }} [0x",
        1,
    )


# Food and accommodation adaptive rules.
p = Path("styles/uralla/inc/priority_points")
lines = p.read_text().splitlines()
out = []
changed = {"H": 0, "M": 0, "L": 0}
for line in lines:
    adaptive_food = "0x2e02" in line and any(
        key in line
        for key in (
            "shop=supermarket",
            "shop=bakers",
            "shop=bakery",
            "shop=butcher",
            "shop=convenience",
            "shop=general",
            "shop=grocery",
            "shop=organic",
            "amenity=supermarket",
        )
    )
    adaptive_lodging = any(
        f"tourism={kind}" in line for kind in ("guest_house", "hotel", "hostel")
    )
    if adaptive_food or adaptive_lodging:
        tier = None
        if "resolution 22]" in line:
            tier = "H"
        elif "resolution 23]" in line:
            tier = "M"
        elif "resolution 24]" in line:
            tier = "L"
        if tier:
            line = with_debug_label(line, tier)
            changed[tier] += 1
    out.append(line)

assert changed == {"H": 8, "M": 5, "L": 4}, changed
text = "\n".join(out) + "\n"
needle = "# category-level resolution 23 fallback because they are intrinsically more important."
assert text.count(needle) == 1
text = text.replace(
    needle,
    needle + "\n# Temporary visual debug suffixes: H=22, M=23, L=24.",
    1,
)
p.write_text(text)


# Adaptive bus/trolleybus stops. Keep bus_station/tram and non-bus platforms fixed/unmarked.
p = Path("styles/uralla/points")
text = p.read_text()
lines = text.splitlines()
out = []
changed = {"H": 0, "M": 0}
for line in lines:
    is_adaptive_transit = (
        "0x2f08" in line
        and "mkgmap:area2poi!=true" in line
        and ("highway=bus_stop" in line or "public_transport=platform" in line)
        and ("uralla:poi_priority=" in line or "uralla:poi_activity_context=remote" in line)
    )
    if is_adaptive_transit:
        if "resolution 22]" in line:
            line = with_debug_label(line, "H")
            changed["H"] += 1
        elif "resolution 23]" in line:
            line = with_debug_label(line, "M")
            changed["M"] += 1
    out.append(line)
assert changed == {"H": 2, "M": 1}, changed
text = "\n".join(out) + "\n"

old = """public_transport=platform & !(layer<0) & mkgmap:area2poi!=true
\t| highway=bus_stop & mkgmap:area2poi!=true
\t| amenity=bus_station & mkgmap:area2poi!=true
\t| railway=tram_stop & mkgmap:area2poi!=true [0x2f08 resolution 24]
"""
new = """(highway=bus_stop | public_transport=platform & (bus=yes | trolleybus=yes)) & mkgmap:area2poi!=true { name '${name} [L]' | '[L]' } [0x2f08 resolution 24]
public_transport=platform & !(layer<0) & mkgmap:area2poi!=true
\t| amenity=bus_station & mkgmap:area2poi!=true
\t| railway=tram_stop & mkgmap:area2poi!=true [0x2f08 resolution 24]
"""
assert text.count(old) == 1, text.count(old)
text = text.replace(old, new, 1)
p.write_text(text)
