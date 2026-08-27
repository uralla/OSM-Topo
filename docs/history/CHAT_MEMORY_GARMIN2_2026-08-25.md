# Garmin OSM Topo — рабочая память чата Garmin2

Дата фиксации: 2026-08-25

> Это консолидированная рабочая память текущего чата: решения, ограничения, принципы, найденные проблемы, согласованные направления и важные детали проекта. Это не скрытая цепочка рассуждений и не дословный лог переписки.

## 1. Общая цель проекта

Проект — пользовательский Garmin OSM Topo стиль и сборочная система для туристических карт.

Главный приоритет карты:
1. лесной туризм / пешие походы;
2. велотуризм;
3. всё остальное.

Городские велодорожки должны оставаться видимыми и маршрутизируемыми. Карты обычно используются по одной, хотя несколько могут быть одновременно включены. Границы подбираются так, чтобы пользовательская зона интереса целиком находилась внутри одной карты и чтобы на стыках не возникало лишних артефактов.

Скорость сборки вторична по отношению к качеству и стабильности. Текущий рабочий компьютер старый, намеренно работает с пониженной частотой, полная сборка может занимать около суток.

## 2. Главный принцип работы над проектом

До полного завершения аудита НЕ вносить частичные изменения в main.

Сначала:
- полный аудит стиля;
- TYP;
- routing;
- LOD/resolution;
- scripts/build pipeline;
- входных данных;
- границ;
- address/name processing;
- packaging;
- кроссплатформенности.

После этого — одна согласованная интеграционная ветка и связанный набор изменений.

## 3. Репозиторий и рабочий процесс

Репозиторий: `uralla/OSM-Topo`.

В GitHub уже находятся:
- `styles/`;
- `scripts/` со всеми актуальными скриптами рабочей сборки;
- `poly/` с границами карт;
- `scripts/transform_places.xml`;
- review/audit документы;
- исходник TYP `styles/uralla.txt`;
- бинарный `styles/uralla.typ`.

План реализации после аудита:
- не писать сразу в main;
- создать отдельную интеграционную ветку;
- писать файлы напрямую в GitHub;
- пользователь на Ubuntu/MacBook получает изменения обычным `git pull`/переключением ветки.

Ручное копирование больших кусков текста из чата в файлы не планируется.

## 4. Карты и scheduler

Сейчас в `scripts` полный набор реально генерируемых карт — 27 карт.

В будущем список будет расширяться.

Новая build-system должна заменить 27 отдельных больших shell-скриптов на:
- один build-manager;
- единый map manifest/config;
- этапы pipeline;
- scheduler;
- state/history database.

Каждая карта должна иметь минимум:
- id;
- product name;
- source;
- polygon;
- elevation dataset;
- DEM profile;
- family-id;
- map-id range/start;
- language profile;
- cadence;
- priority;
- publish names;
- временные legacy overrides splitter/mkgmap.

### Периодичность

Идея одобрена:
- российские/важные карты — примерно weekly;
- менее важные и ресурсоёмкие, например Turkey — monthly или реже;
- возможны quarterly/manual.

Лучше считать период от `last_success`, а не по жёстким календарным датам.

Пример:
- `cadence_days=7`;
- `cadence_days=30`;
- `cadence_days=90`.

Если сборка просрочена и очередная попытка упала, `last_success` не меняется, поэтому карта остаётся due.

### Очередь

Главный порядок очереди:
1. PRIORITY;
2. степень просрочки (overdue).

Это решение пользователю особенно понравилось.

Дополнительные критерии можно использовать только после первых двух:
- общая source-family;
- историческая длительность сборки;
- удобство повторного использования уже загруженного source.

Priority никогда не должен быть перепрыгнут оптимизатором очереди.

### Ежедневный cron

Предпочтительная схема:
- cron запускает build-manager раз в день;
- build-manager сам проверяет, работает ли предыдущий запуск;
- если работает — новый запуск сразу завершается без ошибки;
- если машина свободна — строится очередь due-карт.

Cron не должен знать список карт или их расписание.

Пример команд будущего менеджера:
- `build-manager run --due`;
- `build-manager --map ural-s --force`;
- `build-manager --weekly`;
- `build-manager --all`;
- `build-manager --status`;
- `build-manager doctor`;
- `build-manager bootstrap`.

## 5. Lock и защита от параллельных сборок

Лучше не зависеть от внешнего binary `flock`, чтобы одинаково работать на Linux/macOS.

Если manager будет на Python, использовать `fcntl.flock()`.

Если global lock занят:
- предыдущий build всё ещё идёт;
- новый cron-run завершает работу с exit 0.

Если в state карта числится BUILDING, но lock свободен:
- предыдущий процесс оборвался;
- состояние можно признать interrupted/failed;
- карта снова попадёт в очередь.

## 6. Состояния и resume

Каждый этап может иметь:
- PENDING;
- RUNNING;
- SUCCESS;
- FAILED.

Планируемые этапы:
1. source download/update;
2. extract;
3. name/address preprocessing;
4. spatial preprocessing;
5. elevation merge;
6. splitter;
7. mkgmap tile compile;
8. Garmin packaging;
9. GMAPI packaging;
10. ZIP GMAPI;
11. validation;
12. publish.

