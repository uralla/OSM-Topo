# Garmin OSM Topo — память проекта на 2026-08-25

Этот файл фиксирует текущее состояние обсуждения проекта, принятые решения, найденные проблемы, архитектурные идеи и следующие шаги. Это рабочая память проекта, чтобы её можно было использовать при продолжении работы в новых чатах или на другом компьютере.

## 1. Общая цель проекта

Проект — пользовательский стиль и конвейер генерации Garmin OSM Topo.

Основной приоритет карты:
1. Пеший туризм, особенно лес, тропы, рельеф, природные объекты.
2. Велотуризм и велосипедная маршрутизация.
3. Остальные сценарии использования.

Городские велодорожки должны быть видимыми и маршрутизируемыми.

Скорость сборки вторична по отношению к качеству, стабильности и предсказуемости результата.

Рабочая production-машина старая Ubuntu и намеренно работает с ограниченной частотой CPU. Полная генерация может занимать много часов или около суток.

Главный принцип аудита: сначала полностью разобраться в текущей системе, потом делать один согласованный набор изменений. Не вносить по частям хаотические правки в style/TYP/build до завершения аудита.

## 2. Репозиторий

Основной репозиторий:
`uralla/OSM-Topo`

В нём сейчас находятся:
- `styles/uralla` — mkgmap style;
- `styles/uralla.txt` — текстовый TYP, фактически канонический исходник оформления;
- `styles/uralla.typ` — бинарный TYP;
- `styles/xuralla.typ` — ещё одна бинарная версия;
- `styles/uralla.args`;
- `styles/uralla-no-dem.args`;
- `scripts/` — полный набор рабочих скриптов генерации всех текущих карт;
- `scripts/transform_places.xml` — текущая Osmosis tag-transform схема;
- `poly/` — границы карт;
- review/audit документы.

Папка `scripts` теперь содержит все рабочие скрипты текущей production-сборки. Это 27 реально генерируемых карт плюс управляющий `all.sh`.

Папка `poly` также добавлена в Git и теперь считается частью определения продуктов.

## 3. Рабочий процесс с GitHub

У ChatGPT есть подключение к репозиторию и возможность:
- читать файлы;
- создавать новые файлы;
- обновлять существующие;
- создавать ветки;
- делать коммиты и PR.

Прямого доступа к Ubuntu/Mac файловой системе нет.

Когда начнётся реализация, изменения планируются непосредственно через GitHub, а не через ручной copy/paste из чата.

Правильная схема:
- `main` пока остаётся стабильной рабочей версией;
- после завершения аудита создаётся отдельная интеграционная ветка;
- изменения пишутся туда напрямую;
- пользователь получает их обычным `git pull`/`git switch`.

До завершения полного аудита репозиторий не меняется, кроме явно согласованных документирующих файлов вроде этого файла памяти.

## 4. Базовые принципы style/TYP

### 4.1. Не разрушать исходную семантику OSM

Безопасные legacy-нормализации допустимы только там, где соответствие однозначное.

Не надо:
- превращать физический `highway=path` в cycleway/footway/bridleway;
- заменять реальные теги на интерпретации ради отображения;
- выдумывать отсутствующую геометрию или доступ.

Нужны внутренние флаги/теги для Garmin-логики.

### 4.2. `length()` и `area_size()`

Это намеренные механизмы LOD/generalization, а не ошибки.

Сохранять:
- дальнюю видимость важных рек;
- специальные пики;
- M-5 и другие осознанно выделенные важные объекты.

### 4.3. TYP fallback

Надёжный fallback на стандартные Garmin-типы очень важен. Был реальный случай: после тяжёлой многопоточной сборки TYP на Garmin не применился, хотя в QMapShack карта выглядела нормально.

Поэтому желательно:
- использовать стандартный Garmin type там, где он семантически подходит;
- custom overlay строить поверх стандартной основы;
- не использовать стандартный type с совершенно другой семантикой только ради свободного номера.

TYP должен оставаться редактируемым и сохраняемым через TYPViewer.

Ночной режим не нужен. В финале убрать NightXpm/NightcustomColor и `DayAndNight`, оставить `Day`.

## 5. TYP FID — важный найденный механизм

Текущий `styles/uralla.txt` содержит:
- FID=1002;
- ProductCode=1;
- CP1251.

Но разные карты имеют разные `family-id`.

Из исходников mkgmap подтверждено: если mkgmap получает текстовый `.txt` TYP, он после разбора заменяет в нём Family ID, Product ID и code page значениями из параметров текущего запуска.

Поэтому целевая схема:
- канонический исходник — `styles/uralla.txt`;
- бинарный TYP не должен быть вручную общей статической зависимостью всех карт;
- mkgmap компилирует TYP для каждой карты с её `family-id` и code page.

Старый фиксированный бинарный `uralla.typ` с FID=1002 является реальным структурным несовпадением для большинства карт и сильным кандидатом на одну из причин старых проблем с Garmin, но пока не доказано, что это была единственная причина.

## 6. Названия объектов

### 6.1. Общая идея

Исходный OSM `name` не уничтожать.

Для Garmin создать отдельное display-name.

