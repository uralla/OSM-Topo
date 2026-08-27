from __future__ import annotations

from pathlib import Path
import re


TYP = Path("styles/uralla.txt")
MARKER = "; === URALLA ROAD/TRAIL ROLE TYPES 0x135 ==="

# New semantic role -> existing visual template.
ROLES = (
    ("0x01", "forest-road-good-far", "0x07"),
    ("0x02", "forest-road-good-near", "0x0a"),
    ("0x03", "forest-road-bad-far", "0x12"),
    ("0x04", "forest-road-bad-near", "0x0a"),
    ("0x05", "pedestrian-cycleway-far", "0x07"),
    ("0x06", "pedestrian-cycleway-near", "0x0e"),
    ("0x07", "foot-trail-far", "0x0b"),
    ("0x08", "foot-trail-near", "0x2e"),
    ("0x09", "bicycle-trail-far", "0x0b"),
    ("0x0a", "bicycle-trail-near", "0x16"),
)


def blocks(text: str) -> list[str]:
    return re.findall(r"\[_line\]\r?\n.*?\r?\n\[end\]", text, flags=re.S | re.I)


def type_of(block: str) -> str | None:
    match = re.search(r"(?mi)^Type=(0x[0-9a-f]+)\s*$", block)
    return match.group(1).lower() if match else None


def clone(block: str, subtype: str, role: str) -> str:
    newline = "\r\n" if "\r\n" in block else "\n"
    lines = block.splitlines()
    out: list[str] = []
    replaced = False
    for line in lines:
        if re.fullmatch(r"Type=0x[0-9a-f]+", line, flags=re.I):
            out.append("Type=0x135")
            out.append(f"SubType={subtype}")
            out.append(f"; URALLA_ROLE: {role}")
            replaced = True
            continue
        if re.fullmatch(r"SubType=0x[0-9a-f]+", line, flags=re.I):
            continue
        out.append(line)
    if not replaced:
        raise RuntimeError(f"template for {role} has no Type line")
    return newline.join(out)


def main() -> None:
    raw = TYP.read_bytes()
    text = raw.decode("cp1251")
    if MARKER in text:
        print("role types already present; nothing to do")
        return

    by_type = {type_of(block): block for block in blocks(text)}
    generated: list[str] = []
    for subtype, role, source in ROLES:
        template = by_type.get(source.lower())
        if template is None:
            raise RuntimeError(f"missing TYP line template {source} for {role}")
        generated.append(clone(template, subtype, role))

    newline = "\r\n" if "\r\n" in text else "\n"
    addition = newline.join(("", "", MARKER, *generated, ""))
    TYP.write_bytes((text + addition).encode("cp1251"))
    print("added 10 semantic road/trail line types under Type=0x135")


if __name__ == "__main__":
    main()
