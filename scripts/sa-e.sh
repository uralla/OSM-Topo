#!/bin/sh

 echo .
 echo .
date
 echo .
 echo .

 echo .
 echo . 
 rm ./output/sa-e/*.*
 rm -r ./output/sa-e/garmin/*.*
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


osmium extract -O -v --progress --strategy=simple --polygon=../poly/RU-SA-E.poly \
   ../input/russia-latest.osm.pbf \
   -o sa-e.osm.pbf



# ../tools/osmosis/bin/osmosis \
# --read-pbf-fast file=../input/russia-latest.osm.pbf \
# --bounding-polygon file=../poly/RU-SA-E.poly completeWays=yes \
# --write-pbf file=sa-e.osm.pbf \
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
 --read-pbf-fast sa-e.osm.pbf \
 --tag-transform file=../transform_places.xml \
 --write-pbf file=sa-e2.osm.pbf \
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
   sa-e2.osm.pbf \
   ../elevation/RU-SA-E.osm.pbf \
   -o topo.sa-e.osm.pbf



# ../tools/osmosis/bin/osmosis \
#    --read-pbf-fast sa-e2.osm.pbf \
#    --read-pbf-fast ../elevation/RU-SA-E.osm.pbf \
#    --merge \
#    --write-pbf file=topo.sa-e.osm.pbf omitmetadata=true

 echo .
 echo .
date
 echo .
 echo . 
 

echo =============================================================
echo .
echo .   splitting ready files
echo .


mkdir sa-e
mkdir sa-e/garmin

cd sa-e

 java -jar ../../tools/splitter/splitter.jar ../topo.sa-e.osm.pbf \
 --description="topo-sa-e" \
 --polygon-file=../../poly/RU-SA-E.poly \
 --precomp-sea=../../input/sea-latest.zip \
 --keep-complete=true \
 --mapid=1012001 \
 --max-nodes=1000000 \
 --geonames-file=../../input/ru.zip \
 --output=pbf \
 --wanted-admin-level=8 \
 --output-dir=../sa-e

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
 --family-id=1012 \
 --family-name="topo-sa-e" \
 --series-name="topo-sa-e" \
 --description="topo-sa-e ($timestamp)" \
 --overview-mapname="topo-sa-e" \
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
mv gmapsupp.img topo-sa-e.img
cp topo-sa-e.img /mnt/nod/garmin

zip -r -0 -s=0 topo-sa-e-ms.zip ./topo-sa-e.gmap
cp topo-sa-e-ms.z* /mnt/nod/garmin/mapsource



