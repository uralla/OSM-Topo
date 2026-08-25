#!/bin/sh

 echo .
 echo .
date
 echo .
 echo .

 echo .
 echo . 
 rm ./output/belarus/*.*
 rm -r ./output/belarus/garmin/*.*
 echo .
 echo .

cd ./input
# wget -N "https://download.geofabrik.de/europe/belarus-latest.osm.pbf"



 echo .   Osmosis 
 echo .
 echo . Adds fake admin_level tag for all place polygons.
 echo . This is needed for better search generation after creating borders with mkgmap
 

cd ../output


osmium extract -O -v --progress --strategy=simple --polygon=../poly/belarus.poly \
   ../input/belarus-latest.osm.pbf \
   -o belarus-latest.osm.pbf


 ../tools/osmosis/bin/osmosis \
 --read-pbf-fast belarus-latest.osm.pbf \
 --tag-transform file=../transform_places.xml \
 --write-pbf file=belarus2.osm.pbf \
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
	belarus2.osm.pbf \
	../elevation/belarus.pbf \
	-o topo.belarus.osm.pbf


# ../tools/osmosis/bin/osmosis \
#    --read-pbf-fast belarus2.osm.pbf \
#    --read-pbf-fast ../elevation/belarus.pbf \
#    --merge \
#    --write-pbf file=topo.belarus.osm.pbf omitmetadata=true

 echo .
 echo .
date
 echo .
 echo . 
 

echo =============================================================
echo .
echo .   splitting ready files
echo .


mkdir belarus
mkdir belarus/garmin

cd belarus

 java -jar ../../tools/splitter/splitter.jar ../topo.belarus.osm.pbf \
 --description="Belarus.OSM" \
 --precomp-sea=../../input/sea-latest.zip \
 --keep-complete=true \
 --mapid=10550001 \
 --max-nodes=1000000 \
 --geonames-file=../../input/allCountries.zip \
 --output=pbf \
 --wanted-admin-level=8 \
 --output-dir=../belarus

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
 --family-id=1055 \
 --family-name="Belarus.OSM" \
 --series-name="Belarus.OSM" \
 --description="Belarus.OSM ($timestamp)" \
 --overview-mapname="Belarus.OSM" \
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
mv gmapsupp.img Belarus.OSM.img
cp Belarus.OSM.img /mnt/nod/garmin

zip -r -0 -s=0 Belarus.OSM-ms.zip ./Belarus.OSM.gmap
cp Belarus.OSM-ms.z* /mnt/nod/garmin/mapsource