Предпочтительная архитектура:
- label1 — короткое читаемое имя для экрана Garmin;
- label2 — полное исходное/сформированное имя;
- адресный поиск использует отдельный `mkgmap:street` и не должен ухудшаться из-за сокращения label1.

mkgmap поддерживает до 4 labels. Обычно отображается первый, второй на некоторых устройствах может участвовать в навигационных подсказках, все labels могут участвовать в поиске.

### 6.2. Русские сокращения

Сокращение должно быть глобальным, не только для дорог.

Существующие/принятые безопасные замены:
- `улица → ул.`
- `переулок → пер.`
- `проспект → пр-т`
- `проезд → пр-д`
- `разъезд → раз.`
- `тракт → тр-т`
- `площадь → пл.`
- `имени → им.`
- `бульвар → бл-р`
- `шоссе → ш.`
- `дорога → дор.`
- `тупик → туп.`
- `микрорайон → мкр.`
- `аллея → алл.`
- `линия → лин.`
- `набережная → наб.`
- `Восточный → Вост.`
- `Западный → Зап.`
- `Южный → Юж.`
- `Северный → Сев.`
- `совхоз → свх.`

Дублирующий `имени=>им.` убрать.

Сильные сокращения — только по белому списку устойчивых общеизвестных конструкций.

Пример целевого результата:

Исходное:
`улица 50-летия Всесоюзного Ленинского Коммунистического Союза Молодёжи`

Garmin label1:
`ул. 50-лет ВЛКСМ`

Garmin label2:
полное исходное название.

Другой пример:
`Совхоз имени XXIII съезда КПСС Северный`
→ `Свх. им. XXIII съезда КПСС Сев.`

### 6.3. Зарубежные карты и язык

Язык отображения и кодировка — отдельные параметры.

Главная задача для зарубежных карт: показывать название, которое с наибольшей вероятностью сможет прочитать пользователь.

Для стран с нелатинским письмом предпочтительный профиль:
1. `name:en`
2. `int_name`
3. уже существующая латинская форма
4. автоматическая транслитерация `name`
5. `name:ru`
6. исходный `name`, если больше ничего нет

Для Грузии/Армении/Монголии желательно английское или транслитерированное имя, а не локальное письмо.

Турция — отдельный случай: местные имена уже латиницей, поэтому профиль может предпочитать `name:en` или нормальное локальное латинское имя с fallback/transliteration.

`--latin1` не решает выбор языка, это только кодировка. Старый `--latin1` следует считать практическим решением правильной проблемы на неправильном уровне.

Перспективная архитектура: preprocessing формирует `uralla:display_name` и `uralla:full_name`, а style только применяет их.

## 7. Protected areas

Для `nature_reserve`, `boundary=protected_area`, `boundary=national_park`:
- hatch только на дальнем/среднем зуме примерно 19–22;
- на 23–24 только граница;
- не добавлять плотную штриховку на близком зуме.

Главная текущая ошибка — порядок: overlay идёт после базового landcover и может не сработать. Protected overlay должен обрабатываться до base landcover с `continue`.

## 8. Clearcut / logging

Пользовательская реальность: в целевых регионах `man_made=clearcut` часто обозначает вырубки, которые на земле уже 5+ лет заросшие, труднопроходимые, кустарниковые.

Целевое отображение:
- `man_made=clearcut` визуально как `natural=heath`;
- fallback label `вырубка`;
- не мутировать `natural=heath` в данных;
- использовать внутренний маркер и тот же visual family.

`landuse=logging` можно отнести к той же визуальной/маршрутизационной семье, но сохранить отдельную семантику.

## 9. Кладбища

Большинство локальных российских кладбищ фактически лесистые, крупные городские бывают открытыми.

Целевая архитектура:
- не выдумывать лес автоматически;
- cemetery — функциональный прозрачный overlay;
- физический landcover под ним берётся из реальных OSM-тегов;
- cemetery+wood = лес + cemetery overlay;
- cemetery без landcover = нейтральная база + cemetery overlay.

Использовать стандартный polygon `0x1a CEMETERY`.

Текущая проблема drawOrder: cemetery ниже forest, поэтому лес может перекрывать cemetery pattern. В финале cemetery должен быть прозрачным/почти прозрачным крестовым pattern и находиться выше forest в drawOrder.

LOD: крупные кладбища могут появляться около 22, обычные 23, все 24.

## 10. Дороги и тропы

### 10.1. Подписи состояния

Использовать именно:
- `гравийка`
- `плохая гравийка`
- `грунтовка`
- `плохая грунтовка`
- `ужасная грунтовка`

Не использовать слово `хорошая`.

### 10.2. Физический тип и designation

`highway=path` не переписывать в cycleway/footway/bridleway.

Path может одновременно иметь несколько designation.

Нужны внутренние маркеры для отображения/маршрутизации.

`path + bicycle=yes` должен визуально отличаться от обычной тропы.

### 10.3. Zoom-dependent weight

Очень важно сохранить разную толщину троп и лесных дорог по зумам.

Идея:
- дальний/средний зум — тонкая display-only non-routable линия;
- близкий зум — одна routable physical base линия, толще;
- один OSM way должен иметь максимум одну routable Garmin base line.