Resume должен быть безопасным: этап можно переиспользовать только если его input/config/tool signatures не изменились.

Если изменился source PBF, style commit, config или версия нужного инструмента — зависимые этапы инвалидируются.

## 7. Статистика сборок

Каждая сборка должна собирать историю, чтобы позднее оптимизировать pipeline на реальных данных, а не на старых ручных настройках.

Хранение — предпочтительно SQLite, например `state/builds.sqlite`.

Хранить по каждой карте и стадии:
- start/end;
- wall time;
- CPU time;
- peak process RAM;
- peak process tree RAM;
- minimum available system RAM;
- peak swap;
- major page faults;
- disk read/write bytes;
- input size;
- output size;
- exit code;
- warning count;
- tile count;
- source timestamp;
- git commit;
- tool versions;
- hostname;
- OS/arch;
- CPU model;
- total RAM/swap.

Для splitter дополнительно:
- strategy;
- keep-complete;
- max-nodes;
- max-threads;
- tile count.

Для mkgmap:
- max-jobs;
- Xmx;
- dem-dists;
- gmappsupp size;
- GMAPI size.

Историю не перетирать: она должна позволять сравнивать разные версии, max-nodes, max-jobs и влияние swap.

В будущем scheduler сможет показывать median build time и ETA очереди.

## 8. Статистика будущего spatial-preprocessor

Нужно собирать и семантическую статистику алгоритмов, например:
- км дорог, получивших penalty из-за clearcut/logging;
- км дорог, идущих вдоль power line;
- км дорог вдоль pipeline;
- число generalized railway pairs;
- число generalized dual-carriageway pairs;
- urban POI demoted;
- rural/wilderness POI promoted;
- распределение `poi_importance`.

Это нужно, чтобы быстро ловить слишком агрессивные алгоритмы.

## 9. Cross-platform bootstrap / doctor

Цель: после clone проект должен сам объяснить и подготовить окружение.

Поддержка минимум:
- Ubuntu/Linux;
- macOS (Apple Silicon).

System dependencies проверяются и при необходимости устанавливаются штатным package manager:
- apt на Ubuntu;
- Homebrew на macOS.

Нужно проверять как минимум:
- Java;
- osmium-tool;
- Osmosis;
- aria2;
- zip;
- Python;
- будущие библиотеки spatial engine.

mkgmap и splitter лучше не ставить глобально как случайный latest, а держать pinned/project-managed versions, например в `.tools/`.

`doctor` должен только проверять и ясно показывать, чего не хватает.

`bootstrap` — устанавливать/готовить недостающие зависимости.

Сам Homebrew без подтверждения автоматически не устанавливать.

## 10. Большие DEM/elevation данные

DEM и elevation datasets очень большие и уже заранее копируются/резервируются пользователем. Для синхронизации используется Syncthing.

Build-manager НЕ должен сам пытаться скачивать сотни гигабайт DEM/elevation.

Нужен внешний data root, например:
- Linux: `URALLA_DATA=/...`;
- Mac: `URALLA_DATA=/Volumes/...`.

Map config должен ссылаться на dataset относительно data root.

Build-manager проверяет наличие нужных DEM/elevation файлов и даёт ясную ошибку, если dataset не синхронизирован.

Полный SHA огромных файлов не считать на каждом build. Можно иметь отдельную `verify-data` команду.

## 11. Syncthing и публикация

У пользователя уже есть отдельная папка готовых файлов.

Текущая схема:
- script генерирует `gmapsupp.img`;
- переименовывает в имя карты;
- копирует в publish folder;
- эта папка через Syncthing синхронизируется с сервером загрузки карт.

Эту архитектуру сохранить.

Build-manager ничего не должен знать о сервере/SSH — его контракт заканчивается publish directory.

Не синхронизировать через Syncthing:
- work;
- staging;
- splitter temp;
- другие промежуточные гигантские файлы.

Синхронизировать можно:
- большие static datasets;
- published output.

### Безопасная публикация

Нельзя удалять рабочий старый релиз заранее.

Новый output:
- собирается в staging;
- валидируется;
- копируется во временное имя в publish filesystem;
- после успешного копирования атомарно переименовывается в финальное имя.

Успешной сборка считается только после успешного publish.

Рядом полезно писать metadata JSON:
- build time;
- source timestamp;
- host;
- git commit;
- mkgmap version;
- file size;
- checksum.

Это защитит и от гонок между рабочим Ubuntu и домашним Mac.

## 12. Формат опубликованных файлов

### IMG

Garmin `.img` дополнительно ZIP-сжимать не нужно.

Публиковать напрямую:
- `MapName.img`.

### GMAPI / BaseCamp / MapSource

GMAPI нужен одним ZIP только ради удобства скачивания.

Использовать один ZIP без split volumes и без лишней компрессии:
- `zip -r -0 MapName-ms.zip MapName.gmap`.

Split ZIP полностью признан историческим артефактом времён Яндекс.Диска с ограничением ~1 GB на файл.

