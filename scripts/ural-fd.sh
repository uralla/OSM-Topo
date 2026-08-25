#!/bin/sh

 echo .
 echo .
date
 echo .
 echo .

mkdir output/ural-fd
mkdir output/ural-fd/garmin

 echo .
 echo . 
 rm ./output/ural-fd/*.*
 rm -r ./output/ural-fd/garmin/*.*
 echo .
 echo .

cd ./input
#wget -N "https://download.geofabrik.de/russia/ural-fed-district-latest.osm.pbf"

#mv ural-fed-district*.osm.pbf ural-fed-district-latest.osm.pbf


cd ../output

osmium extract -O -v --progress --strategy=simple --polygon=../poly/ural-fed-district.poly \
   ../input/russia-latest.osm.pbf \
   -o ural-fed-district-latest.osm.pbf


 echo .   Osmosis 
 echo .
 echo . Adds fake admin_level tag for all place polygons.
 echo . This is needed for better search generation after creating borders with mkgmap
 


 ../tools/osmosis/bin/osmosis \
 --read-pbf-fast ural-fed-district-latest.osm.pbf \
 --tag-transform file=./transform_places.xml \
 --write-pbf file=ural-fed-district.osm.pbf \
 omitmetadata=true




			# ../tools/osmosis/bin/osmosis \
			# --read-pbf-fast ural-fed-district2.osm.pbf \
			# --lp --bb clipIncompleteEntities=true \
			# --tag-area-content file=tag-highway.xml \
			# --write-pbf file=ural-fed-district.tag1.osm.pbf \
			# omitmetadata=true
			
			
			# ../tools/osmosis/bin/osmosis \
			# --read-pbf-fast ural-fed-district.tag1.osm.pbf \
			# --lp --tag-area-content file=tag-poi-addr.xml \
			# --write-pbf file=ural-fed-district.tag2.osm.pbf \
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
   ural-fed-district.osm.pbf \
   ../elevation/ele_10_ru_ural-fed-district.osm.pbf \
   -o topo_ural-fed-district.osm.pbf


# ../tools/osmosis/bin/osmosis \
#    --read-pbf-fast ural-fed-district2.osm.pbf \
#    --read-pbf-fast ../elevation/ele_10_ru_ural-fed-district.osm.pbf \
#    --merge \
#    --write-pbf file=topo_ural-fed-district.osm.pbf omitmetadata=true

 echo .
 echo .
date
 echo .
 echo . 
 

echo =============================================================
echo .
echo .   splitting ready files
echo .


cd ural-fd

 java -jar ../../tools/splitter/splitter.jar ../topo_ural-fed-district.osm.pbf \
 --description="ural_fd" \
 --polygon-file=../../poly/ural-fed-district.poly \
 --precomp-sea=../../input/sea-latest.zip \
 --keep-complete=true \
 --mapid=10260001 \
 --max-nodes=2000000 \
 --geonames-file=../../input/ru.zip \
 --output=pbf \
 --wanted-admin-level=8 \
 --output-dir=../ural-fd

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
 --family-id=1026 \
 --family-name="Ural-fed-district" \
 --series-name="Ural-fed-district" \
 --description="Ural-fed-district ($timestamp)" \
 --overview-mapname="Ural-fed-district" \
 --country-name=RUS \
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
mv gmapsupp.img Ural-fed-district.img
cp Ural-fed-district.img /mnt/nod/garmin

zip -r -0 -s=0 Ural-fed-district-ms.zip ./Ural-fed-district.gmap
cp Ural-fed-district-ms.z* /mnt/nod/garmin/mapsource

