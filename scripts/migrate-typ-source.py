#!/usr/bin/env python3
"""One-time migration: make styles/uralla.txt the authoritative TYP source."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TYP = ROOT / "styles" / "uralla.txt"
MANIFEST = ROOT / "config" / "maps.yaml"

PIER_POLYGON_OLD = '''[_polygon]
Type=0x10f11
;GRMN_TYPE: Customizable Areas/CUSTOMIZABLE_AREA_18/Customizable area/Non NT, NT
String1=0x19,пирс
String2=0x04,pier
ExtendedLabels=Y
FontStyle=NoLabel (invisible)
CustomColor=No
ContourColor=No
Xpm="0 0 1 0"
"1 c #E6E6E6"
[end]'''

PIER_POLYGON_NEW = PIER_POLYGON_OLD.replace("#E6E6E6", "#626262")

PIER_LINE_OLD = '''[_line]
Type=0x10f07
;GRMN_TYPE: Customizable Line Types/CUSTOMIZABLE_LINE_40/Non-routable customizable line/Non NT, NT
UseOrientation=N
Xpm="32 5 2  1"
"! c #101010"
"  c none"
"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
"!!!     !!!     !!!     !!!     "
"!!!     !!!     !!!     !!!     "
"!!!     !!!     !!!     !!!     "
"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
;12345678901234567890123456789012
String1=0x19,пирс
String2=0x04,pier
ExtendedLabels=Y
FontStyle=NoLabel (invisible)
CustomColor=No
ContourColor=No
[end]'''

PIER_LINE_NEW = '''[_line]
Type=0x10f07
;GRMN_TYPE: Customizable Line Types/CUSTOMIZABLE_LINE_40/Non-routable customizable line/Non NT, NT
UseOrientation=N
LineWidth=3
Xpm="0 0 1 0"
"1 c #626262"
String1=0x19,пирс
String2=0x04,pier
ExtendedLabels=Y
FontStyle=NoLabel (invisible)
CustomColor=No
ContourColor=No
[end]'''


def migrate_definition(text: str, old: str, new: str, label: str) -> tuple[str, bool]:
    if new in text:
        return text, False
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one old definition, found {count}")
    return text.replace(old, new, 1), True


def main() -> int:
    typ_text = TYP.read_text(encoding="utf-8-sig")
    typ_text, polygon_changed = migrate_definition(
        typ_text, PIER_POLYGON_OLD, PIER_POLYGON_NEW, "pier polygon"
    )
    typ_text, line_changed = migrate_definition(
        typ_text, PIER_LINE_OLD, PIER_LINE_NEW, "pier line"
    )
    # Keep the BOM: mkgmap uses it to recognize this TYP source as UTF-8.
    TYP.write_text(typ_text, encoding="utf-8-sig", newline="\n")

    manifest_text = MANIFEST.read_text(encoding="utf-8")
    old_manifest = "  typ: styles/uralla.typ\n"
    new_manifest = "  typ: styles/uralla.txt\n"
    if new_manifest not in manifest_text:
        if manifest_text.count(old_manifest) != 1:
            raise SystemExit("manifest: expected exactly one styles/uralla.typ setting")
        manifest_text = manifest_text.replace(old_manifest, new_manifest, 1)
        MANIFEST.write_text(manifest_text, encoding="utf-8", newline="\n")
        manifest_changed = True
    else:
        manifest_changed = False

    print("TYP source migration complete")
    print(f"  pier polygon: {'updated' if polygon_changed else 'already current'}")
    print(f"  pier line:    {'updated' if line_changed else 'already current'}")
    print(f"  manifest:     {'updated' if manifest_changed else 'already current'}")
    print(f"  source:       {TYP}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
