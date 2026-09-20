OFFLINE OVERPASS → GPKG + POLY

Запуск без полигона:
  ./offline_overpass_to_gpkg_poly.py query.overpass

Запуск внутри .poly:
  ./offline_overpass_to_gpkg_poly.py query.overpass --poly region.poly

Явно задать всё:
  ./offline_overpass_to_gpkg_poly.py query.overpass russia-latest.osm.pbf result.gpkg --poly region.poly

Если одновременно указан --poly и в Overpass-запросе присутствует [bbox:...],
сначала применяется polygon, затем bbox. Итоговая территория — их пересечение.

Для .poly используется osmium extract --polygon с complete_ways, поэтому ways,
пересекающие границу, сохраняются целиком вместе с необходимыми node-ссылками.
