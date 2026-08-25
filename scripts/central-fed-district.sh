#!/bin/sh

 echo .
 echo .
date
 echo .
 echo .

mkdir output/central
mkdir output/central/garmin

 echo .
 echo . 
 rm ./output/central/*.*
 rm -r ./output/central/garmin/*.*
 echo .
 echo .

cd ./input
# wget -N "https://download.geofabrik.de/russia/central-fed-district-latest.osm.pbf"



cd ../output

osmium extract -O -v --progress --strategy=simple --polygon=../poly/central-fed-district.poly \
   ../input/russia-latest.osm.pbf \
   -o central-fed-district-latest.osm.pbf



 echo .   Osmosis 
 echo .
 echo . Adds fake admin_level tag for all place polygons.
 echo . This is needed for better search generation after creating borders with mkgmap
 

 ../tools/osmosis/bin/osmosis \
 --read-pbf-fast central-fed-district-latest.osm.pbf \
 --tag-transform file=./transform_places.xml \
 --write-pbf file=central-fed-district.osm.pbf \
 omitmetadata=true


			# ../tools/osmosis/bin/osmosis \
			# --read-pbf-fast central-fed-district2.osm.pbf \
			# --lp --bb clipIncompleteEntities=true \
			# --tag-area-content file=tag-highway.xml \
			# --write-pbf file=central-fed-district.tag1.osm.pbf \
			# omitmetadata=true
			
			
			# ../tools/osmosis/bin/osmosis \
			# --read-pbf-fast central-fed-district.tag1.osm.pbf \
			# --lp --tag-area-content file=tag-poi-addr.xml \
			# --write-pbf file=central-fed-district.tag2.osm.pbf \
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



osmium merge -O -v --progress central-fed-district.osm.pbf ../elevation/ele_10_ru_central-fed-district.osm.pbf -o topo_central-fed-district.osm.pbf

# ../tools/osmosis/bin/osmosis \
#    --read-pbf-fast central-fed-district2.osm.pbf \
#    --read-pbf-fast ../elevation/ele_10_ru_central-fed-district.osm.pbf \
#    --merge \
#    --write-pbf file=topo_central-fed-district.osm.pbf omitmetadata=true

 echo .
 echo .
date
 echo .
 echo . 
 

echo =============================================================
echo .
echo .   splitting ready files
echo .


cd central

 java -jar ../../tools/splitter/splitter.jar ../topo_central-fed-district.osm.pbf \
 --description="Central OSM" \
 --precomp-sea=../../input/sea-latest.zip \
 --keep-complete=true \
 --mapid=10060001 \
 --max-nodes=1000000 \
 --geonames-file=../../input/ru.zip \
 --output=pbf \
 --wanted-admin-level=8 \
 --output-dir=../central

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
 --family-id=1006 \
 --family-name="Central.OSM" \
 --series-name="Central.OSM" \
 --description="Central.OSM ($timestamp)" \
 --overview-mapname="Central.OSM" \
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
mv gmapsupp.img Central-fed-district.img
cp Central-fed-district.img /mnt/nod/garmin

zip -r -0 -s=0 Central-fed-district-ms.zip ./Central.OSM.gmap
cp Central-fed-district-ms.z* /mnt/nod/garmin/mapsource