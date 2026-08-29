# POI group `0x115` migration

This file is the authoritative **current-state** record for the `0x115` point group under backlog task `POI-01`.

Historical snapshots under `docs/history/` are intentionally not edited when types move. They describe the repository at an earlier date and must not be used to decide which `0x115` types are still active.

## Current production remainder

As of the current `main`, production point style and TYP contain exactly these six `0x115` subtypes:

| Garmin type | Current meaning | Production rule |
| --- | --- | --- |
| `0x11500` | межевой знак | `historic=boundary_stone` |
| `0x11501` | очистные сооружения | `man_made=wastewater_plant` |
| `0x11504` | урочище / locality | `place=locality` |
| `0x11506` | тура | `man_made=cairn` |
| `0x11507` | седловина / перевал | `natural=saddle` and `mountain_pass=yes` |
| `0x11509` | chalet / домик | `tourism=chalet` |

These six are **not migrated yet**. They are the complete remaining scope of the `0x115` migration unless a later deliberate rule introduces another subtype.

## Confirmed completed migrations

The following former `0x115` types have already been removed from both production style and TYP:

| Old type | Meaning | Current type | Evidence |
| --- | --- | --- | --- |
| `0x11505` | пчеловод | `0x2f1a` | commit `a95fde3f2a59dec5c413fc2bcc70b5b5b16716c4` |
| `0x1150a` | велосипеды / велосервис | `0x2f18` | commit `4dc53cb50692966f675364d8bb8664acdbfffe8a` |

The old codes above are forbidden as current production references. `tests/test_group_115_migration.py` checks that neither their style rules nor their TYP blocks return.

## Empty subtype numbers are not migration records

Missing values such as `0x11502`, `0x11503`, `0x11508` and other gaps are **not** to be described as “already migrated” without a concrete repository-history proof. A gap only means the subtype is not active now.

For migration accounting, use only these categories:

1. **remaining** — present in current production style and matching TYP;
2. **confirmed migrated** — old type and destination are proven by a commit;
3. **inactive/unknown history** — absent now, but no migration claim is made.

This prevents old comments, removed experiments, historical snapshots, or stale tests from being mistaken for the current map state.

## Guardrail

`tests/test_group_115_migration.py` is the machine-readable current-state guardrail. Its `REMAINING_115` set must shrink each time one of the six remaining types is moved. When the group migration is complete, that set must be empty and no `_point` block with `Type=0x115` may remain in the TYP file.