Для trail:
- far/mid thin overview custom;
- close `0x16 TRAIL` routable.

Для track:
- far/mid thin overview custom;
- close `0x0a UNPAVED_ROAD` routable.

Не использовать `0x0b MAJOR_CONNECTOR` как far trail/track.

### 10.4. Service parking aisle

`service=parking_aisle` визуально скрывать полностью, но маршрутизацию сохранять, вероятно через прозрачный routable TYP type.

### 10.5. Тоннели и мосты

Тоннели: единая сплошная серая линия для road/rail/cycle, кроме подземного subway, который скрывается.

Мосты: base + overlay.

### 10.6. Surface / smoothness

Материал покрытия и качество — разные параметры.

- gravel сам по себе не плохой;
- tracktype fallback использовать только если surface отсутствует;
- grade1 hard-ish;
- grade2–5 unpaved;
- grade6 noncanonical;
- smoothness независимо влияет на routing penalty;
- impassable блокирует колёсную маршрутизацию, но пеший проход может сохраняться;
- sac_scale не означает автоматически unpaved;
- informal — не то же самое, что плохая видимость.

## 11. Железные дороги

Сохранять подробную иерархию.

- narrow_gauge визуально как tram family;
- abandoned отображается;
- abandoned может стать path только если это реально один и тот же объект с соответствующим физическим тегом, без spatial guessing;
- disused слабая железная дорога, не path;
- subway underground скрывать;
- above-ground subway показывать;
- funicular → `0x10f00`;
- cable_car → стандартный `0x2f`, но текущий TYP-вид нужно переделать;
- main rail лучше стандартный `0x14 RAILROAD`;
- tram/light_rail/narrow_gauge/above-ground subway — custom urban rail family;
- lifecycle tags обрабатывать внутренними маркерами, чтобы inactive rail не падала потом в active rule.

Station POI target:
- station ~21;
- halt 22–23;
- platform 24.

Платформы/подходы желательно сделать bike-routable как dismount, если физически связаны, без фальшивых соединителей.

## 12. Вода и водный туризм

River routing через taxi hack — намеренная и ценная функция. Не удалять.

Сохранять hard-coded важные реки.

Целевая логика:
- river `0x1f`;
- stream/drain ближе к стандартным водным типам;
- ditch только close zoom;
- intermittent — standard `0x26`;
- waterfall только point, удалить line/polygon waterfall;
- rapids поддерживать canonical `waterway=rapids` + legacy singular/whitewater;
- route=canoe high priority;
- dam `0x12d01`;
- ferry восстановить как routable `0x1b` с `mkgmap:ferry=yes`;
- water tap не считать автоматически potable;
- water_point label `запас воды`.

`0x19` как stream плохой fallback, потому что стандартно это TIME_ZONE_BOUNDARY. Для stream использовать `0x18 STREAM`.

## 13. Леса и landcover

Сохранять существующие разумные forest LOD thresholds.

Forest close лучше строить как:
- стандартный `0x50 WOODS` base;
- transparent species overlay на res24.

Leaf type применять только после подтверждения wood/forest semantics.

Bare rock/blockfield/scree:
- близко различать;
- средний зум может использовать общую семью;
- сохранить туристические thresholds.

Water lake LOD текущий хороший и должен остаться примерно таким:
- >10 км² res16;
- >3.5 км² 17–18;
- >150k 19;
- >50k 20–21;
- >20k 22–23;
- все 24.

Wetlands:
- стандартный `0x51` base;
- transparent subtype overlay;
- swamp / marsh-fen / bog-string_bog / reedbed / wet meadow.

`landuse=basin` нельзя безусловно превращать в `natural=water`.

## 14. Functional polygons

Ключевые найденные проблемы:

- ранние `man_made=* & landuse=* {delete man_made}` и `man_made=* & natural=* {delete man_made}` разрушительны — убрать;
- place city/town сейчас перепутаны относительно TYP: city должен идти в large city type, town в small city;
- military `0x04` визуально нормален как overlay, но label `запретная зона` слишком сильный — лучше `военная территория`;
- generic healthcare слишком широк;
- generic shop слишком ранний и ворует fuel+shop;
- fuel должен обрабатываться первым, собственный close polygon, без разрушения highway;
- plaza/pedestrian area не должны использовать `0x0d RESERVATION`;
- platform polygon нужен отдельный custom type ближе к 23–24;
- building=no надо исключать из building rules;
- generic tourism должен быть поздним;
- private leisure catchall удалить;
- utilities: modern `power=plant/substation`, water_works/wastewater;
- retail использовать стандартный `0x08 SHOPPING_AREA`;
- golf должен использовать стандартный golf polygon type;
- meadow не должен занимать golf type;
- geoglyph не должен делить type с far forest.

## 15. Механическая проверка polygon ↔ TYP ↔ drawOrder

Критическое правило mkgmap TYP: polygon type, которого нет в `_drawOrder`, не отображается вообще.

Текущие примеры проблем:
- style выдаёт polygon `0x0e` runway/taxiway, но его нет в drawOrder;
- style выдаёт polygon `0x1e` historic area, но его нет в drawOrder;
- current drawOrder имеет дубли и stale types, например `0x10f09` встречается дважды.

