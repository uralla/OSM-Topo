from __future__ import annotations

import unittest
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from uralla_build.area_poi_analysis import (
    analyze_area_pois,
    area_poi_enrichments_from_analysis,
)
from uralla_build.analysis_bundle import _validated_area_enrichments
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

    def test_artifact_preserves_real_node_enrichment_and_freshness_versions(self) -> None:
        try:
            import osmium
        except ImportError:
            self.skipTest("optional osmium dependency is not installed")
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.osm"
            artifact = root / "area-pois.json.gz"
            source.write_text(
                """<?xml version='1.0' encoding='UTF-8'?>
<osm version='0.6' generator='uralla-test'>
  <node id='1' lat='55.0' lon='37.0' version='1'/>
  <node id='2' lat='55.0' lon='37.001' version='1'/>
  <node id='3' lat='55.001' lon='37.001' version='1'/>
  <node id='4' lat='55.001' lon='37.0' version='1'/>
  <node id='10' lat='55.0005' lon='37.0005' version='2'>
    <tag k='tourism' v='hostel'/>
  </node>
  <way id='100' version='3'>
    <nd ref='1'/><nd ref='2'/><nd ref='3'/><nd ref='4'/><nd ref='1'/>
    <tag k='building' v='yes'/>
    <tag k='tourism' v='guest_house'/>
    <tag k='name' v='Приют'/>
  </way>
</osm>
""",
                encoding="utf-8",
            )
            plan, stats = analyze_area_pois(source, artifact, osmium)
            loaded = area_poi_enrichments_from_analysis(artifact)
            counters: Counter[str] = Counter()
            valid = _validated_area_enrichments(source, loaded, osmium, counters)

        self.assertFalse(plan.synthetic)
        self.assertEqual(stats["matched_areas"], 1)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].node_id, 10)
        self.assertEqual(loaded[0].node_version, 2)
        self.assertEqual(loaded[0].source_version, 3)
        self.assertEqual(loaded[0].added_tags, {"name": "Приют"})
        self.assertIn(10, valid)
        self.assertEqual(counters["area_enrichment_stale_skipped"], 0)


if __name__ == "__main__":
    unittest.main()
