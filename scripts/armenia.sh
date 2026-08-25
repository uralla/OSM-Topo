#!/bin/sh

 echo .
 echo .
date
 echo .
 echo .

 echo .
 echo . 
 rm ./output/armenia/*.*
 rm -r ./output/armenia/garmin/*.*
 echo .
 echo .

cd ./input
# wget -N "https://download.geofabrik.de/asia/armenia-latest.osm.pbf"



 echo .   Osmosis 
 echo .
 echo . Adds fake admin_level tag for all place polygons.
 echo . This is needed for better search generation after creating borders with mkgmap
 

cd ../output


osmium extract -O -v --progress --strategy=simple --polygon=../poly/armenia.poly \
   ../input/armenia-latest.osm.pbf \
   -o armenia-latest.osm.pbf


 ../tools/osmosis/bin/osmosis \
 --read-pbf-fast armenia-latest.osm.pbf \
 --tag-transform file=../transform_places.xml \
 --write-pbf file=armenia2.osm.pbf \
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
   armenia2.osm.pbf \
   ../elevation/armenia.osm.pbf \
   -o topo.armenia.osm.pbf


# ../tools/osmosis/bin/osmosis \
#    --read-pbf-fast armenia2.osm.pbf \
#    --read-pbf-fast ../elevation/armenia.osm.pbf \
#    --merge \
#    --write-pbf file=topo.armenia.osm.pbf omitmetadata=true

 echo .
 echo .
date
 echo .
 echo . 
 

echo =============================================================
echo .
echo .   splitting ready files
echo .


mkdir armenia
mkdir armenia/garmin

cd armenia

 java -jar ../../tools/splitter/splitter.jar ../topo.armenia.osm.pbf \
 --description="Armenia.OSM" \
 --precomp-sea=../../input/sea-latest.zip \
 --keep-complete=true \
 --mapid=10530001 \
 --ignore-osm-bounds=true \
 --max-nodes=2500000 \
 --output=pbf \
 --wanted-admin-level=8 \
 --output-dir=../armenia

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
 --family-id=1053 \
 --family-name="Armenia.OSM" \
 --series-name="Armenia.OSM" \
 --description="Armenia.OSM ($timestamp)" \
 --overview-mapname="Armenia.OSM" \
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
mv gmapsupp.img Armenia.OSM.img
cp Armenia.OSM.img /mnt/nod/garmin

zip -r -0 -s=0 Armenia.OSM-ms.zip ./Armenia.OSM.gmap
cp Armenia.OSM-ms.z* /mnt/nod/garmin/mapsource


