#!/bin/sh

 echo .
 echo .
date
 echo .
 echo .

 echo .
 echo . 
 rm ./output/pri-kha-yev/*.*
 rm -r ./output/pri-kha-yev/garmin/*.*
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


osmium extract -O -v --progress --strategy=simple --polygon=../poly/RU-PRI_RU-KHA_RU-YEV.poly \
   ../input/russia-latest.osm.pbf \
   -o pri-kha-yev.osm.pbf


# ../tools/osmosis/bin/osmosis \
# --read-pbf-fast file=../input/russia-latest.osm.pbf \
# --bounding-polygon file=../poly/RU-PRI_RU-KHA_RU-YEV.poly completeWays=yes \
# --write-pbf file=pri-kha-yev.osm.pbf \
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
 --read-pbf-fast pri-kha-yev.osm.pbf \
 --tag-transform file=../transform_places.xml \
 --write-pbf file=pri-kha-yev2.osm.pbf \
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
   pri-kha-yev2.osm.pbf \
   ../elevation/pri-kha-yev.osm.pbf \
   -o topo.pri-kha-yev.osm.pbf



# ../tools/osmosis/bin/osmosis \
#    --read-pbf-fast pri-kha-yev2.osm.pbf \
#    --read-pbf-fast ../elevation/pri-kha-yev.osm.pbf \
#    --merge \
#    --write-pbf file=topo.pri-kha-yev.osm.pbf omitmetadata=true

 echo .
 echo .
date
 echo .
 echo . 
 

echo =============================================================
echo .
echo .   splitting ready files
echo .


mkdir pri-kha-yev
mkdir pri-kha-yev/garmin

cd pri-kha-yev


 java -jar ../../tools/splitter/splitter.jar ../topo.pri-kha-yev.osm.pbf \
 --description="Prim-Khabar-Yevr" \
 --polygon-file=../../poly/RU-PRI_RU-KHA_RU-YEV.poly \
 --precomp-sea=../../input/sea-latest.zip \
 --keep-complete=true \
 --mapid=1025001 \
 --max-nodes=1000000 \
 --geonames-file=../../input/ru.zip \
 --output=pbf \
 --wanted-admin-level=8 \
 --output-dir=../pri-kha-yev

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
 --family-id=1025 \
 --family-name="topo-pri-kha-yev" \
 --series-name="topo-pri-kha-yev" \
 --description="Prim-Khabar-Yevr ($timestamp)" \
 --overview-mapname="Prim-Khabar-Yevr" \
 --code-page=1251 \
 --gmapi \
 --bounds=../../input/bounds-latest.zip \
 --precomp-sea=../../input/sea-latest.zip \
 --output-dir=garmin \
 --dem-dists=15000 \
 --gmapsupp *.pbf ../../styles/uralla.typ

 echo .
 echo .
date
 echo .
 echo .

cd ./garmin
mv gmapsupp.img topo-pri-kha-yev.img
cp topo-pri-kha-yev.img /mnt/nod/garmin

zip -r -0 -s=0 topo-pri-kha-yev-ms.zip ./topo-pri-kha-yev.gmap
cp topo-pri-kha-yev-ms.z* /mnt/nod/garmin/mapsource



