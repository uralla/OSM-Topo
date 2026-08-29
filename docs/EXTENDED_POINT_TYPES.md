# Extended point types on Garmin

## Device rule

On the target Garmin, custom point families `0x115xx`, `0x116xx` and higher extended point addresses are not considered safe merely because mkgmap/TYP accepts them. Device visibility is the deciding criterion.

For custom POIs that must be visible, this project uses the device-proven `0x064xx` point family and moves the complete TYP bitmap block together with the style address.

## Current migration

| Previous active type | Current `0x064xx` type |
| --- | --- |
| `0x11601` | `0x6400` |
| `0x11604` | `0x640e` |
| `0x11605` | `0x640f` |
| `0x11803` | `0x6412` |
| `0x1341d` | `0x6413` |
| `0x1341e` | `0x6414` |
| `0x1341f` | `0x6415` |
| `0x13703` | `0x6416` |

The table contains only extended types that were active in the production point style at migration time. TYP-only historical blocks are not treated as active map objects.
