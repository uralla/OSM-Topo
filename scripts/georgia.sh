#!/bin/sh

 echo .
 echo .
date
 echo .
 echo .

 echo .
 echo . 
 rm ./output/georgia/*.*
 rm -r ./output/georgia/garmin/*.*
 echo .
 echo .

cd ./input
# wget -N "https://download.geofabrik.de/europe/georgia-latest.osm.pbf"



 echo .   Osmosis 
 echo .
 echo . Adds fake admin_level tag for all place polygons.
 echo . This is needed for better search generation after creating borders with mkgmap
 

cd ../output


osmium extract -O -v --progress --strategy=simple --polygon=../poly/georgia.poly \
   ../input/georgia-latest.osm.pbf \
   -o georgia-latest.osm.pbf


 ../tools/osmosis/bin/osmosis \
 --read-pbf-fast georgia-latest.osm.pbf \
 --tag-transform file=../transform_places.xml \
 --write-pbf file=georgia2.osm.pbf \
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



osmium merge -O -v --progress georgia2.osm.pbf ../elevation/georgia.osm.pbf -o topo.georgia.osm.pbf


# ../tools/osmosis/bin/osmosis \
#    --read-pbf-fast georgia2.osm.pbf \
#    --read-pbf-fast ../elevation/georgia.osm.pbf \
#    --merge \
#    --write-pbf file=topo.georgia.osm.pbf omitmetadata=true

 echo .
 echo .
date
 echo .
 echo . 
 

echo =============================================================
echo .
echo .   splitting ready files
echo .


mkdir georgia
mkdir georgia/garmin

cd georgia

 java -jar ../../tools/splitter/splitter.jar ../topo.georgia.osm.pbf \
 --description="Georgia.OSM" \
 --precomp-sea=../../input/sea-latest.zip \
 --keep-complete=true \
 --mapid=10520001 \
 --max-nodes=2000000 \
 --output=pbf \
 --wanted-admin-level=8 \
 --output-dir=../georgia

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
 --family-id=1052 \
 --family-name="Georgia.OSM" \
 --series-name="Georgia.OSM" \
 --description="Georgia.OSM ($timestamp)" \
 --overview-mapname="Georgia.OSM" \
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
mv gmapsupp.img Georgia.OSM.img
cp Georgia.OSM.img /mnt/nod/garmin

zip -r -0 -s=0 Georgia.OSM-ms.zip ./Georgia.OSM.gmap
cp Georgia.OSM-ms.z* /mnt/nod/garmin/mapsource