Удалить в новой системе:
- `-s990`;
- `-s=0` как split-механику;
- `.z01/.z02/...` workflow.

GMAPI archive validation:
- `zip -T`;
- наличие ожидаемого `.gmap`.

## 13. Источники и скачивание

Текущий `all.sh` сначала удаляет PBF, потом скачивает новые — это в новой системе не сохранять.

Новая схема:
- сохранить последний исправный source;
- скачивать новый в `.part`;
- проверить;
- atomically replace.

Если загрузка оборвалась, старый source остаётся пригодным.

Dependency planner должен скачивать только те source, которые нужны due-картам.

Например несколько российских карт используют один `russia-latest.osm.pbf`, который скачивается один раз.

## 14. `osmium extract --strategy=simple`

Очень важное историческое решение пользователя.

`simple` использовался сознательно после того, как более сложные способы extraction создавали проблемы. Точная историческая причина забыта и могла смешиваться со старыми downstream bugs.

Поэтому:
- НЕ объявлять `simple` ошибкой;
- НЕ заменять его автоматически на smart/complete;
- current simple pipeline — baseline A.

У пользователя важны чистые границы продукта: более «полные» extraction strategies могут притягивать больше внешних ways/relations и увеличивать артефакты на границе, особенно когда одновременно включены соседние карты.

Будущий принцип:
- PRODUCT BOUNDARY — жёсткая граница конечной Garmin-карты;
- ANALYSIS BOUNDARY — временная расширенная область только для preprocessing/context.

Spatial processor может смотреть за границу, но конечная геометрия обязана вернуться строго к product polygon.

Для relation context возможна схема:
- посмотреть внешние members;
- перенести нужную семантику на внутренние objects/internal tags;
- удалить внешнюю geometry перед продуктовой сборкой.

## 15. Northwestern / Калининград

Текущий `northwestern-fed-district.sh` использует готовый `northwestern-fed-district-latest.osm.pbf` как legacy workaround, потому что при попытке собирать из `russia-latest` карта когда-то не проходила дальше splitter.

Пользователь подозревал multipart `.poly` из-за Калининградской области.

После добавления `poly/` проверено:
- `northwestern-fed-district.poly` содержит два внешних контура;
- Калининград — второй outer ring;
- это НЕ hole.

Целевая схема остаётся:
- `russia-latest.osm.pbf`;
- `osmium extract --strategy=simple` по multipart poly;
- preprocessing;
- splitter;
- mkgmap.

Калининград пока НЕ выделять в отдельную карту.

План controlled test:
A. current working workaround;
B. desired `russia-latest -> simple multipart poly -> splitter polygon`;
C. multipart extract, но splitter без polygon-file;
D. при необходимости два extract + merge.

Если современный pipeline работает — Northwestern остаётся одной картой.

## 16. Poly files

`poly/` теперь хранится в Git — это правильно, потому что product boundaries маленькие и являются частью definition продукта.

Не каждый `.poly` автоматически означает активную карту.

Источник истины — map manifest.

В `poly/` есть также старые/reference/test варианты, например:
- `northwestern-fed-district2.poly`;
- `mongolia2.poly`;
- `far-eastern-fed-district.poly`;
- `siberian-fed-district.poly`;
- `south-ural.poly`;
- `ural-odd.poly`;
- `test.poly`.

Их не удалять вслепую.

Future `doctor` должен валидировать active polygons:
- existence;
- syntax;
- outer rings;
- holes;
- END sections;
- plausible coordinates;
- empty/self-intersection obvious issues.

## 17. `transform_places.xml`

Файл теперь находится в `scripts/transform_places.xml`.

Текущая логика:
- city/town -> fake admin_level=7;
- village/hamlet -> fake admin_level=10;
- isolated_dwelling/allotments -> fake admin_level=11;
- добавляет boundary=administrative и type=boundary;
- copy-all сохраняет исходные теги.

Цель — улучшить address/location inference в mkgmap.

Нужно проверить:
- действительно ли transformation ограничивается polygon/area objects;
- не получают ли nodes бессмысленные boundary tags;
- не перезаписывается ли настоящая boundary/admin семантика.

Будущий target:
- применять только к area-capable place objects;
- не перезаписывать реальные admin/boundary objects;
- возможно добавить internal marker `uralla:fake_place_boundary=yes`, чтобы синтетическая boundary не попадала в видимый boundary rendering.

Пути к XML в старых скриптах различаются (`../transform_places.xml`, `./transform_places.xml`) — новый manager должен использовать один canonical path от project root.

## 18. Name/language architecture

### Русские сокращения

Пользователь хочет глобальные сокращения, не только для highway.

Исходный OSM `name` не уничтожать.

Garmin primary/display label может быть сокращён, полный оригинал/сконструированный label — secondary label, если отличается.

Согласованный безопасный словарь включает:
- улица -> ул.;
- переулок -> пер.;
- проспект -> пр-т;
- проезд -> пр-д;
- разъезд -> раз.;
- тракт -> тр-т;
- площадь -> пл.;
- имени -> им.;
- бульвар -> бл-р;
- шоссе -> ш.;
- дорога -> дор.;
- тупик -> туп.;
- микрорайон -> мкр.;
- аллея -> алл.;
- линия -> лин.;
- набережная -> наб.;
- Восточный -> Вост.;
- Западный -> Зап.;
- Южный -> Юж.;
- Северный -> Сев.;
- совхоз -> свх.

