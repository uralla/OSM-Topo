#!/bin/sh

 echo .
 echo .
date
 echo .
 echo .

 echo .
 echo . 
 rm ./output/kz/*.*
 rm -r ./output/kz/garmin/*.*
 echo .
 echo .

cd ./input
# wget -N "https://download.geofabrik.de/asia/kazakhstan-latest.osm.pbf"



 echo .   Osmosis 
 echo .
 echo . Adds fake admin_level tag for all place polygons.
 echo . This is needed for better search generation after creating borders with mkgmap
 

cd ../output

osmium extract -O -v --progress --strategy=simple --polygon=../poly/KZ.poly \
   ../input/kazakhstan-latest.osm.pbf \
   -o kazakhstan-latest.osm.pbf


 ../tools/osmosis/bin/osmosis \
 --read-pbf-fast kazakhstan-latest.osm.pbf \
 --tag-transform file=../transform_places.xml \
 --write-pbf file=kz2.osm.pbf \
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
   kz2.osm.pbf \
   ../elevation/kz.osm.pbf \
   -o topo.kz.osm.pbf


# ../tools/osmosis/bin/osmosis \
#    --read-pbf-fast kz2.osm.pbf \
#    --read-pbf-fast ../elevation/kz.osm.pbf \
#    --merge \
#    --write-pbf file=topo.kz.osm.pbf omitmetadata=true

 echo .
 echo .
date
 echo .
 echo . 
 

echo =============================================================
echo .
echo .   splitting ready files
echo .


mkdir kz
mkdir kz/garmin

cd kz

 java -jar ../../tools/splitter/splitter.jar ../topo.kz.osm.pbf \
 --description="KZ OSM-topo" \
 --precomp-sea=../../input/sea-latest.zip \
 --keep-complete=true \
 --mapid=10500001 \
 --max-nodes=500000 \
 --geonames-file=../../input/allCountries.zip \
 --output=pbf \
 --wanted-admin-level=8 \
 --output-dir=../kz

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
 --family-id=1050 \
 --family-name="KZ.OSM" \
 --series-name="KZ.OSM" \
 --description="KZ.OSM ($timestamp)" \
 --overview-mapname="KZ.OSM" \
 --code-page=1251 \
 --gmapi \
 --bounds=../../input/bounds-latest.zip \
 --precomp-sea=../../input/sea-latest.zip \
 --output-dir=garmin \
 --dem-dists=15000 \
 --gmapsupp *.pbf ../../styles/uralla.typ

 echo .
 echo .
date
 echo .
 echo .


cd ./garmin
mv gmapsupp.img KZ.OSM.img
cp KZ.OSM.img /mnt/nod/garmin

zip -r -0 -s=0 KZ.OSM-ms.zip ./KZ.OSM.gmap
cp KZ.OSM-ms.z* /mnt/nod/garmin/mapsource











