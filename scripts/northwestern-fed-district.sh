#!/bin/sh

 echo .
 echo .
date
 echo .
 echo .

mkdir output/northwestern
mkdir output/northwestern/garmin

 echo .
 echo . 
 rm ./output/northwestern/*.*
 rm -r ./output/northwestern/garmin/*.*
 echo .
 echo .

cd ./input
#wget -N "https://download.geofabrik.de/russia/northwestern-fed-district-latest.osm.pbf"



 echo .   Osmosis 
 echo .
 echo . Adds fake admin_level tag for all place polygons.
 echo . This is needed for better search generation after creating borders with mkgmap
 

cd ../output


#osmium extract -O -v --progress --strategy=simple --polygon=../poly/northwestern-fed-district.poly \
#   ../input/russia-latest.osm.pbf \
#   -o northwestern-fed-district-latest.osm.pbf

 ../tools/osmosis/bin/osmosis \
 --read-pbf-fast ../input/northwestern-fed-district-latest.osm.pbf \
 --tag-transform file=./transform_places.xml \
 --write-pbf file=northwestern-fed-district2.osm.pbf \
 omitmetadata=true


			# ../tools/osmosis/bin/osmosis \
			# --read-pbf-fast northwestern-fed-district2.osm.pbf \
			# --lp --bb clipIncompleteEntities=true \
			# --tag-area-content file=tag-highway.xml \
			# --write-pbf file=northwestern-fed-district.tag1.osm.pbf \
			# omitmetadata=true
			
			
			# ../tools/osmosis/bin/osmosis \
			# --read-pbf-fast northwestern-fed-district.tag1.osm.pbf \
			# --lp --tag-area-content file=tag-poi-addr.xml \
			# --write-pbf file=northwestern-fed-district.tag2.osm.pbf \
			# omitmetadata=true

 echo .
 echo .
date
 echo .
 echo .
 
echo =============================================================
echo .
echo .   join OSM and elevation data
echo .
echo .



osmium merge -O -v --progress \
   northwestern-fed-district2.osm.pbf \
   ../elevation/ele_10_ru_northwestern-fed-district.osm.pbf \
   -o topo_northwestern-fed-district.osm.pbf


# ../tools/osmosis/bin/osmosis \
#    --read-pbf-fast northwestern-fed-district2.osm.pbf \
#    --read-pbf-fast ../elevation/ele_10_ru_northwestern-fed-district.osm.pbf \
#    --merge \
#    --write-pbf file=topo_northwestern-fed-district.osm.pbf omitmetadata=true

 echo .
 echo .
date
 echo .
 echo . 
 

echo =============================================================
echo .
echo .   splitting ready files
echo .


cd northwestern

 java -jar ../../tools/splitter/splitter.jar ../topo_northwestern-fed-district.osm.pbf \
 --description="Northwestern_OSM" \
 --precomp-sea=../../input/sea-latest.zip \
 --keep-complete=true \
 --mapid=10070001 \
 --max-nodes=400000 \
 --geonames-file=../../input/ru.zip \
 --output=pbf \
 --wanted-admin-level=8 \
 --output-dir=../northwestern


 echo .
 echo .
date
 echo .
 echo .
 



echo =============================================================
echo .
echo .   MAKES FINAL MAPS
echo .


timestamp=$(date +%d.%m.%Y)


 

java -jar ../../tools/mkgmap/mkgmap.jar  -c ../../styles/uralla.args \
--style-file=../../styles/uralla \
--family-id=1007 \
--family-name="Northwestern.OSM" \
--series-name="Northwestern.OSM" \
--description="Northwestern.OSM ($timestamp)" \
--overview-mapname="Northwestern.OSM" \
--country-name=RUS \
--code-page=1251 \
--gmapi \
--bounds=../../input/bounds-latest.zip \
--precomp-sea=../../input/sea-latest.zip \
--output-dir=garmin \
--dem-dists=15000 \
--dem-poly=../../poly/northwestern-fed-district.poly \
--gmapsupp *.pbf ../../styles/uralla.typ

 echo .
 echo .
date
 echo .
 echo .

cd ./garmin
mv gmapsupp.img Northwestern-fed-district.img
cp Northwestern-fed-district.img /mnt/nod/garmin


zip -r -0 -s=0 Northwestern-fed-district-ms.zip ./Northwestern.OSM.gmap
cp Northwestern-fed-district-ms.z* /mnt/nod/garmin/mapsource