Пользователь предложил целевой пример:
- `улица 50-летия Всесоюзного Ленинского Коммунистического Союза Молодёжи`
- display -> `ул. 50-лет ВЛКСМ`.

Это принято как хороший целевой стиль.

Сильные сокращения/аббревиатуры делать только по whitelist, не общим «умным» урезанием всего текста.

Пример:
- `Совхоз имени XXIII съезда КПСС Северный`
- -> `Свх. им. XXIII съезда КПСС Сев.`.

### Garmin labels

mkgmap поддерживает до 4 labels (`mkgmap:label:1..4`).

Обычно отображается первый; на некоторых устройствах второй label дороги может участвовать в routing instruction; labels используются и для поиска.

`mkgmap:street` отдельно используется для house number search, поэтому display abbreviation не должна ломать адресный поиск.

### Зарубежные карты

Язык отображения и code page — разные задачи.

`--latin1` не выбирает английские названия, а только меняет кодировку.

Новая система должна иметь language profile.

Для international-профиля базовая идея:
1. `name:en`;
2. `int_name`;
3. уже имеющееся латинское/транслитерированное имя;
4. автоматическая transliteration;
5. `name:ru`;
6. исходный `name` как последний fallback.

Для стран с уже латинским local name, например Turkey, отдельный профиль:
- English при наличии;
- readable local Latin;
- int_name;
- ASCII/transliteration fallback.

Исходный OSM `name` не мутировать; preprocessing создаёт internal display-name.

CP1251 может остаться полезной даже для international maps, если primary labels привести к ASCII/Latin, потому что она сохраняет возможность русского fallback. Решение по code page — после тестов.

Текущие `--latin1` у Georgia/Armenia/Turkey/Mongolia — считать старым практическим способом решать проблему читаемости, но не окончательной архитектурой.

## 19. TYP и Family ID

Текущий `styles/uralla.txt`:
- ProductCode=1;
- FID=1002;
- CP1251.

В бинарном `.typ` фиксированный FID не совпадает с family-id многих карт.

По исходнику mkgmap TypCompiler подтверждено:
- при передаче text TYP source mkgmap может override family-id/product-id/code-page параметрами текущей сборки.

Целевой вариант:
- canonical editable `styles/uralla.txt`;
- mkgmap компилирует per-map TYP с правильным FID;
- бинарный `.typ` — build artifact/reference, а не единственный canonical source.

Это сильный кандидат на объяснение старых случаев, когда Garmin не подхватывал TYP после тяжёлой low-memory сборки, но не утверждать, что это единственная доказанная причина.

TYP должен остаться редактируемым/сохраняемым в TYPViewer.

Night mode в финале не нужен:
- убрать NightXpm/NightcustomColor;
- DayAndNight -> Day.

## 20. Packaging mkgmap

Текущий combined `gmapsupp + gmapi + index` повышает peak memory и связывает два независимых результата.

Документация mkgmap указывает, что gmapsupp может собираться из уже compiled IMG, а одновременно два индекса для gmapsupp/tdb требуют примерно удвоенной памяти.

Целевой архитектурный принцип:
- compile OSM tiles once;
- отдельно package Garmin gmapsupp/index;
- отдельно package desktop GMAPI/tdb/index;
- TYP должен быть compiled с правильным family-id/code page в соответствующем packaging flow.

Нужно ещё проверить точные команды на используемой версии mkgmap.

## 21. Current args — решения

Текущий `uralla.args` содержит:
- gmapsupp;
- make-poi-index;
- code-page=1251;
- road-name-pois;
- verbose;
- route;
- process-destination;
- process-exits;
- make-cycleways;
- index;
- location-autofill;
- x-split-name-index;
- housenumbers;
- add-boundary-nodes-at-admin-boundaries;
- max-jobs=4;
- tdbfile;
- split-name-index;
- lower-case;
- gmapi;
- polygon density settings;
- simplify-lines;
- merge-lines;
- allow-reverse-merge;
- ignore-fixme-values;
- draw-priority=25;
- improve-overview;
- order-by-decreasing-area;
- cycle-map;
- link-pois-to-ways;
- keep-going;
- check-styles;
- DEM.

Предварительные решения:
- remove `make-cycleways` (obsolete/no modern effect);
- remove `road-name-pois`;
- keep `make-poi-index`;
- keep CP1251/lowercase пока;
- keep process-destination/exits;
- keep merge-lines;
- reverse merge only при корректной directional handling;
- keep link-pois;
- keep cycle-map пока до device test;
- remove keep-going в production build;
- packaging разделить;
- jobs и DEM parameters измерять;
- `uralla-no-dem.args` не должен быть независимой разъехавшейся копией args: в будущем общий base + DEM toggle/profile.

## 22. Current scripts — важные legacy/bug findings

