#!/bin/sh

 echo .
 echo .
date
 echo .
 echo .

mkdir output/volga
mkdir output/volga/garmin

 echo .
 echo . 
 rm ./output/volga/*.*
 rm -r ./output/volga/garmin/*.*
 echo .
 echo .

cd ./input
# wget -N "https://download.geofabrik.de/russia/volga-fed-district-latest.osm.pbf"



 echo .   Osmosis 
 echo .
 echo . Adds fake admin_level tag for all place polygons.
 echo . This is needed for better search generation after creating borders with mkgmap
 

cd ../output


osmium extract -O -v --progress --strategy=simple --polygon=../poly/volga-fed-district.poly \
   ../input/russia-latest.osm.pbf \
   -o volga-fed-district-latest.osm.pbf



 ../tools/osmosis/bin/osmosis \
 --read-pbf-fast volga-fed-district-latest.osm.pbf \
 --tag-transform file=./transform_places.xml \
 --write-pbf file=volga-fed-district2.osm.pbf \
 omitmetadata=true


			# ../tools/osmosis/bin/osmosis \
			# --read-pbf-fast volga-fed-district2.osm.pbf \
			# --lp --bb clipIncompleteEntities=true \
			# --tag-area-content file=tag-highway.xml \
			# --write-pbf file=volga-fed-district.tag1.osm.pbf \
			# omitmetadata=true
			
			
			# ../tools/osmosis/bin/osmosis \
			# --read-pbf-fast volga-fed-district.tag1.osm.pbf \
			# --lp --tag-area-content file=tag-poi-addr.xml \
			# --write-pbf file=volga-fed-district.tag2.osm.pbf \
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
   volga-fed-district2.osm.pbf \
   ../elevation/ele_10_ru_volga-fed-district.osm.pbf \
   -o topo_volga-fed-district.osm.pbf


# ../tools/osmosis/bin/osmosis \
#    --read-pbf-fast volga-fed-district2.osm.pbf \
#    --read-pbf-fast ../elevation/ele_10_ru_volga-fed-district.osm.pbf \
#    --merge \
#    --write-pbf file=topo_volga-fed-district.osm.pbf omitmetadata=true

 echo .
 echo .
date
 echo .
 echo . 
 

echo =============================================================
echo .
echo .   splitting ready files
echo .


cd volga

 java -jar ../../tools/splitter/splitter.jar ../topo_volga-fed-district.osm.pbf \
 --description="Volga_OSM" \
 --precomp-sea=../../input/sea-latest.zip \
 --keep-complete=true \
 --mapid=10010001 \
 --max-nodes=2000000 \
 --geonames-file=../../input/ru.zip \
 --output=pbf \
 --wanted-admin-level=8 \
 --output-dir=../volga

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
 --family-id=1001 \
 --family-name="Volga.OSM" \
 --series-name="Volga.OSM" \
 --description="Volga.OSM ($timestamp)" \
 --overview-mapname="Volga.OSM" \
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
mv gmapsupp.img Volga-fed-district.img
cp Volga-fed-district.img /mnt/nod/garmin

zip -r -0 -s=0 Volga-fed-district-ms.zip ./Volga.OSM.gmap
cp Volga-fed-district-ms.z* /mnt/nod/garmin/mapsource

