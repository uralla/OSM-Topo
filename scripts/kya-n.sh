#!/bin/sh

 echo .
 echo .
date
 echo .
 echo .

 echo .
 echo . 
 rm ./output/kya-n/*.*
 rm -r ./output/kya-n/garmin/*.*
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



osmium extract -O -v --progress --strategy=simple --polygon=../poly/RU-KYA-N.poly \
   ../input/russia-latest.osm.pbf \
   -o kya-n.osm.pbf






# ../tools/osmosis/bin/osmosis \
# --read-pbf-fast file=../input/russia-latest.osm.pbf \
# --bounding-polygon file=../poly/RU-KYA-N.poly completeWays=yes \
# --write-pbf file=kya-n.osm.pbf \
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
 --read-pbf-fast kya-n.osm.pbf \
 --tag-transform file=../transform_places.xml \
 --write-pbf file=kya-n2.osm.pbf \
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
   kya-n2.osm.pbf \
   ../elevation/RU-KYA-N.osm.pbf \
   -o topo.kya-n.osm.pbf



# ../tools/osmosis/bin/osmosis \
#    --read-pbf-fast kya-n2.osm.pbf \
#    --read-pbf-fast ../elevation/RU-KYA-N.osm.pbf \
#    --merge \
#    --write-pbf file=topo.kya-n.osm.pbf omitmetadata=true

 echo .
 echo .
date
 echo .
 echo . 
 

echo =============================================================
echo .
echo .   splitting ready files
echo .


mkdir kya-n
mkdir kya-n/garmin

cd kya-n

 java -jar ../../tools/splitter/splitter.jar ../topo.kya-n.osm.pbf \
 --description="topo-kya-n" \
 --polygon-file=../../poly/RU-KYA-N.poly \
 --precomp-sea=../../input/sea-latest.zip \
 --keep-complete=true \
 --mapid=1016001 \
 --max-nodes=1000000 \
 --geonames-file=../../input/ru.zip \
 --output=pbf \
 --wanted-admin-level=8 \
 --output-dir=../kya-n

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
 --family-id=1016 \
 --family-name="topo-kya-n" \
 --series-name="topo-kya-n" \
 --description="topo-kya-n ($timestamp)" \
 --overview-mapname="topo-kya-n" \
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
mv gmapsupp.img topo-kya-n.img
cp topo-kya-n.img /mnt/nod/garmin

zip -r -0 -s=0 topo-kya-n-ms.zip ./topo-kya-n.gmap
cp topo-kya-n-ms.z* /mnt/nod/garmin/mapsource