`all.sh`:
- глобально удаляет старые PBF/IMG/ZIP/GMAP перед сборкой — убрать в новой системе;
- скачивает общий комплект независимо от due tasks — заменить dependency planning;
- карты связаны через `&&`, поэтому падение одной останавливает последующие — новая система должна изолировать fail per map;
- `/georgia.sh` вместо `./georgia.sh` — реальная ошибка.

Региональные скрипты содержат большой исторический drift:
- max-nodes от ~400k до 4M;
- отдельные max-threads/max-jobs;
- разные dem-dists;
- `keep-complete=false` у Turkey;
- `smart` у Mongolia;
- разные geonames;
- разные country/code-page overrides;
- старые commented Osmosis/wget pipelines.

Не объявлять это всё сразу ошибками. Классифицировать:
- REQUIRED;
- PRODUCT;
- LEGACY/TEST;
- BUG/STALE.

И измерять before/after.

## 23. Map ID / tile ID ranges

Обнаружены две исторические схемы mapid start:
- восьмизначные вроде `10220001`;
- семизначные вроде `1010001`, `1011001`, `1018001`.

Нельзя проверять только uniqueness стартового mapid.

После splitter manager должен знать фактический first/last tile ID и проверять пересечения диапазонов между картами.

Историю tile count хранить и предупреждать при приближении к reserved range.

Старые IDs не перенумеровывать без реальной необходимости, чтобы не менять идентичность установленных Garmin maps.

Для новых карт нужен central ID registry/reservation.

## 24. Spatial preprocessor — будущий центральный компонент

Разделение ответственности:
- preprocessor = spatial/context reasoning;
- mkgmap style = translation в Garmin semantics/rendering/routing;
- TYP = визуальный дизайн.

Планируемые модули:

### Routing context

Определять forest tracks/paths:
- проходящие через `man_made=clearcut` / logging;
- идущие ВДОЛЬ power line corridor;
- идущие ВДОЛЬ pipeline corridor.

Требования:
- crossing alone не считается;
- distance + parallel bearing + common corridor length;
- по возможности split geometry на affected segments;
- explicit survey physical tags (`surface`, `smoothness`) сильнее heuristic;
- route relation не отменяет physical penalty;
- strong routing penalty, но не access prohibition.

Garmin road speed общий, не bicycle-specific, поэтому точный уровень penalty нужно test на device.

### Transport generalization

Для parallel duplicate geometry (double-track railway, dual carriageways):
- все physical/routable originals сохраняются close zoom;
- far overview получает один representative line;
- overview geometry НЕ routable;
- internal tags типа `uralla:overview_primary=yes`;
- строгий match: proximity, parallelism, overlap, compatible class/ref/name;
- избегать yards/stations/service tracks/switches/links/roundabouts/interchanges;
- simplified geometry только для overview/synthetic objects.

### Contextual POI / declutter

Определять контекст не по admin city boundary, а по фактической плотности:
- urban_core;
- urban;
- suburban/periurban;
- settlement;
- rural;
- wilderness.

Использовать:
- building density;
- road density;
- POI density;
- landuse;
- distance from dense settlement;
- forest/protected context.

Внутренние теги:
- `uralla:context`;
- `uralla:poi_importance=1..5`.

Один POI может иметь разный LOD по контексту:
- city bench только close;
- isolated forest bench раньше;
- city grocery close;
- sole village grocery раньше;
- remote grocery near cycle route ещё раньше.

Учитывать rarity/distance to nearest same-category POI для воды, shelter, camp, station, ferry, bike repair, pharmacy и т.п.

Сначала НЕ создавать synthetic cluster POI; только менять LOD реальных objects.

### Modular design

Модули потенциально:
- corridors;
- transport_generalization;
- poi_context;
- tourist_priority;
- name normalization.

## 25. Clearcut/logging

Пользовательская реальность регионов:
- satellite updates запаздывают;
- clearcut polygons часто уже 5+ лет зарастают;
- в реальности похожи на сложный scrub/heath-like wasteland.

Финальное направление:
- `man_made=clearcut` визуально сделать точно как `natural=heath`;
- fallback label `вырубка`;
- не мутировать source `natural=heath`;
- использовать internal marker/visual mapping;
- `landuse=logging` можно близко визуально/по heuristic, но отдельная semantics.

Текущий `{add natural=heath}` случайно даёт похожий результат, но разрушает semantics — заменить намеренной архитектурой.

## 26. Cemetery

Большинство местных кладбищ фактически лесистые; крупные городские часто открытые.

Решение:
- cemetery = functional overlay;
- physical landcover определяется реальными тегами;
- cemetery+wood -> woods base + cemetery overlay;
- open cemetery -> neutral base + cemetery overlay;
- не придумывать forest всем кладбищам.

`0x1a` standard CEMETERY можно использовать.

Current drawOrder problem:
- cemetery 0x1a priority 6;
- forest 0x50 priority 7;
- forest может перекрывать pattern.

Финал:
- transparent/mostly-transparent cemetery cross pattern;
- cemetery drawOrder выше forest.

LOD ориентир:
- large cemetery ~22;
- ordinary ~23;
- all 24.

## 27. Protected areas

