# POI group `0x115` migration

This file is the authoritative current-state record for POI group `0x115`. Historical snapshots under `docs/history/` are not current state.

## Status: COMPLETE

No production point rule and no TYP `_point` block remains in group `0x115`.

| Old type | Meaning | Current type |
| --- | --- | --- |
| `0x11500` | межевой знак | `0x6609` |
| `0x11501` | очистные сооружения | `0x641e` |
| `0x11504` | урочище / locality | `0x660a` |
| `0x11505` | пчеловод | `0x2f1a` |
| `0x11506` | тура | `0x660b` |
| `0x11507` | седловина / перевал | `0x660c` |
| `0x11509` | chalet / домик | `0x2b08` |
| `0x1150a` | велосипеды / велосервис | `0x2f18` |

The final six moves preserve their original TYP bitmap blocks and change only the Garmin address plus descriptive comment.
