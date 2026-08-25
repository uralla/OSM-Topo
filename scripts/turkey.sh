#!/bin/sh

 echo .
 echo .
date
 echo .
 echo .

 echo .
 echo . 
 rm ./output/turkey/*.*
 rm -r ./output/turkey/garmin/*.*
 echo .
 echo .

cd ./input
# wget -N "https://download.geofabrik.de/europe/turkey-latest.osm.pbf"



 echo .   Osmosis 
 echo .
 echo . Adds fake admin_level tag for all place polygons.
 echo . This is needed for better search generation after creating borders with mkgmap
 

cd ../output

osmium extract -O -v --progress --strategy=simple --polygon=../poly/turkey.poly \
   ../input/turkey-latest.osm.pbf \
   -o turkey-latest.osm.pbf

 ../tools/osmosis/bin/osmosis \
 --read-pbf-fast turkey-latest.osm.pbf \
 --tag-transform file=../transform_places.xml \
 --write-pbf file=turkey2.osm.pbf \
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
   turkey2.osm.pbf \
   ../elevation/turkey.osm.pbf \
   -o topo.turkey.osm.pbf


# ../tools/osmosis/bin/osmosis \
#    --read-pbf-fast turkey2.osm.pbf \
#    --read-pbf-fast ../elevation/turkey.osm.pbf \
#    --merge \
#    --write-pbf file=topo.turkey.osm.pbf omitmetadata=true

 echo .
 echo .
date
 echo .
 echo . 
 

echo =============================================================
echo .
echo .   splitting ready files
echo .


mkdir turkey
mkdir turkey/garmin

cd turkey

 java -jar ../../tools/splitter/splitter.jar ../topo.turkey.osm.pbf \
 --description="Turkey.OSM" \
 --polygon-file=../../poly/turkey.poly \
 --precomp-sea=../../input/sea-latest.zip \
 --keep-complete=false \
 --mapid=10540001 \
 --max-nodes=800000 \
 --geonames-file=../../input/allCountries.zip \
 --output=pbf \
 --wanted-admin-level=8 \
 --output-dir=../turkey

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
 --family-id=1054 \
 --family-name="Turkey.OSM" \
 --series-name="Turkey.OSM" \
 --description="Turkey.OSM ($timestamp)" \
 --overview-mapname="Turkey.OSM" \
 --latin1 \
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
mv gmapsupp.img Turkey.OSM.img
cp Turkey.OSM.img /mnt/nod/garmin

zip -r -0 -s=0 Turkey.OSM-ms.zip ./Turkey.OSM.gmap
cp Turkey.OSM-ms.z* /mnt/nod/garmin/mapsource

