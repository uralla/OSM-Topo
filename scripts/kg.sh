#!/bin/sh

 echo .
 echo .
date
 echo .
 echo .

 echo .
 echo . 
 rm ./output/kg/*.*
 rm -r ./output/kg/garmin/*.*
 echo .
 echo .

cd ./input
# wget -N "https://download.geofabrik.de/asia/kyrgyzstan-latest.osm.pbf"



 echo .   Osmosis 
 echo .
 echo . Adds fake admin_level tag for all place polygons.
 echo . This is needed for better search generation after creating borders with mkgmap
 

cd ../output

osmium extract -O -v --progress --strategy=simple --polygon=../poly/KG.poly \
   ../input/kyrgyzstan-latest.osm.pbf \
   -o kyrgyzstan-latest.osm.pbf
   

 ../tools/osmosis/bin/osmosis \
 --read-pbf-fast kyrgyzstan-latest.osm.pbf \
 --tag-transform file=../transform_places.xml \
 --write-pbf file=kg2.osm.pbf \
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
   kg2.osm.pbf \
   ../elevation/kg.osm.pbf \
   -o topo.kg.osm.pbf


# ../tools/osmosis/bin/osmosis \
#    --read-pbf-fast kg2.osm.pbf \
#    --read-pbf-fast ../elevation/kg.osm.pbf \
#    --merge \
#    --write-pbf file=topo.kg.osm.pbf omitmetadata=true

 echo .
 echo .
date
 echo .
 echo . 
 

echo =============================================================
echo .
echo .   splitting ready files
echo .


mkdir kg
mkdir kg/garmin

cd kg

 java -jar ../../tools/splitter/splitter.jar ../topo.kg.osm.pbf \
 --description="KG OSM-topo" \
 --precomp-sea=../../input/sea-latest.zip \
 --keep-complete=true \
 --mapid=10510001 \
 --max-nodes=2500000 \
 --geonames-file=../../input/allCountries.zip \
 --output=pbf \
 --wanted-admin-level=8 \
 --output-dir=../kg

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
 --family-id=1051 \
 --family-name="KG.OSM" \
 --series-name="KG.OSM" \
 --description="KG.OSM ($timestamp)" \
 --overview-mapname="KG.OSM" \
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
mv gmapsupp.img KG.OSM.img
cp KG.OSM.img /mnt/nod/garmin

zip -r -0 -s=0 KG.OSM-ms.zip ./KG.OSM.gmap
cp KG.OSM-ms.z* /mnt/nod/garmin/mapsource