После финального rewrite нужен автоматический validator:
- A = polygon types, которые реально выдаёт style;
- B = polygon definitions в TYP;
- C = drawOrder.

Проверки:
- `A - C` = ERROR, невидимый polygon;
- `A - B` допустимо только для намеренного стандартного Garmin fallback;
- `C - A` stale drawOrder candidates;
- `B - A` stale TYP candidates.

Build должен падать, если `A-C` не пусто.

Аналогичный mechanical inventory нужен потом для lines и points с учётом независимых geometry namespaces.

## 16. Points / POI

Основные решения:
- fuel rules сейчас конфликтуют — объединить;
- restaurant/cafe/fast_food/food_court → одна food family;
- supermarket/convenience/general/grocery/food/bakery/bakers/butcher/organic → products family;
- pharmacy отдельный;
- bicycle shop отдельный;
- auto family отдельный;
- other shop generic поздно;
- fuel+convenience может давать второй POI `АЗС (продукты)`;
- убрать caravan_site и speed bumps;
- railway signals/km/picket оставить;
- named trees/shrubs только;
- utility poles убрать;
- communication towers оставить;
- wilderness/alpine hut отдельный;
- shelter отдельно;
- campground отдельный;
- remove playground/sports/pitch/pool/fitness point POI, если polygons остаются;
- picnic table/firepit/camp оставить;
- viewpoint dedicated;
- generic attraction поздно.

Peak hierarchy:
- special peak всегда большой;
- ordinary name+ele small far, medium close;
- name-only/ele-only small close;
- neither small24.

Текущий bug: peak с name без ele может пропадать — исправить.

## 17. Relations

Relation context не должен менять физический тип или доступ.

- route=hiking / foot walking;
- bicycle routes;
- mtb отдельно;
- canoe routes;
- relation membership может продвинуть LOD на +1;
- relation не делает путь автоматически разрешённым;
- forward/back roles — itinerary, не oneway;
- portage поддержать;
- piste relation — nonroutable winter overlay;
- superroute пока deferred;
- horse future.

Пока не делать отдельные hiking/bike/mtb overlays в первом релизе: relation повышает видимость и помогает label, но не дублирует routable base.

## 18. Future spatial preprocessor — важная архитектура

Это потенциально одна из главных отличительных особенностей проекта.

Разделение обязанностей:
- preprocessor = spatial/context reasoning;
- mkgmap style = перевод результата в Garmin rendering/routing;
- TYP = визуальное оформление.

Предпочтительное место в pipeline:
`regional OSM extract → name/address normalization → SPATIAL PREPROCESSOR → merge elevation/contours → splitter → mkgmap`

### 18.1. Routing context

Определять tracks/paths:
- проходящие через `man_made=clearcut` / logging;
- долго идущие вдоль ЛЭП;
- долго идущие вдоль pipeline.

Важно отличать продольное следование от простого пересечения.

Критерии:
- distance;
- parallel bearing;
- common corridor length.

На affected segments давать сильный routing penalty, но не access prohibition.

Желательно делить geometry на сегменты, чтобы penalty получал только реально плохой участок.

Явные физические survey tags (`surface`, `smoothness`) важнее heuristic.

Relation membership не отменяет физический penalty.

Точный `road-speed=0/1` тестировать на Garmin.

### 18.2. Transport generalization

Определять параллельные линии одного транспортного коридора:
- double-track railway;
- dual carriageway.

На близком зуме сохранять все оригинальные physical/routable линии.

На дальнем зуме выбирать одну representative display-only geometry, например:
- `uralla:overview_primary=yes`;
- `uralla:overview_secondary=yes`.

Overview geometry не должна быть routable.

Строгие условия:
- proximity;
- parallelism;
- long overlap;
- compatible class/ref/name;
- исключать yards/stations/service tracks/switches/links/ramps/roundabouts/interchanges.

### 18.3. Contextual POI / declutter

Цель: в городских парках и центрах слишком много bench/shop/POI, а в wilderness важный одиночный POI может быть слишком поздним.

Контекст должен быть не просто admin city boundary, а вычисляемый:
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

Внутренние параметры:
- `uralla:poi_importance=1..5`;
- `uralla:context=...`.

Одинаковый POI:
- в dense city показывается позже;
- в rural/wilderness раньше.

Пример:
- urban bench только res24;
- isolated forest bench res22–24.

Rarity: distance до ближайшего POI той же категории.

Особенно важно для:
- shop/food;
- drinking water/water source;
- shelter;
- camp;
- station;
- ferry;
- bicycle repair;
- pharmacy.

Близость к hiking/bicycle/canoe route может давать +1 importance.

Пока не создавать synthetic cluster POI. Сначала только promote/suppress LOD реальных POI.

### 18.4. Product boundary vs analysis boundary

Текущие `.poly` из Git считаются `PRODUCT BOUNDARY` — строгая граница конечной Garmin-карты.

Будущий preprocessor может временно использовать более широкую `ANALYSIS BOUNDARY`, чтобы понимать контекст за краем карты.

Схема:
`product poly → temporary buffer → preprocessing → clip обратно строго по product poly`

