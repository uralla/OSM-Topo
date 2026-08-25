#!/bin/sh

 echo .
 echo .
date
 echo .
 echo .

 echo .
 echo . 
 rm ./output/chu-kam/*.*
 rm -r ./output/chu-kam/garmin/*.*
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


osmium extract -O -v --progress --strategy=simple --polygon=../poly/RU-CHU_RU-KAM.poly \
   ../input/russia-latest.osm.pbf \
   -o chu-kam.osm.pbf

# ../tools/osmosis/bin/osmosis \
# --read-pbf-fast file=../input/russia-latest.osm.pbf \
# --bounding-polygon file=../poly/RU-CHU_RU-KAM.poly completeWays=yes \
# --write-pbf file=chu-kam.osm.pbf \
# omitmetadata=true

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
 --read-pbf-fast chu-kam.osm.pbf \
 --tag-transform file=../transform_places.xml \
 --write-pbf file=chu-kam2.osm.pbf \
 omitmetadata=true


			# ../tools/osmosis/bin/osmosis \
			# --read-pbf-fast crimean-fed-district2.osm.pbf \
			# --lp --bb clipIncompleteEntities=true \
			# --tag-area-content file=tag-highway.xml \
			# --write-pbf file=crimean-fed-district.tag1.osm.pbf \
			# omitmetadata=true
			
			
			# ../tools/osmosis/bin/osmosis \
			# --read-pbf-fast crimean-fed-district.tag1.osm.pbf \
			# --lp --tag-area-content file=tag-poi-addr.xml \
			# --write-pbf file=crimean-fed-district.tag2.osm.pbf \
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
   chu-kam2.osm.pbf \
   ../elevation/RU-CHU_RU-KAM.osm.pbf \
   -o topo.chu-kam.osm.pbf



# ../tools/osmosis/bin/osmosis \
#    --read-pbf-fast chu-kam2.osm.pbf \
#    --read-pbf-fast ../elevation/RU-CHU_RU-KAM.osm.pbf \
#    --merge \
#    --write-pbf file=topo.chu-kam.osm.pbf omitmetadata=true

 echo .
 echo .
date
 echo .
 echo . 
 

echo =============================================================
echo .
echo .   splitting ready files
echo .


mkdir chu-kam
mkdir chu-kam/garmin

cd chu-kam

 java -jar ../../tools/splitter/splitter.jar ../topo.chu-kam.osm.pbf \
 --description="topo-chu-kam" \
 --polygon-file=../../poly/RU-CHU_RU-KAM.poly \
 --precomp-sea=../../input/sea-latest.zip \
 --keep-complete=true \
 --mapid=1024001 \
 --max-nodes=2000000\
 --geonames-file=../../input/ru.zip \
 --output=pbf \
 --wanted-admin-level=8 \
 --output-dir=../chu-kam

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
 --family-id=1024 \
 --family-name="topo-chu-kam" \
 --series-name="topo-chu-kam" \
 --description="topo-chu-kam ($timestamp)" \
 --overview-mapname="topo-chu-kam" \
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
mv gmapsupp.img topo-chu-kam.img
cp topo-chu-kam.img /mnt/nod/garmin

zip -r -0 -s=0 topo-chu-kam-ms.zip ./topo-chu-kam.gmap
cp topo-chu-kam-ms.z* /mnt/nod/garmin/mapsource



