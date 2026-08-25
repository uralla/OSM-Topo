#!/bin/sh

 echo .
 echo .
date
 echo .
 echo .

 echo .
 echo . 
 rm ./output/zap-sib/*.*
 rm -r ./output/zap-sib/garmin/*.*
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


osmium extract -O -v --progress --strategy=simple --polygon=../poly/zap-sib.poly \
   ../input/russia-latest.osm.pbf \
   -o zap-sib.osm.pbf

# ../tools/osmosis/bin/osmosis \
# --read-pbf-fast file=../input/russia-latest.osm.pbf \
# --bounding-polygon file=../poly/zap-sib.poly completeWays=yes \
# --write-pbf file=zap-sib.osm.pbf \
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
 --read-pbf-fast zap-sib.osm.pbf \
 --tag-transform file=../transform_places.xml \
 --write-pbf file=zap-sib2.osm.pbf \
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
   zap-sib2.osm.pbf \
   ../elevation/zap-sib.osm.pbf \
   -o topo.zap-sib.osm.pbf

# ../tools/osmosis/bin/osmosis \
#    --read-pbf-fast zap-sib2.osm.pbf \
#    --read-pbf-fast ../elevation/zap-sib.osm.pbf \
#    --merge \
#    --write-pbf file=topo.zap-sib.osm.pbf omitmetadata=true

 echo .
 echo .
date
 echo .
 echo . 
 

echo =============================================================
echo .
echo .   splitting ready files
echo .


mkdir zap-sib
mkdir zap-sib/garmin

cd zap-sib

 java -jar ../../tools/splitter/splitter.jar ../topo.zap-sib.osm.pbf \
 --description="topo-zap-sib" \
 --polygon-file=../../poly/zap-sib.poly \
 --precomp-sea=../../input/sea-latest.zip \
 --keep-complete=true \
 --mapid=1011001 \
 --max-nodes=1000000 \
 --geonames-file=../../input/ru.zip \
 --output=pbf \
 --wanted-admin-level=8 \
 --output-dir=../zap-sib

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
--family-id=1011 \
--family-name="topo-zap-sib" \
--series-name="topo-zap-sib" \
--description="topo-zap-sib ($timestamp)" \
--overview-mapname="topo-zap-sib" \
--code-page=1251 \
--gmapi \
--bounds=../../input/bounds-latest.zip \
--precomp-sea=../../input/sea-latest.zip \
--output-dir=garmin \
--dem-dists=15000 \
--dem-poly=../../poly/zap-sib.poly \
--gmapsupp *.pbf ../../styles/uralla.typ

 echo .
 echo .
date
 echo .
 echo .

cd ./garmin
mv gmapsupp.img topo-zap-sib.img
cp topo-zap-sib.img /mnt/nod/garmin

zip -r -0 -s=0 topo-zap-sib-ms.zip ./topo-zap-sib.gmap
cp topo-zap-sib-ms.z* /mnt/nod/garmin/mapsource