`nature_reserve`, `boundary=protected_area`, `boundary=national_park`:
- hatch только far/mid примерно 19–22;
- close 23–24 boundary only;
- не добавлять close hatch, чтобы не забивать trails/terrain/landcover.

Current bug:
- protected overlay идёт до/после базового landcover в неправильном порядке и теряется.

Финал:
- protected overlay before base landcover с continue;
- явно прокомментировать намеренное отсутствие close hatch.

## 28. Road/path philosophy

Labels exactly:
- `гравийка`;
- `плохая гравийка`;
- `грунтовка`;
- `плохая грунтовка`;
- `ужасная грунтовка`.

Не использовать `хорошая`.

Physical condition отделять от routing penalty.

Не переписывать `highway=path` в cycleway/footway/bridleway. Использовать internal markers; path может иметь несколько designations.

Path+bicycle=yes должен визуально отличаться от plain path.

City park cycleways visible/routable.

`service=parking_aisle` визуально скрыть, routing сохранить через transparent routable type, если device test подтвердит.

Tunnels:
- unified solid gray line для road/rail/cycle;
- underground subway hidden.

Bridges:
- physical base + overlay.

One-way arrows позже.

Route relation может повышать visibility, но не access.

### Trail/track zoom-dependent line width

Сохранить различный weight по zoom:
- far/mid thin non-routable custom overview line;
- close thick single routable physical base.

Path/trail close base -> standard `0x16 TRAIL`.

Track close base -> `0x0a UNPAVED_ROAD`.

Один OSM way <= один routable Garmin base.

Far trail/track representation только display-only.

Не использовать current routable `0x0b MAJOR_CONNECTOR` для far trails.

## 29. Rail

Сохранить hierarchy.

- narrow_gauge визуально как tram family;
- abandoned показывать, но не считать path без physical evidence;
- disused = weak rail, not path;
- underground subway hidden;
- above-ground subway shown;
- funicular custom;
- cable_car standard 0x2f, но текущий TYP надо визуально исправить;
- construction non-routable;
- miniature close;
- monorail close-ish.

Lifecycle forms:
- `railway=disused`;
- `disused:railway=*`;
- `railway=* & disused=yes`;
- аналогично abandoned.

Не давать inactive rail проваливаться в active rules.

Main rail standard `0x14 RAILROAD` предпочтителен для fallback.

Station POI target:
- station ~21;
- halt 22–23;
- platform 24.

Bike approach:
- physically connected platform/station access graph должен позволять bicycle routing as dismount;
- не создавать fake connectors;
- stop_area relation не считать достаточной заменой physical network.

## 30. Hydrology

Сохранить intentional river routing через taxi hack для water tourism.

Не удалять бездумно.

Hard-coded important rivers / far zoom rules сохранить.

Water lines:
- river -> 0x1f;
- stream/drain -> coherent standard family;
- ditch close only;
- intermittent -> standard 0x26 where appropriate;
- ferry routable вернуть 0x1b + `mkgmap:ferry=1`;
- route=canoe high priority;
- dam/weir distinct;
- waterfall point only;
- waterfall line/polygon удалить;
- rapids support canonical `waterway=rapids`, singular/whitewater compatibility.

Strong recommendation остаётся убрать waterfall из water taxi route set, но это ещё не отдельно подтверждено пользователем.

Water POI:
- seasonal/intermittent;
- water tap not automatically potable;
- `water_point` label `запас воды`.

## 31. Polygon/landcover audit — ключевые решения

Architecture:
- normalize;
- preprocess markers;
- overlays/LOD;
- physical/base landcover;
- functional overlays/areas;
- generic fallbacks late;
- finalize.

Ключевые проблемы/решения:
- destructive `man_made=* & landuse/natural=* {delete man_made}` убрать;
- protected overlay move before landcover;
- geoglyph не должен делить type с forest overview;
- golf должен использовать semantic fallback 0x18, current meadow/golf mapping исправить;
- forest base close standard 0x50 + species overlay;
- leaf_type classification scope только внутри forest/wood;
- bare_rock/blockfield/scree close distinguish;
- peat cutting duplicated/unsafe type — move custom;
- residential duplicated rules simplify;
- named islands move before landcover with continue;
- generic tourism/manmade late;
- private leisure catchall remove;
- retail use standard shopping area 0x08;
- `landuse=farm` не нормализовать автоматически в farmland;
- farmyard separate;
- plant_nursery/greenhouse_horticulture close support;
- managed grass vs meadow/grassland close distinguish;
- greenfield = development, not meadow;
- quarry/landfill/construction manmade base + hatch;
- wetlands: standard 0x51 base + transparent subtype overlay;
- add bog/fen/string_bog groups;
- saltmarsh duplicate remove;
- basin не blanket-convert в water;
- water lake current size LOD thresholds сохранить;
- glacier standard 0x4d base + detail;
- waterfall polygon delete.

Mechanical TYP validation for polygons:
- A = emitted polygon types;
- B = TYP polygon definitions;
- C = drawOrder.

Rules:
- A-C => ERROR, invisible polygon;
- A-B => intentional fallback only;
- C-A => stale drawOrder candidates;
- B-A => stale TYP candidates.

