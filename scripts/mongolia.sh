#!/bin/sh

 echo .
 echo .
date
 echo .
 echo .

 echo .
 echo . 
 rm ./output/mongolia/*.*
 rm -r ./output/mongolia/garmin/*.*
 echo .
 echo .

cd ./input
# wget -N "https://download.geofabrik.de/asia/mongolia-latest.osm.pbf"



 echo .   Osmosis 
 echo .
 echo . Adds fake admin_level tag for all place polygons.
 echo . This is needed for better search generation after creating borders with mkgmap
 

cd ../output



osmium extract -O -v --progress --strategy=smart --polygon=../poly/mongolia.poly \
   ../input/mongolia-latest.osm.pbf \
   -o mongolia-latest.osm.pbf


 ../tools/osmosis/bin/osmosis \
 --read-pbf-fast mongolia-latest.osm.pbf \
 --tag-transform file=../transform_places.xml \
 --write-pbf file=mongolia2.osm.pbf \
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



osmium merge -O -v --progress mongolia2.osm.pbf ../elevation/mongolia.osm.pbf -o topo.mongolia.osm.pbf


# ../tools/osmosis/bin/osmosis \
#    --read-pbf-fast mongolia2.osm.pbf \
#    --read-pbf-fast ../elevation/mongolia.osm.pbf \
#    --merge \
#    --write-pbf file=topo.mongolia.osm.pbf omitmetadata=true

 echo .
 echo .
date
 echo .
 echo . 
 

echo =============================================================
echo .
echo .   splitting ready files
echo .


mkdir mongolia
mkdir mongolia/garmin

cd mongolia

 java -jar ../../tools/splitter/splitter.jar ../topo.mongolia.osm.pbf \
 --description="Mongolia.OSM" \
 --polygon-file=../../poly/mongolia.poly \
 --precomp-sea=../../input/sea-latest.zip \
 --keep-complete=true \
 --mapid=10560001 \
 --max-nodes=2000000 \
 --geonames-file=../../input/allCountries.zip \
 --output=pbf \
 --wanted-admin-level=8 \
 --output-dir=../mongolia

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
 --family-id=1056 \
 --family-name="Mongolia.OSM" \
 --series-name="Mongolia.OSM" \
 --description="Mongolia.OSM ($timestamp)" \
 --overview-mapname="Mongolia.OSM" \
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
mv gmapsupp.img Mongolia.OSM.img
cp Mongolia.OSM.img /mnt/nod/garmin

zip -r -0 -s=0 Mongolia.OSM-ms.zip ./Mongolia.OSM.gmap
cp Mongolia.OSM-ms.z* /mnt/nod/garmin/mapsource


