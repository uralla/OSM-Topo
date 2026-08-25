#!/bin/sh

find output/ -name "*.pbf" -type f -delete
find input/ -name "*.pbf" -type f -delete
find output/ -name "*.img" -type f -delete
find output/ -name "*.z*" -type f -delete
find output/ -name '*gmap' -type d -exec rm -rf {} +
#rm -rf /mnt/g/garmin/output/*/

#sudo cpupower frequency-set -d 800MHz -u 1100MHz


dir
cd ./input &&

#aria2c -V --allow-overwrite=true --conditional-get=true --max-overall-download-limit=9500K --file-allocation=none --max-concurrent-downloads=5 --input-file=globus.input

aria2c -V --allow-overwrite=true --conditional-get=true --max-overall-download-limit=9500K --file-allocation=none --max-concurrent-downloads=4 --input-file=all.input

mv belarus*.osm.pbf belarus-latest.osm.pbf
mv georgia*.osm.pbf georgia-latest.osm.pbf
mv turkey*.osm.pbf turkey-latest.osm.pbf
mv kazakhstan*.osm.pbf kazakhstan-latest.osm.pbf
mv kyrgyzstan*.osm.pbf kyrgyzstan-latest.osm.pbf
#mv volga-fed-district*.osm.pbf volga-fed-district-latest.osm.pbf
#mv south-fed-district*.osm.pbf south-fed-district-latest.osm.pbf
mv northwestern-fed-district*.osm.pbf northwestern-fed-district-latest.osm.pbf
#mv north-caucasus-fed-district*.osm.pbf north-caucasus-fed-district-latest.osm.pbf
#mv central-fed-district*.osm.pbf central-fed-district-latest.osm.pbf
mv crimean-fed-district*.osm.pbf crimean-fed-district-latest.osm.pbf
mv armenia*.osm.pbf armenia-latest.osm.pbf
mv mongolia*.osm.pbf mongolia-latest.osm.pbf
mv russia*.osm.pbf russia-latest.osm.pbf
#mv planet*.osm.pbf planet-latest.osm.pbf



# wget -N -c "https://download.geofabrik.de/europe/belarus-latest.osm.pbf" &&
# wget -N -c "https://download.geofabrik.de/europe/georgia-latest.osm.pbf" &&
# wget -N -c "https://download.geofabrik.de/europe/turkey-latest.osm.pbf" &&
# wget -N -c "https://download.geofabrik.de/asia/kazakhstan-latest.osm.pbf" &&
# wget -N -c "https://download.geofabrik.de/asia/kyrgyzstan-latest.osm.pbf" &&
# wget -N -c "https://download.geofabrik.de/russia/volga-fed-district-latest.osm.pbf" &&
# wget -N -c "https://download.geofabrik.de/russia/south-fed-district-latest.osm.pbf" &&
# wget -N -c "https://download.geofabrik.de/russia/northwestern-fed-district-latest.osm.pbf" &&
# wget -N -c "https://download.geofabrik.de/russia/north-caucasus-fed-district-latest.osm.pbf" &&
# wget -N -c "https://download.geofabrik.de/russia/central-fed-district-latest.osm.pbf" &&

cd .. &&

dir


./crimea.sh &&
#1021
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx



./belarus.sh &&
#1055
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx	



./north-caucasus-fed-district.sh &&
#1004
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx


	
./central-fed-district.sh &&
#1006
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx


	
./south-fed-district.sh &&
#1003
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx


	
./northwestern-fed-district.sh &&
#1007
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx



./volga-fed-district.sh &&
#1001
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx


./mongolia.sh &&
#1056
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	

./ural-s.sh &&
#1022
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
dir	
./ural-n.sh &&
#1018
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
dir

./ural-fd.sh &&
#1026
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx	
	


	
./irk.sh &&
#1010
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx


	
./zap-sib.sh &&
#1011
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx



./sa-e.sh &&
#1012
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx


	
./sa-w.sh &&
#1013
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx


	
./mag.sh &&
#1014
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx


	
./kya-s.sh &&
#1015
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx


	
./kya-n.sh &&
#1016
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx



./sak.sh &&
#1017
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx



./bu-zab-amu.sh &&
#1023
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx



./chu-kam.sh &&
#1024
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx



./pri-kha-yev.sh &&
#1025
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx	
	


./kg.sh &&
#1051
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
 
./kz.sh &&
#1050
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	
/georgia.sh &&
#1052
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

./armenia.sh &&
#1053
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	
./turkey.sh
#1054
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
	date
	echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx	
