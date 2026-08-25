#!/bin/sh

 echo .
 echo .
date
 echo .
 echo .

mkdir output/north-caucasus
mkdir output/north-caucasus/garmin

 echo .
 echo . 
 rm ./output/north-caucasus/*.*
 rm -r ./output/north-caucasus/garmin/*.*
 echo .
 echo .

cd ./input
# wget -N "https://download.geofabrik.de/russia/north-caucasus-fed-district-latest.osm.pbf"


cd ../output


osmium extract -O -v --progress --strategy=simple --polygon=../poly/north-caucasus-fed-district.poly \
   ../input/russia-latest.osm.pbf \
   -o north-caucasus-fed-district-latest.osm.pbf




 echo .   Osmosis 
 echo .
 echo . Adds fake admin_level tag for all place polygons.
 echo . This is needed for better search generation after creating borders with mkgmap
 

 ../tools/osmosis/bin/osmosis \
 --read-pbf-fast north-caucasus-fed-district-latest.osm.pbf \
 --tag-transform file=./transform_places.xml \
 --write-pbf file=north-caucasus-fed-district2.osm.pbf \
 omitmetadata=true


			# ../tools/osmosis/bin/osmosis \
			# --read-pbf-fast north-caucasus-fed-district2.osm.pbf \
			# --lp --bb clipIncompleteEntities=true \
			# --tag-area-content file=tag-highway.xml \
			# --write-pbf file=north-caucasus-fed-district.tag1.osm.pbf \
			# omitmetadata=true
			
			
			# ../tools/osmosis/bin/osmosis \
			# --read-pbf-fast north-caucasus-fed-district.tag1.osm.pbf \
			# --lp --tag-area-content file=tag-poi-addr.xml \
			# --write-pbf file=north-caucasus-fed-district.tag2.osm.pbf \
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
   north-caucasus-fed-district2.osm.pbf \
   ../elevation/ele_10_ru_north-caucasus-fed-district.osm.pbf \
   -o topo_north-caucasus-fed-district.osm.pbf


# ../tools/osmosis/bin/osmosis \
#    --read-pbf-fast north-caucasus-fed-district2.osm.pbf \
#    --read-pbf-fast ../elevation/ele_10_ru_north-caucasus-fed-district.osm.pbf \
#    --merge \
#    --write-pbf file=topo_north-caucasus-fed-district.osm.pbf omitmetadata=true

 echo .
 echo .
date
 echo .
 echo . 
 

echo =============================================================
echo .
echo .   splitting ready files
echo .


cd north-caucasus

 java -jar ../../tools/splitter/splitter.jar ../topo_north-caucasus-fed-district.osm.pbf \
 --description="North-Caucasus_OSM" \
 --precomp-sea=../../input/sea-latest.zip \
 --keep-complete=true \
 --mapid=10040001 \
 --max-nodes=1000000 \
 --geonames-file=../../input/ru.zip \
 --output=pbf \
 --wanted-admin-level=8 \
 --output-dir=../north-caucasus

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
 --family-id=1004 \
 --family-name="North-Caucasus.OSM" \
 --series-name="North-Caucasus.OSM" \
 --description="North-Caucasus.OSM ($timestamp)" \
 --overview-mapname="North-Caucasus.OSM" \
 --country-name=RUS \
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
mv gmapsupp.img North-Caucasus.OSM.img
cp North-Caucasus.OSM.img /mnt/nod/garmin

zip -r -0 -s=0 North-Caucasus.OSM-ms.zip ./North-Caucasus.OSM.gmap
cp North-Caucasus.OSM-ms.z* /mnt/nod/garmin/mapsource