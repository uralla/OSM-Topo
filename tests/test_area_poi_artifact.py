from __future__ import annotations

import unittest

from uralla_build.area_pois import (
    SYNTHETIC_AREA_POI_ID_BASE,
    area_poi_kind,
    synthetic_area_poi_id,
)


class AreaPoiArtifactTests(unittest.TestCase):
    def test_synthetic_id_is_stable_and_way_derived(self) -> None:
        self.assertEqual(
            synthetic_area_poi_id(4365587225),
            -(SYNTHETIC_AREA_POI_ID_BASE + 4365587225),
        )
        self.assertEqual(synthetic_area_poi_id(4365587225), synthetic_area_poi_id(4365587225))
        self.assertNotEqual(synthetic_area_poi_id(4365587225), synthetic_area_poi_id(4365587226))

    def test_building_ruins_is_promoted_to_ruins_poi_kind(self) -> None:
        self.assertEqual(
            area_poi_kind({"building": "ruins", "abandoned": "yes"}),
            "historic:ruins",
        )
        self.assertEqual(
            area_poi_kind({"building": "ruins", "historic": "ruins"}),
            "historic:ruins",
        )


if __name__ == "__main__":
    unittest.main()
