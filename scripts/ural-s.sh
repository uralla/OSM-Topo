#!/bin/sh

 echo .
 echo .
date
 echo .
 echo .

 echo .
 echo . 
 rm ./output/ural-s/*.*
 rm -r ./output/ural-s/garmin/*.*
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


osmium extract -O -v --progress --strategy=simple --polygon=../poly/ru_ural.poly \
   ../input/russia-latest.osm.pbf \
   -o ural.osm.pbf



# ../tools/osmosis/bin/osmosis \
# --read-pbf-fast file=../input/russia-latest.osm.pbf \
# --bounding-polygon file=../poly/ru_ural.poly completeWays=yes \
# --write-pbf file=ural.osm.pbf omitmetadata=true granularity=1000 granularity=1000

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
 --read-pbf-fast ural.osm.pbf \
 --tag-transform file=../transform_places.xml \
 --write-pbf file=ural2.osm.pbf omitmetadata=true granularity=1000 granularity=1000


			# ../tools/osmosis/bin/osmosis \
			# --read-pbf-fast crimean-fed-district2.osm.pbf \
			# --lp --bb clipIncompleteEntities=true \
			# --tag-area-content file=tag-highway.xml \
			# --write-pbf file=crimean-fed-district.tag1.osm.pbf \
			# omitmetadata=true granularity=1000 granularity=1000
			
			
			# ../tools/osmosis/bin/osmosis \
			# --read-pbf-fast crimean-fed-district.tag1.osm.pbf \
			# --lp --tag-area-content file=tag-poi-addr.xml \
			# --write-pbf file=crimean-fed-district.tag2.osm.pbf \
			# omitmetadata=true granularity=1000 granularity=1000

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
   ural2.osm.pbf \
   ../elevation/ural.osm.pbf \
   -o topo.ural.osm.pbf

# ../tools/osmosis/bin/osmosis \
#    --read-pbf-fast ural2.osm.pbf \
#    --read-pbf-fast ../elevation/ural.osm.pbf \
#    --merge \
#    --write-pbf file=topo.ural.osm.pbf omitmetadata=true granularity=1000 granularity=1000

 echo .
 echo .
date
 echo .
 echo . 
 

echo =============================================================
echo .
echo .   splitting ready files
echo .


mkdir ural-s
mkdir ural-s/garmin

cd ural-s

java -jar ../../tools/splitter/splitter.jar ../topo.ural.osm.pbf \
--description="Topo-Ural-S" \
--polygon-file=../../poly/ru_ural.poly \
--precomp-sea=../../input/sea-latest.zip \
--keep-complete=true \
--mapid=10220001 \
--max-nodes=500000 \
--output=pbf \
--wanted-admin-level=8 \
--output-dir=../ural-s



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


 

java -jar ../../tools/mkgmap/mkgmap.jar -c ../../styles/uralla.args \
--style-file=../../styles/uralla \
--family-id=1022 \
--family-name="Topo-Ural-S" \
--series-name="Topo-Ural-S" \
--description="Topo-Ural-S ($timestamp)" \
--overview-mapname="Topo-Ural-S" \
--code-page=1251 \
--gmapi \
--bounds=../../input/bounds-latest.zip \
--precomp-sea=../../input/sea-latest.zip \
--output-dir=garmin \
--dem-poly=../../poly/ru_ural.poly \
--gmapsupp *.pbf ../../styles/uralla.typ
 

 echo .
 echo .
date
 echo .
 echo .



cd ./garmin
mv gmapsupp.img Topo-Ural-S.img
cp Topo-Ural-S.img /mnt/nod/garmin

zip -r -s990 Topo-Ural-S-ms.zip ./Topo-Ural-S.gmap
cp Topo-Ural-S-ms.z* /mnt/nod/garmin/mapsource
