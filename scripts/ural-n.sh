#!/bin/sh

 echo .
 echo .
date
 echo .
 echo .

 echo .
 echo . 
 rm ./output/ural-n/*.*
 rm -r ./output/ural-n/garmin/*.*
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


osmium extract -O -v --progress --strategy=simple --polygon=../poly/ru_ural_polar.poly \
   ../input/russia-latest.osm.pbf \
   -o ural-n.osm.pbf


# ../tools/osmosis/bin/osmosis \
# --read-pbf-fast file=../input/russia-latest.osm.pbf \
# --bounding-polygon file=../poly/ru_ural_polar.poly completeWays=yes \
# --write-pbf file=ural-n.osm.pbf \
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
 --read-pbf-fast ural-n.osm.pbf \
 --tag-transform file=../transform_places.xml \
 --write-pbf file=ural-n2.osm.pbf \
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
   ural-n2.osm.pbf \
   ../elevation/ural_n.osm.pbf \
   -o topo.ural-n.osm.pbf


# ../tools/osmosis/bin/osmosis \
#    --read-pbf-fast ural-n2.osm.pbf \
#    --read-pbf-fast ../elevation/ural_n.osm.pbf \
#    --merge \
#    --write-pbf file=topo.ural-n.osm.pbf omitmetadata=true

 echo .
 echo .
date
 echo .
 echo . 
 

echo =============================================================
echo .
echo .   splitting ready files
echo .


mkdir ural-n
mkdir ural-n/garmin

cd ural-n

java -jar ../../tools/splitter/splitter.jar ../topo.ural-n.osm.pbf \
--description="Topo-Ural-N" \
--polygon-file=../../poly/ru_ural_polar.poly \
--precomp-sea=../../input/sea-latest.zip \
--keep-complete=true \
--mapid=1018001 \
--max-nodes=2000000 \
--geonames-file=../../input/ru.zip \
--output=pbf \
--wanted-admin-level=8 \
--output-dir=../ural-n

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
--family-id=1018 \
--family-name="Topo-Ural-N" \
--series-name="Topo-Ural-N" \
--description="Topo-Ural-N ($timestamp)" \
--overview-mapname="Topo-Ural-N" \
--code-page=1251 \
--gmapi \
--bounds=../../input/bounds-latest.zip \
--precomp-sea=../../input/sea-latest.zip \
--output-dir=garmin \
--dem-dists=9942 \
--dem-poly=../../poly/ru_ural_polar.poly \
--gmapsupp *.pbf ../../styles/uralla.typ

 echo .
 echo .
date
 echo .
 echo .

cd ./garmin
mv gmapsupp.img Topo-Ural-N.img
cp Topo-Ural-N.img /mnt/nod/garmin

zip -r -0 -s=0 Topo-Ural-N-ms.zip ./Topo-Ural-N.gmap
cp Topo-Ural-N-ms.z* /mnt/nod/garmin/mapsource