Никакой внешний контекст не должен попадать в финальную Garmin-карту.

Это важно, потому что карты часто включаются по одной, но несколько могут быть активны одновременно. Пользователь специально выбирает продуктовые границы так, чтобы основной интерес лежал внутри одной карты, а приграничные артефакты не мешали чтению.

## 19. `osmium extract --strategy=simple`

Текущий `simple` — не ошибка, а исторический stability compromise с неизвестной, но вероятно реальной причиной.

Нельзя просто заменить его на smart/complete.

Большинство текущих карт используют `simple`.

Монголия — заметное исключение с `--strategy=smart`.

Турция использует `simple` + `--keep-complete=false`.

Новая политика:
- baseline A = текущий `simple`;
- позже контролируемые A/B тесты альтернативных strategies;
- оценивать не только build success, но и:
  - количество ways/relations;
  - completeness hiking/bicycle/canoe relations;
  - multipolygon forest/water/admin integrity;
  - PBF size;
  - memory/time;
  - mkgmap warnings;
  - Garmin visual result.

Создать корпус проблемных объектов:
- huge admin relation;
- long tourist route;
- complex forest/water multipolygon;
- double-track railway;
- ferry;
- giant relation.

Возможно оставить simple-like bounded behavior и селективно гарантировать нужные relations, вместо полного smart extraction.

## 20. Northwestern / Калининград

Текущая рабочая сборка СЗФО использует готовый `northwestern-fed-district-latest.osm.pbf` как legacy workaround, потому что прежняя попытка резать из `russia-latest` почему-то ломалась дальше по pipeline.

Пользователь предполагает, что причина могла быть связана с multipart `.poly` и Калининградом.

Проверено:
- `poly/northwestern-fed-district.poly` содержит два внешних контура;
- второй контур — Калининград;
- это не hole.

То есть сам `.poly` выглядит корректно как multipart product boundary.

Целевая схема всё равно:
`russia-latest.osm.pbf → osmium extract simple → northwestern multipart poly → preprocessing → splitter → mkgmap`

План теста:
A. текущий workaround с Geofabrik district PBF;
B. желаемая схема из `russia-latest` + polygon + splitter polygon;
C. из `russia-latest` + polygon, splitter без polygon-file;
D. два отдельных extract (основной СЗФО + Калининград) → merge → splitter.

Отделять Калининград в отдельную карту только если современный pipeline реально не сможет устойчиво собирать multipart СЗФО.

## 21. `transform_places.xml`

Файл теперь находится в `scripts/transform_places.xml`.

Текущая логика:
- city/town → fake admin_level=7;
- village/hamlet → fake admin_level=10;
- isolated_dwelling/allotments → fake admin_level=11;
- добавляет `boundary=administrative` и `type=boundary`.

Назначение: улучшение address/search после boundary processing.

Проблемы для аудита:
- комментарий говорит про place polygons, но match видит только `place=*`; надо проверить применение к nodes/ways/relations;
- правило не проверяет наличие уже настоящей admin semantics;
- в старых скриптах путь к файлу плавает между `../transform_places.xml` и `./transform_places.xml`.

Новая система должна иметь одну каноническую копию и использовать абсолютный путь от project root.

Возможная будущая схема: temporary marker вроде `uralla:fake_place_boundary=yes`, чтобы искусственные границы для address inference не попадали в visible boundary rendering.

## 22. Текущая build-система и её проблемы

Текущий pipeline:
`PBF → osmium extract → Osmosis transform_places → merge elevation → splitter → mkgmap → IMG + GMAPI → rename/copy publish`

Скрипты исторически разошлись по:
- max-nodes;
- max-jobs;
- splitter threads;
- keep-complete;
- extract strategy;
- dem-dists;
- code page / latin1;
- geonames;
- polygon usage;
- source PBF;
- publish/zip режимам.

Не считать все различия необходимыми: многие могут быть следами старых OOM/экспериментов.

Категории при аудите:
- REQUIRED — реальная необходимость;
- PRODUCT — осознанная характеристика карты;
- LEGACY/TEST — старый override, который переносим как baseline и проверяем измерениями;
- BUG/STALE — явная ошибка/устаревший артефакт.

Примеры:
- Northwestern Geofabrik PBF → LEGACY WORKAROUND;
- Mongolia smart → LEGACY/TEST;
- Turkey keep-complete=false → LEGACY/TEST;
- `/georgia.sh` вместо `./georgia.sh` в `all.sh` → BUG;
- split ZIP → STALE, удалить;
- family-id → REQUIRED;
- polygon → PRODUCT/REQUIRED.

## 23. `all.sh`

Текущий `all.sh`:
- удаляет PBF/IMG/ZIP/GMAP перед работой;
- скачивает набор источников;
- переименовывает их;
- вызывает карты последовательной `&&`-цепочкой;
- содержит ошибку `/georgia.sh` вместо `./georgia.sh`.

Новая система не должна быть большим аналогом `all.sh`.

27 `.sh` должны превратиться в 27 записей конфигурации, а программа сборки должна быть одна.

## 24. Future build-manager

Предпочтительно написать менеджер на Python, а не на shell.

