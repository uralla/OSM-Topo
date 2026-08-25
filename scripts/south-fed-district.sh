#!/bin/sh

 echo .
 echo .
date
 echo .
 echo .

mkdir output/south
mkdir output/south/garmin

 echo .
 echo . 
 rm ./output/south/*.*
 rm -r ./output/south/garmin/*.*
 echo .
 echo .

cd ./input
# wget -N "https://download.geofabrik.de/russia/south-fed-district-latest.osm.pbf"




cd ../output

osmium extract -O -v --progress --strategy=simple --polygon=../poly/south-fed-district.poly \
   ../input/russia-latest.osm.pbf \
   -o south-fed-district-latest.osm.pbf


 echo .   Osmosis 
 echo .
 echo . Adds fake admin_level tag for all place polygons.
 echo . This is needed for better search generation after creating borders with mkgmap
 


 ../tools/osmosis/bin/osmosis \
 --read-pbf-fast south-fed-district-latest.osm.pbf \
 --tag-transform file=./transform_places.xml \
 --write-pbf file=south-fed-district2.osm.pbf \
 omitmetadata=true


			# ../tools/osmosis/bin/osmosis \
			# --read-pbf-fast south-fed-district2.osm.pbf \
			# --lp --bb clipIncompleteEntities=true \
			# --tag-area-content file=tag-highway.xml \
			# --write-pbf file=south-fed-district.tag1.osm.pbf \
			# omitmetadata=true
			
			
			# ../tools/osmosis/bin/osmosis \
			# --read-pbf-fast south-fed-district.tag1.osm.pbf \
			# --lp --tag-area-content file=tag-poi-addr.xml \
			# --write-pbf file=south-fed-district.tag2.osm.pbf \
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


osmium merge -O -v --progress south-fed-district2.osm.pbf ../elevation/ele_10_ru_south-fed-district.osm.pbf -o topo_south-fed-district.osm.pbf


# ../tools/osmosis/bin/osmosis \
#    --read-pbf-fast south-fed-district2.osm.pbf \
#    --read-pbf-fast ../elevation/ele_10_ru_south-fed-district.osm.pbf \
#    --merge \
#    --write-pbf file=topo_south-fed-district.osm.pbf omitmetadata=true

 echo .
 echo .
date
 echo .
 echo . 
 

echo =============================================================
echo .
echo .   splitting ready files
echo .


cd south

java -jar ../../tools/splitter/splitter.jar ../topo_south-fed-district.osm.pbf \
 --description="South_OSM" \
 --precomp-sea=../../input/sea-latest.zip \
 --keep-complete=true \
 --mapid=10030001 \
 --max-nodes=2000000 \
 --geonames-file=../../input/ru.zip \
 --output=pbf \
 --wanted-admin-level=8 \
 --output-dir=../south

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
 --family-id=1003 \
 --family-name="South.OSM" \
 --series-name="South.OSM" \
 --description="South.OSM ($timestamp)" \
 --overview-mapname="South.OSM" \
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
mv gmapsupp.img South-fed-district.img
cp South-fed-district.img /mnt/nod/garmin

zip -r -0 -s=0 South-fed-district-ms.zip ./South.OSM.gmap
cp South-fed-district-ms.z* /mnt/nod/garmin/mapsource