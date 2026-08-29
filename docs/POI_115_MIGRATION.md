# POI group `0x115` migration

This file is the authoritative current-state record for the former `0x115` POIs. Historical snapshots under `docs/history/` are not current state.

## Status: MIGRATED TO `0x064xx`, DEVICE VERIFICATION PENDING

The previous attempt moved several symbols to numerically free `0x66xx`/other addresses. That was not a valid definition of “safe”: those addresses can fail to render on the target Garmin. The affected custom symbols are now consolidated in the already proven `0x064xx` point family.

| Old type | Meaning | Current type |
| --- | --- | --- |
| `0x11500` | межевой знак | `0x6404` |
| `0x11501` | очистные сооружения | `0x6407` |
| `0x11504` | урочище / locality | `0x6408` |
| `0x11505` | пчеловод | `0x2f1a` |
| `0x11506` | тура | `0x6409` |
| `0x11507` | седловина / перевал | `0x640a` |
| `0x11509` | chalet / домик | `0x640d` |
| `0x1150a` | велосипеды / велосервис | `0x2f18` |

The TYP bitmap artwork for each of the six remapped symbols was moved with the style address; only Type/SubType changed.

## Device-safety rule

A free Garmin type is not automatically a working or safe type. For custom POIs, prefer a type family already confirmed on the target device. `0x064xx` is the working anchor for this set. `0x66xx` and extended `0x11xxx` families must not be used merely because a subtype is vacant. Real-device rendering is the final criterion.