Причины:
- portability Linux/macOS;
- SQLite;
- process monitoring;
- locks;
- scheduling;
- resume/checkpoints;
- structured config;
- easier validation.

### 24.1. Ежедневный cron

Cron должен быть максимально тупым:
`раз в день → build-manager --due`

Build-manager сам проверяет:
- не работает ли предыдущий запуск;
- какие карты просрочены;
- какой приоритет;
- какие source datasets нужны.

Global lock делать через Python `fcntl.flock()` на Linux/macOS.

Если предыдущая сборка идёт — новый cron-run спокойно выходит.

### 24.2. Cadence

Периодичность хранится как свойство карты, а не в cron.

Например:
- weekly / 7 days;
- monthly / 30 days;
- quarterly / 90 days;
- manual.

Считать от `last_success`, а не от календарного первого числа.

Если build failed — `last_success` не обновляется, карта остаётся overdue и будет повторена на следующем запуске.

### 24.3. Priority + overdue

Главный порядок очереди:
1. priority;
2. насколько сильно карта просрочена.

Это пользователь одобрил как одну из главных идей.

Третьими критериями позже можно учитывать:
- shared source family;
- historical duration.

Но они не должны перепрыгивать пользовательский priority.

### 24.4. State / status

Хранить:
- last_attempt;
- last_success;
- status;
- duration;
- source_date;
- git commit;
- tool versions;
- output size;
- host.

Команда `--status` должна показывать примерно:
- OK;
- DUE;
- BUILDING;
- FAILED;
- due in N days;
- ETA.

### 24.5. Resume/checkpoints

Этапы:
1. source;
2. extract;
3. name/address preprocessing;
4. spatial preprocessing;
5. elevation merge;
6. splitter;
7. mkgmap tile compile;
8. Garmin package;
9. GMAPI package;
10. ZIP GMAPI;
11. validation;
12. publish.

Статусы:
- PENDING;
- RUNNING;
- SUCCESS;
- FAILED.

Возобновление только если signatures входов не изменились:
- source PBF;
- style/git commit;
- config;
- tool versions.

Если изменился source, downstream stages invalidated.

## 25. Метрики сборки

Каждая сборка должна быть не только production job, но и измерением.

Собирать для каждого этапа:
- wall_time;
- cpu_time;
- peak process RSS;
- peak process-tree RSS;
- minimum available system RAM;
- swap peak;
- major page faults;
- disk read bytes;
- disk write bytes;
- input size;
- output size;
- exit code;
- warning count.

Для splitter:
- max_nodes;
- max_threads;
- keep_complete;
- extract_strategy;
- tile count.

Для mkgmap:
- max_jobs;
- Java Xmx;
- dem_dists;
- tile count;
- gmapsupp size;
- gmapi size.

Сохранять характеристики хоста:
- hostname;
- OS/kernel;
- architecture;
- CPU model;
- logical CPUs;
- total RAM;
- swap;
- Java version;
- osmium version;
- osmosis version;
- splitter version;
- mkgmap version;
- Git commit.

Историю не удалять.

SQLite — предпочтительная база для состояния и статистики, например `state/builds.sqlite`.

Возможные таблицы:
- maps;
- builds;
- stages;
- artifacts;
- hosts;
- tool_versions.

Это позволит позже анализировать:
- median build time;
- влияние max-nodes;
- влияние max-jobs;
- swap/OOM;
- рост размера карт;
- success rate конфигурации.

## 26. Метрики future spatial engine

Полезные counters:
- km дорог, penalized by clearcut;
- km дорог вдоль power corridors;
- km дорог вдоль pipelines;
- railway pairs generalized;
- dual carriageway pairs generalized;
- urban POI demoted;
- rural POI promoted;
- wilderness POI promoted.

Это позволит выявлять слишком агрессивные heuristic rules без ручного просмотра всей карты.

## 27. Tool bootstrap / doctor / portability

Цель: после `git clone` не вспоминать вручную список зависимостей.

Новая система должна иметь:
- `bootstrap`;
- `doctor`.

Проверять/устанавливать системные инструменты:
- Java;
- osmium-tool;
- Osmosis;
- aria2;
- zip;
- Python dependencies;
- будущие spatial libraries.

Linux: apt.

macOS: Homebrew.

Сам Homebrew без подтверждения автоматически не устанавливать.

mkgmap и splitter предпочтительно хранить как pinned project tools, а не как глобальные пакеты:
`.tools/mkgmap/<version>/...`
`.tools/splitter/<version>/...`

Это даст одинаковые версии на Ubuntu и Mac.

`doctor` должен уметь показывать весь required environment до запуска карты.

## 28. Large data: DEM и elevation

DEM и готовые elevation PBF очень большие и не должны автоматически скачиваться build-manager.

Они заранее копируются/синхронизируются пользователем, сейчас для этого хорошо используется Syncthing. Есть резервная копия.

Считать их внешним data-root, например:
- Ubuntu: `/mnt/...`
- macOS: `/Volumes/...`

В конфиге машины один `URALLA_DATA`, а карты используют относительные paths внутри него.

`doctor` только проверяет наличие и разумный размер.

Полная checksum для огромных файлов — отдельная команда `verify-data`, а не каждый build.

## 29. Syncthing и публикация

