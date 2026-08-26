#!/usr/bin/env python3
"""Prepare the build TYP source from the checked-in editable text definition."""

from __future__ import annotations

import argparse
from pathlib import Path


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

PIER_POLYGON_NEW = '''[_polygon]
Type=0x10f11
;GRMN_TYPE: Customizable Areas/CUSTOMIZABLE_AREA_18/Customizable area/Non NT, NT
String1=0x19,пирс
String2=0x04,pier
ExtendedLabels=Y
FontStyle=NoLabel (invisible)
CustomColor=No
ContourColor=No
Xpm="0 0 1 0"
"1 c #626262"
[end]'''

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


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"TYP source: expected exactly one {label} definition, found {count}")
    return text.replace(old, new, 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    source = Path(args.input)
    destination = Path(args.output)
    text = source.read_text(encoding="utf-8")
    text = replace_once(text, PIER_POLYGON_OLD, PIER_POLYGON_NEW, "pier polygon")
    text = replace_once(text, PIER_LINE_OLD, PIER_LINE_NEW, "pier line")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8", newline="\n")
    print(f"prepared TYP source: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
