#!/usr/bin/env python3
"""One-time migration: restrict the legacy pier line rule to open ways."""

from pathlib import Path

PATH = Path("styles/uralla/lines")
OLD = "man_made=pier { name 'пирс' } [0x10f07 resolution 24 continue]"
NEW = "man_made=pier & is_closed()=false { name 'пирс' } [0x10f07 resolution 24 continue]"


def main() -> int:
    text = PATH.read_text(encoding="utf-8")
    if NEW in text:
        print(f"already fixed: {PATH}")
        return 0
    count = text.count(OLD)
    if count != 1:
        raise SystemExit(f"expected exactly one legacy pier rule, found {count}")
    PATH.write_text(text.replace(OLD, NEW, 1), encoding="utf-8", newline="\n")
    print(f"fixed: {PATH}")
    print(f"  {NEW}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