Current known invisible polygon candidates из-за отсутствия drawOrder:
- 0x0e runway/taxiway areas;
- 0x1e historic polygon use.

Current drawOrder duplicate:
- 0x10f09 appears twice.

## 32. Functional polygons — ключевые решения

- place city/town current mapping reversed relative TYP; fix city->large city, town->small city, village/hamlet next;
- military 0x04 label should mean neutral military territory, not automatically prohibited;
- explicit access controls routing;
- military airfield = airport base + military overlay;
- industrial standard 0x0c;
- commercial custom safe;
- retail 0x08;
- healthcare generic too broad; hospital/clinic specific;
- fuel before generic shop; no destructive highway mutation;
- paved/plaza areas should not use reservation/parking types incorrectly;
- platform polygon custom close, preserve name;
- building=no exclude;
- bridge area separate from building;
- ruins on building better building base + POI;
- tourism attraction mostly POI;
- sport areas unify where meaningful;
- dog park custom close;
- utilities modern power plant/substation support;
- water_works/wastewater remain identifiable even if industrial.

## 33. Lines audit — ключевые проблемы

Known current issues:
- `bridge=no` deletes highway — wrong;
- delete rail typo/legacy;
- `highway=escape -> service` semantically bad;
- overlays can render before cleanup;
- bad access defaults on cycleway/footway;
- lifecycle prefix forms incomplete;
- roundabout/link rules can create duplicate routable bases;
- links need one routable base only;
- motorroad=yes should not imply trunk visual class;
- custom tertiary/residential types may have poor fallback;
- path 0x2e bad fallback, actual via_ferrata should own 0x2e;
- highway=minor ambiguous legacy;
- aeroway taxiway current 0x1a wrong (ferry); use standard 0x27;
- steps should have routable base + decorative overlay;
- highway=road can be dead due catchall;
- disused currently can get multiple routable copies;
- private/no tunnels must not be physically deleted;
- winter/ice XOR bug, should be OR logic;
- ford current can overwrite base; use overlay;
- fuel line rule mutates highway wrongly;
- path conversion duplicates/destructive rewrite; replace internal flags;
- halfpipe must not invent footway routing;
- pier fallback name only, preserve real name;
- pipeline generic catchall ordering;
- hide underground/underwater pipelines;
- piste remove `is_closed()=false` dependency;
- embankment/cutting infra types move safe custom;
- one OSM way <= one routable Garmin base.

Final desired line architecture:
- normalize/name/legacy;
- lifecycle;
- access preprocess;
- non-routable overlays;
- exactly one routable highway base;
- exactly one trail base;
- rail;
- infra/terrain;
- finalize.

## 34. Surface/smoothness semantics

Separate:
- material/surface;
- physical difficulty;
- access.

Rules:
- gravel not automatically bad;
- tracktype fallback only if surface missing;
- grade1 hard-ish;
- grade2-5 unpaved;
- grade6 noncanonical;
- sac_scale implies foot use, not automatically unpaved material;
- mtb/sac/via_ferrata not material;
- smoothness excellent/good/intermediate normal;
- bad small penalty;
- very_bad stronger;
- horrible/very_horrible strong;
- impassable blocks wheeled routing but may keep foot;
- do not invent source access=no;
- trail_visibility affects LOD;
- route membership may promote +1;
- informal != poor visibility;
- incline no generic penalty;
- gravel/dirt labels mutually exclusive.

## 35. TYP line system — предварительная классификация

Good/semantic standard line types:
- 0x01–09 roads/ramps;
- 0x0a unpaved road;
- 0x0c roundabout;
- 0x14 railroad;
- 0x16 trail;
- 0x18 stream;
- 0x1b ferry;
- 0x1c–0x1e boundaries;
- 0x1f river;
- 0x20–0x22 contours;
- 0x23–0x25 bathymetry;
- 0x26 intermittent stream;
- 0x27 runway/taxiway;
- 0x28 pipeline;
- 0x29 powerline;
- 0x2e via ferrata;
- 0x2f cable car, но restyle.

Good custom concepts:
- routable water taxi;
- winter road;
- ridge/gully;
- tunnel redraw;
- pier/tree row/cutline;
- oneway arrows;
- urban rail;
- bridges;
- cliff;
- construction;
- ford;
- dam/fence/protected boundary/stairs.

Unsafe/stale candidates:
- old smoothness custom types;
- waterfall line;
- rapids unsafe type;
- old piste types move;
- stale cycle custom definitions;
- culvert custom line;
- infra types with poor fallback.

Не финализировать allocation до полного cross-inventory.

## 36. Relations

Principles:
- relation context не должен переписывать physical type/access;
- hiking route=hiking, foot walking;
- bicycle route networks;
- mtb separate;
- relation membership only raises visibility/labels, not access;
- names/refs accumulate as internal metadata;
- canoe route networks;
- untagged water relation link может стать taxi route только если water semantics подтверждены;
- access respected;
- forward/back roles itinerary, not oneway;
- portage support modern/legacy;
- piste relation = non-routable winter overlay, physical summer base preserved;
- no separate hiking/bike/mtb route overlay in initial release, only LOD/labels;
- empty overlays file KEEP reserved;
- superroute deferred;
- horse future;
- ferry restore.