Тяжёлые DEM/elevation можно синхронизировать через Syncthing.

Не синхронизировать:
- work;
- staging;
- tmp;
- splitter output.

У пользователя уже есть отдельная папка готовых карт. Скрипты после генерации переименовывают `gmapsupp.img` в имя карты и копируют туда. Эта папка через Syncthing синхронизируется с сервером, откуда пользователи скачивают карты.

Новая система должна сохранить этот принцип:
`build-manager → publish folder → Syncthing → server`

Build-manager не должен знать про сервер/SSH.

### 29.1. Atomic publish

Не удалять старый опубликованный файл заранее.

Новый файл:
- создаётся/копируется под временным именем;
- проверяется;
- атомарно переименовывается в final name.

`last_success` обновлять только после успешной публикации.

Если сборка завершилась, но publish failed — релиз считать failed.

### 29.2. Publish metadata

Рядом можно хранить `MapName.build.json`:
- built_at;
- source_date;
- host;
- git_commit;
- mkgmap_version;
- file_size;
- checksum.

Полезно, если production Ubuntu и MacBook потенциально могут публиковать одну карту.

Позже можно добавить защиту от замены более новой карты более старой.

## 30. ZIP policy

Исторический split ZIP (`-s990`, `-s=0`) был нужен из-за старого ограничения Яндекс.Диска на размер тома около 1 ГБ.

Это больше не нужно.

Принято окончательно:
- IMG вообще не архивировать;
- GMAPI/MapSource/BaseCamp архивировать в один ZIP только ради удобства скачивания;
- ZIP делать без сжатия (`-0`), потому что данные уже сжаты и дополнительная компрессия почти бессмысленна;
- никаких `.z01/.z02/...`.

Пример:
- `Topo-Ural-S.img`
- `Topo-Ural-S-ms.zip`
- optional `Topo-Ural-S.build.json`.

## 31. Source download policy

Старый `all.sh` удаляет PBF перед скачиванием — это плохо.

Новая схема:
- сохранять последний исправный source PBF;
- скачивать новый в `.part`;
- проверить `osmium fileinfo`, размер/timestamp;
- atomic rename на final filename;
- если download failed — старый source остаётся цел.

Scheduler сначала определяет DUE maps, потом скачивает только нужные source families.

Например, если due только Ural-S и Volga — скачать `russia-latest` один раз.

Если due только Turkey — не скачивать Россию.

## 32. Packaging split: compile once

Текущие args одновременно включают gmapsupp + gmapi + index, что может повышать peak memory.

Из документации mkgmap: index при одновременном gmapsupp и tdbfile/gmapi может потреблять существенно больше памяти.

Целевая архитектура:
- OSM tiles компилировать один раз;
- потом отдельный packaging для Garmin gmapsupp/index;
- отдельный packaging для GMAPI/tdb/index.

Нужно ещё подтвердить точные команды в используемой версии mkgmap и безопасную передачу compiled IMG + TYP в packaging-only runs.

## 33. `uralla.args` и `uralla-no-dem.args`

`uralla.args` содержит:
- gmapsupp;
- make-poi-index;
- code-page=1251;
- road-name-pois;
- route;
- process-destination/process-exits;
- make-cycleways;
- index;
- location-autofill;
- x-split-name-index;
- housenumbers;
- add-boundary-nodes;
- max-jobs=4;
- tdbfile;
- split-name-index;
- lower-case;
- gmapi;
- polygon density;
- simplify-lines;
- merge-lines;
- allow-reverse-merge;
- ignore-fixme-values;
- draw-priority;
- improve-overview;
- order-by-decreasing-area;
- cycle-map;
- link-pois-to-ways;
- keep-going;
- check-styles;
- DEM.

Принятые направления:
- `make-cycleways` устарел/неэффективен → убрать;
- `road-name-pois` убрать;
- `x-split-name-index` подозрительный/не документирован — предпочесть нормальный split-name-index;
- `make-poi-index` оставить;
- cp1251/lower-case пока оставить;
- `keep-going` убрать, production должен fail-fast;
- process destination/exits оставить;
- simplify-lines оставить;
- merge-lines оставить;
- reverse merge только с корректной поддержкой direction types;
- link-pois оставить;
- cycle-map пока оставить и позже проверить;
- args DEM/no-DEM должны отличаться только DEM-блоком.

Текущий `uralla-no-dem.args` уже успел разойтись с основным по другим параметрам — это надо устранить.

## 34. Family ID / Map ID registry

Нельзя просто красиво перенумеровывать существующие карты без необходимости: ID является частью Garmin identity.

Нужно создать центральный registry:
- family_id;
- map_id_start;
- реальный диапазон tile IDs после splitter.

Есть исторические схемы:
- некоторые карты имеют 8-digit style start, например `10220001`;
- часть восточных карт — 7-digit, например `1010001`, `1011001`, `1018001`.

Новый validator должен проверять фактический first/last tile ID и не допускать пересечений.

Хранить историю tile count и заранее предупреждать, если резерв диапазона заканчивается.

## 35. Active `.poly` vs reference `.poly`

