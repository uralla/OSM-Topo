#!/bin/sh

 echo .
 echo .
date
 echo .
 echo .

 echo .
 echo . 
 rm ./output/crimea/*.*
 rm -r ./output/crimea/garmin/*.*
 echo .
 echo .

cd ./input
# wget -N "https://download.geofabrik.de/russia/crimean-fed-district-latest.osm.pbf"




 echo .   Osmosis 
 echo .
 echo . Adds fake admin_level tag for all place polygons.
 echo . This is needed for better search generation after creating borders with mkgmap
 

cd ../output


osmium extract -O -v --progress --strategy=simple --polygon=../poly/crimean-fed-district.poly \
   ../input/crimean-fed-district-latest.osm.pbf \
   -o crimean-fed-district-latest.osm.pbf


 ../tools/osmosis/bin/osmosis \
 --read-pbf-fast crimean-fed-district-latest.osm.pbf \
 --tag-transform file=./transform_places.xml \
 --write-pbf file=crimean-fed-district2.osm.pbf omitmetadata=true granularity=1000





			# ../tools/osmosis/bin/osmosis \
			# --read-pbf-fast crimean-fed-district2.osm.pbf \
			# --lp --bb clipIncompleteEntities=true \
			# --tag-area-content file=tag-highway.xml \
			# --write-pbf file=crimean-fed-district.tag1.osm.pbf \
			# omitmetadata=true granularity=1000 granularity=1000
			
			
			# ../tools/osmosis/bin/osmosis \
			# --read-pbf-fast crimean-fed-district.tag1.osm.pbf \
			# --lp --tag-area-content file=tag-poi-addr.xml \
			# --write-pbf file=crimean-fed-district.tag2.osm.pbf \
			# omitmetadata=true granularity=1000 granularity=1000

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
   crimean-fed-district2.osm.pbf \
   ../elevation/ele_10_ru_crimean-fed-district.osm.pbf \
   -o topo_crimean-fed-district.osm.pbf


# ../tools/osmosis/bin/osmosis \
#    --read-pbf-fast crimean-fed-district2.osm.pbf \
#    --read-pbf-fast ../elevation/ele_10_ru_crimean-fed-district.osm.pbf \
#    --read-pbf-fast ../elevation/crimea-depth.osm.pbf \
#    --merge \
#    --write-pbf file=topo_crimean-fed-district.osm.pbf omitmetadata=true granularity=1000
   

 echo .
 echo .
date
 echo .
 echo . 
 

 

echo =============================================================
echo .
echo .   splitting ready files
echo .


mkdir crimea
mkdir crimea/garmin

cd crimea

 java -jar ../../tools/splitter/splitter.jar ../topo_crimean-fed-district.osm.pbf \
 --description="Crimea OSM" \
 --precomp-sea=../../input/sea-latest.zip \
 --keep-complete=true \
 --mapid=10210001 \
 --max-nodes=4000000 \
 --geonames-file=../../input/ru.zip \
 --output=pbf \
 --wanted-admin-level=8 \
 --ignore-osm-bounds=true \
 --output-dir=../crimea

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
 --family-id=1021 \
 --family-name="Crimea.OSM" \
 --series-name="Crimea.OSM" \
 --description="Crimea.OSM ($timestamp)" \
 --overview-mapname="Crimea.OSM" \
 --country-name=RUS \
 --max-jobs=2 \
 --code-page=1251 \
 --gmapi \
 --bounds=../../input/bounds-latest.zip \
 --precomp-sea=../../input/sea-latest.zip \
 --output-dir=garmin \
 --gmapsupp *.pbf ../../styles/uralla.typ

 echo .
 echo .
date
 echo .
 echo .
 
cd ./garmin
mv gmapsupp.img Crimea.OSM.img
cp Crimea.OSM.img /mnt/nod/garmin

zip -r -0 -s=0 Crimea.OSM-ms.zip ./Crimea.OSM.gmap
cp Crimea.OSM-ms.z* /mnt/nod/garmin/mapsource

