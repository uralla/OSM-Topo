#!/bin/sh

 echo .
 echo .
date
 echo .
 echo .

 echo .
 echo . 
 rm ./output/kya-s/*.*
 rm -r ./output/kya-s/garmin/*.*
 echo .
 echo .

cd ./input
# wget -N "https://download.geofabrik.de/russia-latest.osm.pbf"




echo =============================================================
echo .
echo .   cut out the desired data file OSM area
echo .
echo .

cd ../output


osmium extract -O -v --progress --strategy=simple --polygon=../poly/RU-KYA-S.poly \
   ../input/russia-latest.osm.pbf \
   -o kya-s.osm.pbf



 echo .
 echo .
date
 echo .
 echo .


 echo .   Osmosis 
 echo .
 echo . Adds fake admin_level tag for all place polygons.
 echo . This is needed for better search generation after creating borders with mkgmap
 


 ../tools/osmosis/bin/osmosis \
 --read-pbf-fast kya-s.osm.pbf \
 --tag-transform file=../transform_places.xml \
 --write-pbf file=kya-s2.osm.pbf \
 omitmetadata=true



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
   kya-s2.osm.pbf \
   ../elevation/RU-KYA-S.osm.pbf \
   -o topo.kya-s.osm.pbf


 echo .
 echo .
date
 echo .
 echo . 
 

echo =============================================================
echo .
echo .   splitting ready files
echo .


mkdir kya-s
mkdir kya-s/garmin

cd kya-s

 java -jar ../../tools/splitter/splitter.jar ../topo.kya-s.osm.pbf \
 --description="topo-kya-s" \
 --polygon-file=../../poly/RU-KYA-S.poly \
 --precomp-sea=../../input/sea-latest.zip \
 --keep-complete=true \
 --mapid=1015001 \
 --max-nodes=1000000 \
 --geonames-file=../../input/ru.zip \
 --output=pbf \
 --wanted-admin-level=8 \
 --output-dir=../kya-s

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
 --family-id=1015 \
 --family-name="topo-kya-s" \
 --series-name="topo-kya-s" \
 --description="topo-kya-s ($timestamp)" \
 --overview-mapname="topo-kya-s" \
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
mv gmapsupp.img topo-kya-s.img
cp topo-kya-s.img /mnt/nod/garmin

zip -r -0 -s=0 topo-kya-s-ms.zip ./topo-kya-s.gmap
cp topo-kya-s-ms.z* /mnt/nod/garmin/mapsource