В `poly/` есть как активные границы, так и старые/экспериментальные:
- `northwestern-fed-district2.poly`;
- `mongolia2.poly`;
- `far-eastern-fed-district.poly`;
- `siberian-fed-district.poly`;
- `south-ural.poly`;
- `ural-odd.poly`;
- `test.poly`;
- и др.

Наличие `.poly` не означает, что карту надо собирать.

Источник истины — `maps` config/manifest.

## 36. Предполагаемый map manifest

Пример структуры:

```yaml
id: ural-s
identity:
  family_id: 1022
  map_id_start: 10220001
product:
  name: Topo-Ural-S
  polygon: poly/ru_ural.poly
  language_profile: ru
source:
  id: russia
  extract_strategy: simple
elevation:
  file: elevation/ural.osm.pbf
  dem: true
schedule:
  cadence_days: 7
  priority: 100
splitter:
  keep_complete: true
  max_nodes: 500000   # initially legacy/test
publish:
  img: Topo-Ural-S.img
  gmapi_zip: Topo-Ural-S-ms.zip
```

Здесь надо явно отличать истинные свойства продукта от временных legacy overrides.

## 37. Current special scripts / anomalies

### Turkey
- `simple`;
- `keep-complete=false`;
- `max-nodes=800000`;
- no-dem args;
- `--latin1`;
- хороший baseline для A/B tests.

### Mongolia
- `smart`;
- `keep-complete=true`;
- `max-nodes=2000000`;
- no-dem args;
- `--latin1`;
- второй хороший baseline для A/B tests.

### Northwestern
- legacy source workaround;
- `max-nodes=400000`;
- no splitter polygon currently;
- dem poly есть;
- вернуть к russia-latest после тестов.

### Crimea
- `max-nodes=4000000`;
- `max-jobs=2` override;
- `ignore-osm-bounds=true`;
- исторические настройки, не считать автоматически правильными.

### Armenia
- `ignore-osm-bounds=true`;
- `max-nodes=2500000`;
- latin1.

### Kazakhstan
- max-nodes 500000;
- dem-dists 15000;
- CP1251.

### Polar Ural
- dem-dists 9942;
- current max-nodes 2000000.

## 38. Address rules

`styles/uralla/inc/address` — кастомная, сложная российская логика address inference.

Сохранять текущую российскую address philosophy до отдельных device/search tests.

Отдельно существует hack `opening_hours → addr:postcode`, который вреден для адресного индекса, но пока его не трогать до проверки на Garmin, потому что это исторически использовалось для UI.

## 39. Service/platform validation

После rewrite нужны автоматические проверки:
- style syntax/check-styles;
- TYP compile;
- emitted types vs TYP/drawOrder;
- map ID overlap;
- poly validity;
- required files;
- source timestamps;
- output existence/size;
- gmapsupp readable;
- GMAPI ZIP integrity;
- TYP family/codepage match;
- no stale `.partial` publication;
- no unexpected tool version drift.

## 40. `.gitignore`

Сейчас `.gitignore` содержит практически только `.DS_Store`.

Перед первой новой сборкой надо добавить исключения для:
- work;
- staging;
- cache;
- state/builds.sqlite;
- logs;
- `.tools` при необходимости;
- PBF;
- IMG;
- GMAP generated output;
- temporary downloads.

При этом `poly`, configs, preprocess code, styles и schema должны оставаться в Git.

## 41. Release changelog

После завершения большого релиза создать отдельный человекочитаемый файл изменений относительно старой версии.

Формат:
- короткий блок `Главные изменения` для Telegram;
- подробные разделы:
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
  - intentional unchanged behavior.

Имя файла выбрать по реальной версии релиза позже, не предполагать заранее.

## 42. Ближайшие шаги

Пока никаких больших правок в рабочие файлы не делать.

Следующие задачи аудита:
1. Закрыть полную матрицу всех 27 карт и классифицировать отличия как REQUIRED / PRODUCT / LEGACY-TEST / BUG-STALE.
2. Доделать точную схему label1/label2/display_name/full_name и international language profiles.
3. Закрыть packaging `compile once → Garmin → GMAPI` и TYP compile-from-text workflow.
4. Закрыть mechanical inventory lines/points/TYP аналогично polygon A/B/C.
5. Проверить transform_places и boundary/address взаимодействие.
6. Проверить product boundary handling у разных карт, особенно Northwestern multipart.
7. После полного аудита создать рабочую ветку и сделать один согласованный набор изменений.
8. После первого стабильного нового build-manager начать собирать метрики и только на их основе менять legacy max-nodes/max-jobs/keep-complete/strategy overrides.

## 43. Главный дух проекта

Карта должна быть не просто ещё одним OSM render.

Цель — туристически ориентированный продукт, который:
- использует OSM-семантику аккуратно;
- умеет учитывать реальный контекст;
- делает wilderness POI полезнее;
- уменьшает городской мусор;
- улучшает велосипедную и пешую маршрутизацию;
- сохраняет чистую границу каждой продуктовой карты;
- остаётся воспроизводимым и переносимым между Ubuntu и macOS;
- сам знает свои зависимости;
- сам следит за расписанием;
- сам собирает статистику собственной работы;
- и со временем становится проще поддерживать, а не сложнее.
