#!/bin/sh

 echo .
 echo .
date
 echo .
 echo .

 echo .
 echo . 
 rm ./output/bu-zab-amu/*.*
 rm -r ./output/bu-zab-amu/garmin/*.*
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



osmium extract -O -v --progress --strategy=simple --polygon=../poly/RU-BU_RU-ZAB_RU-AMU.poly \
   ../input/russia-latest.osm.pbf \
   -o bu-zab-amu.osm.pbf



# ../tools/osmosis/bin/osmosis \
# --read-pbf-fast file=../input/russia-latest.osm.pbf \
# --bounding-polygon file=../poly/RU-BU_RU-ZAB_RU-AMU.poly completeWays=yes \
# --write-pbf file=bu-zab-amu.osm.pbf \
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
 --read-pbf-fast bu-zab-amu.osm.pbf \
 --tag-transform file=../transform_places.xml \
 --write-pbf file=bu-zab-amu2.osm.pbf \
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
   bu-zab-amu2.osm.pbf \
   ../elevation/RU-BU_RU-ZAB_RU-AMU.osm.pbf \
   -o topo.bu-zab-amu.osm.pbf


# ../tools/osmosis/bin/osmosis \
#    --read-pbf-fast bu-zab-amu2.osm.pbf \
#    --read-pbf-fast ../elevation/RU-BU_RU-ZAB_RU-AMU.osm.pbf \
#    --merge \
#    --write-pbf file=topo.bu-zab-amu.osm.pbf omitmetadata=true

 echo .
 echo .
date
 echo .
 echo . 
 

echo =============================================================
echo .
echo .   splitting ready files
echo .


mkdir bu-zab-amu
mkdir bu-zab-amu/garmin

cd bu-zab-amu

 java -jar ../../tools/splitter/splitter.jar ../topo.bu-zab-amu.osm.pbf \
 --max-threads=8 \
 --description="topo-bu-zab-amu" \
 --polygon-file=../../poly/RU-BU_RU-ZAB_RU-AMU.poly \
 --precomp-sea=../../input/sea-latest.zip \
 --keep-complete=true \
 --mapid=1023001 \
 --max-nodes=1000000 \
 --geonames-file=../../input/ru.zip \
 --output=pbf \
 --wanted-admin-level=8 \
 --output-dir=../bu-zab-amu

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


 

 java -jar ../../tools/mkgmap/mkgmap.jar  -c ../../styles/uralla-no-dem.args \
 --style-file=../../styles/uralla \
 --family-id=1023 \
 --family-name="topo-bu-zab-amu" \
 --series-name="topo-bu-zab-amu" \
 --description="topo-bu-zab-amu ($timestamp)" \
 --overview-mapname="topo-bu-zab-amu" \
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
mv gmapsupp.img topo-bu-zab-amu.img
cp topo-bu-zab-amu.img /mnt/nod/garmin

zip -r -0 -s=0 topo-bu-zab-amu-ms.zip ./topo-bu-zab-amu.gmap
cp topo-bu-zab-amu-ms.z* /mnt/nod/garmin/mapsource



