#!/bin/sh

 echo .
 echo .
date
 echo .
 echo .

 echo .
 echo . 
 rm ./output/irk/*.*
 rm -r ./output/irk/garmin/*.*
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



osmium extract -O -v --progress --strategy=simple --polygon=../poly/RU-IRK.poly \
   ../input/russia-latest.osm.pbf \
   -o irk.osm.pbf


# ../tools/osmosis/bin/osmosis \
# --read-pbf-fast file=../input/russia-latest.osm.pbf \
# --bounding-polygon file=../poly/RU-IRK.poly completeWays=yes \
# --write-pbf file=irk.osm.pbf \
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
 --read-pbf-fast irk.osm.pbf \
 --tag-transform file=../transform_places.xml \
 --write-pbf file=irk2.osm.pbf \
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
   irk2.osm.pbf \
   ../elevation/RU-IRK.osm.pbf \
   -o topo.irk.osm.pbf


# ../tools/osmosis/bin/osmosis \
#    --read-pbf-fast irk2.osm.pbf \
#    --read-pbf-fast ../elevation/RU-IRK.osm.pbf \
#    --merge \
#    --write-pbf file=topo.irk.osm.pbf omitmetadata=true

 echo .
 echo .
date
 echo .
 echo . 
 

echo =============================================================
echo .
echo .   splitting ready files
echo .


mkdir irk
mkdir irk/garmin

cd irk

 java -jar ../../tools/splitter/splitter.jar ../topo.irk.osm.pbf \
 --description="topo-irk" \
 --polygon-file=../../poly/RU-IRK.poly \
 --precomp-sea=../../input/sea-latest.zip \
 --keep-complete=true \
 --mapid=1010001 \
 --max-nodes=2000000 \
 --geonames-file=../../input/ru.zip \
 --output=pbf \
 --wanted-admin-level=8 \
 --output-dir=../irk

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
 --family-id=1010 \
 --family-name="topo-irk" \
 --series-name="topo-irk" \
 --description="topo-irk ($timestamp)" \
 --overview-mapname="topo-irk" \
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
mv gmapsupp.img topo-irk.img
cp topo-irk.img /mnt/nod/garmin

zip -r -0 -s=0 topo-irk-ms.zip ./topo-irk.gmap
cp topo-irk-ms.z* /mnt/nod/garmin/mapsource