## 37. Points/POI

Key decisions:
- fuel rules consolidate; generic first currently kills specifics;
- memorial/signpost preserve real name + fallback;
- opening_hours -> postcode hack intentional for current Garmin UI but harms address index; keep until test/documentation;
- building POI only actual nodes because add-pois-to-areas disabled;
- no protected area point POI;
- guidepost/cross/shrine/cairn useful;
- food collapse restaurant/cafe/fast_food/food_court;
- supermarket/convenience/general/grocery/food/bakery/butcher/organic product family;
- pharmacy standard;
- bicycle shop standard;
- auto family standard;
- generic shop standard;
- fuel + convenience -> fuel POI + product POI;
- remove caravan_site and speed bumps;
- keep railway signals/km/picket;
- named trees/shrubs only;
- utility poles remove;
- communication towers remain;
- huts split wilderness/alpine vs shelter;
- accommodation normalize;
- remove point playground/sports/pitch/pool/fitness, polygons stay;
- picnic table/firepit/camp remain;
- viewpoint dedicated;
- generic attraction after specifics.

Known point bugs:
- broad `ele=* & natural!=*` steals mountain_pass;
- forest island exclusion OR bug;
- special peak marker should be internal;
- survey/cave fallback types wrong;
- stream point remove;
- duplicates basin/village_green;
- station/halt/platform LOD inversion;
- guidepost modern/legacy;
- whitewater impossible combination;
- motorcycle shop icon wrong;
- AED/first aid custom;
- remove utility pole;
- remove nature reserve point;
- huts/accommodation normalization;
- supermarket/fuel duplicates;
- traffic_calming remove;
- bridge point remove candidate;
- info after guidepost;
- cairn custom;
- valley/arch types;
- intermittent spring semantics;
- healthcare split;
- topo/water before attraction.

## 38. Peak hierarchy

User intended:
- special hard-coded peaks always large/far;
- ordinary name+ele small far, medium close;
- name-only or ele-only small close;
- neither small res24.

Current bug: name without ele disappears.

Preserve hierarchy, fix fallback/types/internal marker.

## 39. Address processing

Current custom `inc/address` has Russia-specific logic and uses fake admin levels.

Important:
- preserve current conceptual address behavior until controlled test;
- `mkgmap:street` should retain full unshortened street name for house-number matching;
- display label can be shortened separately;
- fabricated place boundaries need lifecycle marker to avoid rendering as real admin boundaries.

## 40. Build-system file layout — tentative

Possible future structure:

```text
scripts/
    build-manager

config/
    maps.*
    tools.*

bootstrap/
    linux
    macos

.tools/
    mkgmap/
    splitter/

cache/
    sources/
    bounds/
    sea/
    geonames/

state/
    builds.sqlite
    locks/
    logs/

work/
staging/
published/
```

Exact names can change after audit.

`.gitignore` currently почти пустой (`.DS_Store` only), поэтому перед первым запуском новой системы нужно исключить generated/cache/state/work/staging/.tools, но оставить source/config/poly/styles/preprocessor schemas под Git.

## 41. Current philosophy of changes

Не удалять старую странность только потому, что выглядит странно.

Каждую региональную разницу классифицировать:
- REQUIRED — реально нужна;
- PRODUCT — сознательная особенность карты;
- LEGACY/TEST — перенести временно и перепроверить измерениями;
- BUG/STALE — доказанная ошибка/устаревший артефакт.

Примеры:
- Northwestern готовый Geofabrik PBF -> LEGACY WORKAROUND;
- Mongolia strategy=smart -> LEGACY/TEST;
- Turkey keep-complete=false -> LEGACY/TEST;
- Ural-S polygon -> PRODUCT/REQUIRED;
- family-id -> REQUIRED;
- split ZIP -> STALE, удалить;
- `/georgia.sh` -> BUG.

## 42. Release changelog

После финального релиза создать отдельный human-readable changelog относительно старой версии.

Он должен быть пригоден для Telegram, а не просто git diff.

Структура:
- короткий блок `Главные изменения`;
- trails/forest roads;
- bicycle routing;
- hiking routing;
- rail;
- water tourism;
- landcover;
- protected areas;
- POI;
- rendering/LOD;
- fixed old bugs;
- TYP;
- naming;
- removed obsolete rules;
- intentionally unchanged behavior.

Имя файла выбрать по реальному номеру релиза позже, не предполагать заранее.

## 43. Что делать дальше

Текущая точка работы:
1. закончить полную матрицу всех 27 карт и классифицировать различия;
2. закрыть country/language/geonames/DEM/no-DEM profiles;
3. проверить exact mkgmap label/addlabel strategy;
4. закрыть TYP compile/package flow;
5. завершить mechanical cross-inventory lines/points/polygons <-> TYP;
6. проверить packaging from precompiled IMG;
7. подготовить controlled tests для Northwestern, Turkey, Mongolia и splitter params;
8. только после полного аудита создать интеграционную ветку и начать реализацию.

До этого main оставлять без изменений, кроме явных пользовательских добавлений и этого файла памяти.
