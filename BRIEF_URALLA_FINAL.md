# BRIEF_URALLA_FINAL.md

## Полный бриф финализации стиля mkgmap `uralla`

**Дата:** 2026-08-20  
**Статус:** финальный бриф для внесения правок  
**Цель:** единый источник истины для всех изменений в стиле `uralla`

---

## 1. ОБЩИЕ ПРИНЦИПЫ

1. **Не трогаем XPM** — пока не увидим в TYPViewer
2. **Не трогаем жёсткие списки** — они нужны для LOD
3. **Не трогаем `cycle-map`** — оставляем
4. **Не трогаем речную маршрутизацию** — оставляем
5. **Не трогаем нерелевантные страны** — оставляем на будущее
6. **Все закомментированные правила собираем в конце файлов** с категориями
7. **Ночные варианты TYP удаляем полностью**

---

## 2. КРИТИЧЕСКИЕ БАГИ (пункты 1-4)

### Пункт 1: `surface=paved` в списках «гравийка» и «грунтовка»

**Файл:** `lines`  
**Строки:** 589, 594

**Действие:** Убрать `surface=paved` из списков поверхностей для подписей «гравийка», «плохая гравийка», «грунтовка», «плохая грунтовка».

**Было:**

surface=gravel|surface=compacted|surface=paved|surface=pebblestone|surface=fine_gravel
text


**Стало:**

surface=gravel|surface=compacted|surface=pebblestone|surface=fine_gravel
text


---

### Пункт 2: АЗС без `continue`

**Файл:** `points`  
**Строка:** ~178

**Действие:** Добавить `continue` к правилу `amenity=fuel` и удалить мёртвые правила.

**Было:**

amenity=fuel [0x2f01 resolution 24]
amenity=fuel & fuel:HGV_diesel=yes [0x2f16 resolution 24]
amenity=fuel & shop=convenience [0x2e06 resolution 24]
text


**Стало:**

amenity=fuel | waterway=fuel [0x2f01 resolution 24 continue]
text


**Примечание:** Правила `fuel:HGV_diesel=yes` и `shop=convenience` **удалить**.

---

### Пункт 3: Пустые имена для memorial и signpost

**Файл:** `points`  
**Строки:** ~263, ~442

**Действие:** Добавить фолбэк (значение по умолчанию).

**Было:**

historic=memorial {name '{inscription}'} amenity=signpost {name '{label}'}
text


**Стало:**

historic=memorial {name '{inscription}' | 'памятник'} amenity=signpost {name '{label}' | 'указатель'}
text


---

### Пункт 4: Дубликат TYP-типа `0x10f09`

**Файл:** `uralla.txt`  
**Строка:** 76

**Действие:** Удалить второе вхождение.

**Было:**

Type=0x10f09,10
text


**Стало:**

удалено — дубликат (2026-08-20)
text


---

## 3. ВАЖНЫЕ ИЗМЕНЕНИЯ (пункты 5-12)

### Пункт 5: Конфликт polygon vs line для `0x10f09` и `0x10f05`

**Файлы:** `lines`, `polygons`, `uralla.txt`

**Действие:** Разнести семантически разные объекты по разным TYP-типам (Вариант А).

| Текущий тип | Полигон (оставить) | Линия (новый тип) |
|-------------|-------------------|-------------------|
| `0x10f09` | `0x10f09` — «частная территория» | `0x10f1a` — «лесная полоса» |
| `0x10f05` | `0x10f05` — «пожарная часть» | `0x10f1b` — «железная дорога» |

**В `lines` заменить:**

natural=tree_row & length()>100 [0x10f09 resolution 23-24]
text

**на:**

natural=tree_row & area!=yes & length()>100 [0x10f1a resolution 23-24]
text

railway=narrow_gauge [0x10f05 resolution 22-24]
text

**на:**

railway=narrow_gauge [0x10f1b resolution 22-24]
text

railway=rail & service=* & length()>500 [0x10f05 resolution 23-23 continue]
railway=rail & service=* [0x10f05 resolution 24]
text

**на:**

railway=rail & service=* & length()>500 [0x10f1b resolution 23-23 continue]
railway=rail & service=* [0x10f1b resolution 24]
text


**В `polygons`:** Убедиться, что `0x10f09` и `0x10f05` используются только как полигоны.

**В `uralla.txt`:** Удалить старые `_line` секции для `0x10f09` и `0x10f05`, добавить новые:

[_line]
Type=0x10f1a
; лесная полоса / tree row
UseOrientation=Y
LineWidth=2
Xpm="0 0 1 0"
"1 c #7BCA6A"
String1=0x19,лесная полоса
ExtendedLabels=N
[end]

[_line]
Type=0x10f1b
; железная дорога (служебная, узкоколейная)
UseOrientation=Y
Xpm="32 3 2 1"
"! c #313131"
"# c #FFFFFF"
"###!!!!!!!!########!!!!!!!!#####"
"###!!!!!!!!########!!!!!!!!#####"
"###!!!!!!!!########!!!!!!!!#####"
String1=0x19,ж/д (служебная)
String2=0x04,railroad
ExtendedLabels=Y
FontStyle=NoLabel (invisible)
CustomColor=No
ContourColor=No
[end]
text


---

### Пункт 6: Некорректные кодировки в TYP

**Файл:** `uralla.txt`

**Действие:** Пересохранить файл с кодировкой Windows-1251, все русские строки должны быть читаемыми.

**Примеры исправлений:**
- `–≥–æ—Ä–æ–¥` → `город`
- `–Ω–∞—Å–µ–ª—ë–Ω–∫–∞` → `населёнка`
- `–∑–∞–ø—Ä–µ—Ç–Ω–∞—è –∑–æ–Ω–∞` → `запретная зона`

---

### Пункт 7: XPM-текстуры

**Статус:** ОТЛОЖЕНО  
**Действие:** Не трогать до визуального контроля в TYPViewer.

---

### Пункт 8: Мёртвый код (закомментированные правила)

**Файлы:** `points`, `lines`, `polygons`

**Действие:** Собрать все закомментированные правила в конце каждого файла, добавить категории.

**Структура:**

============================================================
[DEPRECATED] Устаревшие правила — перенесены в конец файла
============================================================
---- HIGHWAY (устаревшие теги) ----
highway=unsurfaced {set highway=track}
...
---- SHOP (экспериментальные) ----
shop=electronics [0x10f0c resolution 24]
...
---- AMENITY (экспериментальные) ----
amenity=bar [0x2d02 resolution 24]
...
text


---

### Пункт 9: `cycle-map`

**Файлы:** `uralla.args`, `uralla-no-dem.args`

**Действие:** Оставить как есть.

---

### Пункт 10: `make-cycleways`

**Файлы:** `uralla.args`, `uralla-no-dem.args`

**Действие:** Удалить устаревшую опцию.

**Было:**

make-cycleways
text


**Стало:**

make-cycleways # удалено — опция устарела (2026-08-20)
text


---

### Пункт 11: Объединение `waterway=fuel` с `amenity=fuel`

**Файл:** `points`

**Действие:** Объединить в одно правило.

**Было:**

amenity=fuel [0x2f01 resolution 24 continue]
waterway=fuel [0x2f01 resolution 24]
text


**Стало:**

amenity=fuel | waterway=fuel [0x2f01 resolution 24 continue]
text


---

### Пункт 12: Удаление ночных вариантов TYP

**Файл:** `uralla.txt`

**Действие:** Удалить полностью.

1. Удалить все `NightXpm` секции из `_point` определений
2. Удалить все `NightcustomColor` из `_line` определений
3. Заменить все `CustomColor=DayAndNight` на `CustomColor=Day`

---

## 4. ОПТИМИЗАЦИОННЫЕ ИЗМЕНЕНИЯ (пункты 13-17)

### Пункт 13: Консолидация ресторанов

**Файл:** `points`  
**Строки:** ~150-234

**Действие:** Заменить 27 правил на одно.

**Было:**

amenity=restaurant [0x2a00 resolution 24]
amenity=restaurant & cuisine=american [0x2a01 resolution 24]
amenity=restaurant & cuisine=asian [0x2a02 resolution 24]
... (все 27 правил)
text


**Стало:**

amenity=restaurant | amenity=cafe | amenity=fast_food | amenity=food_court [0x2a00 resolution 24]
text


**TYP-типы на удаление:** `0x2a01`-`0x2a17` (23 типа)

---

### Пункт 14: Консолидация продуктовых магазинов

**Файл:** `points`  
**Строки:** ~329-363

**Действие:** Заменить 7 правил на одно.

**Было:**

shop=supermarket [0x2e02 resolution 24]
shop=convenience [0x2e06 resolution 24]
shop=general [0x2e03 resolution 24]
shop=bakery [0x2e02 resolution 24]
shop=bakers [0x2e02 resolution 24]
shop=butcher [0x2e0c resolution 24]
shop=organic [0x2e0a resolution 24]
text


**Стало:**

shop=supermarket | shop=convenience | shop=general | shop=bakery | shop=bakers | shop=butcher | shop=organic [0x2e02 resolution 24]
text


**TYP-типы на удаление:** `0x2e03`, `0x2e06`, `0x2e0a`, `0x2e0c`

---

### Пункт 15: Консолидация прочих магазинов

**Файл:** `points`

**Действие:** Оставить отдельно аптеку и велосипеды, всё остальное объединить.

**Было:** множество правил для разных типов магазинов.

**Стало:**

---- АПТЕКА (оставлена отдельно) ----

shop=chemist [0x2e05 resolution 24]
---- ВЕЛОСИПЕДЫ (оставлены отдельно) ----

shop=bicycle [0x2f13 resolution 24]
---- ВСЕ ОСТАЛЬНЫЕ МАГАЗИНЫ ----

shop=* & shop!=no & shop!=none & shop!=chemist & shop!=bicycle & shop!=supermarket & shop!=convenience & shop!=general & shop!=bakery & shop!=bakers & shop!=butcher & shop!=organic [0x2e00 resolution 24]
text


**TYP-типы на удаление:** `0x2e01`, `0x2e04`, `0x2e07`, `0x2e08`, `0x2e09`, `0x2e0b`, `0x2f03`, `0x2f07`, `0x2f0d`, `0x2f10`, `0x2f13` (для мотор-транспорта), и другие

---

### Пункт 16: Локализация английских названий

**Файл:** `inc/name`

**Действие:** Заменить английские названия на русские.

**Было:**

'Embassy' → 'Embassy'
'Services' → 'Services'
'Telephone' → 'Telephone'
'Toilets' → 'Toilets'
'Diesel/LPG' → 'Diesel/LPG'
text


**Стало:**

'Embassy' → 'Посольство'
'Services' → 'Сервис'
'Telephone' → 'Телефон'
'Toilets' → 'Туалет'
'Diesel/LPG' → 'Дизель/Газ'
text


---

### Пункт 17: Удаление `overlays`

**Файл:** `overlays`

**Действие:** Удалить пустой файл.

---

## 5. ИЗМЕНЕНИЯ В АРГУМЕНТАХ СБОРКИ (пункты 9-10)

### Пункт 9: `cycle-map`

**Файлы:** `uralla.args`, `uralla-no-dem.args`

**Действие:** Оставить как есть.

---

### Пункт 10: `make-cycleways`

**Файлы:** `uralla.args`, `uralla-no-dem.args`

**Действие:** Удалить строку.

**Было:**

make-cycleways
text


**Стало:**

make-cycleways # удалено — опция устарела (2026-08-20)
text


---

## 6. TYP-ФАЙЛ (пункты 4, 5, 6, 12)

### Сводка изменений в `uralla.txt`

| Пункт | Действие |
|-------|----------|
| 4 | Удалить дубликат `Type=0x10f09,10` из `_drawOrder` |
| 5 | Удалить старые `_line` секции для `0x10f09` и `0x10f05`, добавить `0x10f1a` и `0x10f1b` |
| 6 | Пересохранить в Windows-1251, исправить все русские строки |
| 12 | Удалить `NightXpm`, `NightcustomColor`, заменить `DayAndNight` на `Day` |

---

## 7. ЧТО НЕ МЕНЯЕМ

| № | Что | Причина |
|---|-----|---------|
| 1 | XPM-текстуры | Отложено до визуального контроля |
| 2 | Жёсткие списки имён (реки, вершины, М-5) | Намеренный LOD |
| 3 | `cycle-map` | Оставляем |
| 4 | Речная маршрутизация через `taxi` | Полезно для водных туристов |
| 5 | Нерелевантные страны | Оставляем на будущее |
| 6 | `length()` правила | Намеренная генерализация |
| 7 | `highway=path → cycleway` при `bicycle=designated` | Намеренная вело-логика |

---

## 8. ПОРЯДОК ВНЕСЕНИЯ ПРАВОК

### Этап 1: Критические баги (пункты 1-4)
1. Исправить `lines` — убрать `surface=paved`
2. Исправить `points` — добавить `continue` к АЗС, удалить мёртвые правила
3. Исправить `points` — добавить фолбэки для memorial и signpost
4. Исправить `uralla.txt` — удалить дубликат `0x10f09`

### Этап 2: TYP и важные изменения (пункты 5-6, 12)
5. Исправить `uralla.txt` — разнести типы, добавить `0x10f1a` и `0x10f1b`
6. Исправить `uralla.txt` — удалить ночные варианты
7. Пересохранить `uralla.txt` в Windows-1251

### Этап 3: Консолидация POI (пункты 13-15)
8. Исправить `points` — консолидировать рестораны
9. Исправить `points` — консолидировать продукты
10. Исправить `points` — консолидировать прочие магазины

### Этап 4: Мелкие правки (пункты 10, 16, 17)
11. Исправить `inc/name` — локализовать английские названия
12. Исправить `uralla.args` и `uralla-no-dem.args` — удалить `make-cycleways`
13. Удалить `overlays`

### Этап 5: Чистка мёртвого кода (пункт 8)
14. Исправить `points` — собрать закомментированные правила в конце
15. Исправить `lines` — собрать закомментированные правила в конце
16. Исправить `polygons` — собрать закомментированные правила в конце

### Этап 6: Проверка и компиляция
17. Проверить все изменения
18. Перекомпилировать TYP из `uralla.txt` в `uralla.typ`
19. Провести тестовую сборку карты

---

## 📋 КОНТРОЛЬНЫЙ СПИСОК

- [ ] `surface=paved` удалён из списков гравийки и грунтовки (`lines`)
- [ ] АЗС объединены с `continue` (`points`)
- [ ] Фолбэки для memorial и signpost добавлены (`points`)
- [ ] Дубликат `0x10f09` удалён из `_drawOrder` (`uralla.txt`)
- [ ] Добавлены новые типы `0x10f1a` и `0x10f1b` (`uralla.txt`, `lines`)
- [ ] Старые `_line` секции для `0x10f09` и `0x10f05` удалены (`uralla.txt`)
- [ ] Ночные варианты удалены (`uralla.txt`)
- [ ] `uralla.txt` пересохранён в Windows-1251
- [ ] Рестораны консолидированы (`points`)
- [ ] Продуктовые магазины консолидированы (`points`)
- [ ] Прочие магазины консолидированы (`points`)
- [ ] Английские названия локализованы (`inc/name`)
- [ ] `make-cycleways` удалён (`uralla.args`, `uralla-no-dem.args`)
- [ ] `overlays` удалён
- [ ] Закомментированные правила собраны в конце файлов (`points`, `lines`, `polygons`)

---

**Конец брифа.**

📥 Как сохранить файл

    Скопируйте весь текст выше (включая ```markdown и ```)

    Откройте любой текстовый редактор (Блокнот, Notepad++, VS Code)

    Вставьте текст

    Сохраните как BRIEF_URALLA_FINAL.md

    Загрузите этот файл обратно в чат

Файл готов для загрузки.
у тебя опять не один файл, а несколько отдельных блоков. Сделай мне в одном файле всё

Понял! Вот один цельный файл для скачивания. Копируйте весь текст от начала до конца и сохраните как BRIEF_URALLA_FINAL.md.
markdown

# BRIEF_URALLA_FINAL.md

## Полный бриф финализации стиля mkgmap `uralla`

**Дата:** 2026-08-20  
**Статус:** финальный бриф для внесения правок  
**Цель:** единый источник истины для всех изменений в стиле `uralla`

---

## 1. ОБЩИЕ ПРИНЦИПЫ

1. **Не трогаем XPM** — пока не увидим в TYPViewer
2. **Не трогаем жёсткие списки** — они нужны для LOD
3. **Не трогаем `cycle-map`** — оставляем
4. **Не трогаем речную маршрутизацию** — оставляем
5. **Не трогаем нерелевантные страны** — оставляем на будущее
6. **Все закомментированные правила собираем в конце файлов** с категориями
7. **Ночные варианты TYP удаляем полностью**

---

## 2. КРИТИЧЕСКИЕ БАГИ (пункты 1-4)

### Пункт 1: `surface=paved` в списках «гравийка» и «грунтовка»

**Файл:** `lines`  
**Строки:** 589, 594

**Действие:** Убрать `surface=paved` из списков поверхностей для подписей «гравийка», «плохая гравийка», «грунтовка», «плохая грунтовка».

**Было:**

surface=gravel|surface=compacted|surface=paved|surface=pebblestone|surface=fine_gravel
text


**Стало:**

surface=gravel|surface=compacted|surface=pebblestone|surface=fine_gravel
text


---

### Пункт 2: АЗС без `continue`

**Файл:** `points`  
**Строка:** ~178

**Действие:** Добавить `continue` к правилу `amenity=fuel` и удалить мёртвые правила.

**Было:**

amenity=fuel [0x2f01 resolution 24]
amenity=fuel & fuel:HGV_diesel=yes [0x2f16 resolution 24]
amenity=fuel & shop=convenience [0x2e06 resolution 24]
text


**Стало:**

amenity=fuel | waterway=fuel [0x2f01 resolution 24 continue]
text


**Примечание:** Правила `fuel:HGV_diesel=yes` и `shop=convenience` **удалить**.

---

### Пункт 3: Пустые имена для memorial и signpost

**Файл:** `points`  
**Строки:** ~263, ~442

**Действие:** Добавить фолбэк (значение по умолчанию).

**Было:**

historic=memorial {name '{inscription}'} amenity=signpost {name '{label}'}
text


**Стало:**

historic=memorial {name '{inscription}' | 'памятник'} amenity=signpost {name '{label}' | 'указатель'}
text


---

### Пункт 4: Дубликат TYP-типа `0x10f09`

**Файл:** `uralla.txt`  
**Строка:** 76

**Действие:** Удалить второе вхождение.

**Было:**

Type=0x10f09,10
text


**Стало:**

удалено — дубликат (2026-08-20)
text


---

## 3. ВАЖНЫЕ ИЗМЕНЕНИЯ (пункты 5-12)

### Пункт 5: Конфликт polygon vs line для `0x10f09` и `0x10f05`

**Файлы:** `lines`, `polygons`, `uralla.txt`

**Действие:** Разнести семантически разные объекты по разным TYP-типам (Вариант А).

| Текущий тип | Полигон (оставить) | Линия (новый тип) |
|-------------|-------------------|-------------------|
| `0x10f09` | `0x10f09` — «частная территория» | `0x10f1a` — «лесная полоса» |
| `0x10f05` | `0x10f05` — «пожарная часть» | `0x10f1b` — «железная дорога» |

**В `lines` заменить:**

natural=tree_row & length()>100 [0x10f09 resolution 23-24]
text

**на:**

natural=tree_row & area!=yes & length()>100 [0x10f1a resolution 23-24]
text

railway=narrow_gauge [0x10f05 resolution 22-24]
text

**на:**

railway=narrow_gauge [0x10f1b resolution 22-24]
text

railway=rail & service=* & length()>500 [0x10f05 resolution 23-23 continue]
railway=rail & service=* [0x10f05 resolution 24]
text

**на:**

railway=rail & service=* & length()>500 [0x10f1b resolution 23-23 continue]
railway=rail & service=* [0x10f1b resolution 24]
text


**В `polygons`:** Убедиться, что `0x10f09` и `0x10f05` используются только как полигоны.

**В `uralla.txt`:** Удалить старые `_line` секции для `0x10f09` и `0x10f05`, добавить новые:

[_line]
Type=0x10f1a
; лесная полоса / tree row
UseOrientation=Y
LineWidth=2
Xpm="0 0 1 0"
"1 c #7BCA6A"
String1=0x19,лесная полоса
ExtendedLabels=N
[end]

[_line]
Type=0x10f1b
; железная дорога (служебная, узкоколейная)
UseOrientation=Y
Xpm="32 3 2 1"
"! c #313131"
"# c #FFFFFF"
"###!!!!!!!!########!!!!!!!!#####"
"###!!!!!!!!########!!!!!!!!#####"
"###!!!!!!!!########!!!!!!!!#####"
String1=0x19,ж/д (служебная)
String2=0x04,railroad
ExtendedLabels=Y
FontStyle=NoLabel (invisible)
CustomColor=No
ContourColor=No
[end]
text


---

### Пункт 6: Некорректные кодировки в TYP

**Файл:** `uralla.txt`

**Действие:** Пересохранить файл с кодировкой Windows-1251, все русские строки должны быть читаемыми.

**Примеры исправлений:**
- `–≥–æ—Ä–æ–¥` → `город`
- `–Ω–∞—Å–µ–ª—ë–Ω–∫–∞` → `населёнка`
- `–∑–∞–ø—Ä–µ—Ç–Ω–∞—è –∑–æ–Ω–∞` → `запретная зона`

---

### Пункт 7: XPM-текстуры

**Статус:** ОТЛОЖЕНО  
**Действие:** Не трогать до визуального контроля в TYPViewer.

---

### Пункт 8: Мёртвый код (закомментированные правила)

**Файлы:** `points`, `lines`, `polygons`

**Действие:** Собрать все закомментированные правила в конце каждого файла, добавить категории.

**Структура:**

============================================================
[DEPRECATED] Устаревшие правила — перенесены в конец файла
============================================================
---- HIGHWAY (устаревшие теги) ----
highway=unsurfaced {set highway=track}
...
---- SHOP (экспериментальные) ----
shop=electronics [0x10f0c resolution 24]
...
---- AMENITY (экспериментальные) ----
amenity=bar [0x2d02 resolution 24]
...
text


---

### Пункт 9: `cycle-map`

**Файлы:** `uralla.args`, `uralla-no-dem.args`

**Действие:** Оставить как есть.

---

### Пункт 10: `make-cycleways`

**Файлы:** `uralla.args`, `uralla-no-dem.args`

**Действие:** Удалить устаревшую опцию.

**Было:**

make-cycleways
text


**Стало:**

make-cycleways # удалено — опция устарела (2026-08-20)
text


---

### Пункт 11: Объединение `waterway=fuel` с `amenity=fuel`

**Файл:** `points`

**Действие:** Объединить в одно правило.

**Было:**

amenity=fuel [0x2f01 resolution 24 continue]
waterway=fuel [0x2f01 resolution 24]
text


**Стало:**

amenity=fuel | waterway=fuel [0x2f01 resolution 24 continue]
text


---

### Пункт 12: Удаление ночных вариантов TYP

**Файл:** `uralla.txt`

**Действие:** Удалить полностью.

1. Удалить все `NightXpm` секции из `_point` определений
2. Удалить все `NightcustomColor` из `_line` определений
3. Заменить все `CustomColor=DayAndNight` на `CustomColor=Day`

---

## 4. ОПТИМИЗАЦИОННЫЕ ИЗМЕНЕНИЯ (пункты 13-17)

### Пункт 13: Консолидация ресторанов

**Файл:** `points`  
**Строки:** ~150-234

**Действие:** Заменить 27 правил на одно.

**Было:**

amenity=restaurant [0x2a00 resolution 24]
amenity=restaurant & cuisine=american [0x2a01 resolution 24]
amenity=restaurant & cuisine=asian [0x2a02 resolution 24]
... (все 27 правил)
text


**Стало:**

amenity=restaurant | amenity=cafe | amenity=fast_food | amenity=food_court [0x2a00 resolution 24]
text


**TYP-типы на удаление:** `0x2a01`-`0x2a17` (23 типа)

---

### Пункт 14: Консолидация продуктовых магазинов

**Файл:** `points`  
**Строки:** ~329-363

**Действие:** Заменить 7 правил на одно.

**Было:**

shop=supermarket [0x2e02 resolution 24]
shop=convenience [0x2e06 resolution 24]
shop=general [0x2e03 resolution 24]
shop=bakery [0x2e02 resolution 24]
shop=bakers [0x2e02 resolution 24]
shop=butcher [0x2e0c resolution 24]
shop=organic [0x2e0a resolution 24]
text


**Стало:**

shop=supermarket | shop=convenience | shop=general | shop=bakery | shop=bakers | shop=butcher | shop=organic [0x2e02 resolution 24]
text


**TYP-типы на удаление:** `0x2e03`, `0x2e06`, `0x2e0a`, `0x2e0c`

---

### Пункт 15: Консолидация прочих магазинов

**Файл:** `points`

**Действие:** Оставить отдельно аптеку и велосипеды, всё остальное объединить.

**Было:** множество правил для разных типов магазинов.

**Стало:**

---- АПТЕКА (оставлена отдельно) ----

shop=chemist [0x2e05 resolution 24]
---- ВЕЛОСИПЕДЫ (оставлены отдельно) ----

shop=bicycle [0x2f13 resolution 24]
---- ВСЕ ОСТАЛЬНЫЕ МАГАЗИНЫ ----

shop=* & shop!=no & shop!=none & shop!=chemist & shop!=bicycle & shop!=supermarket & shop!=convenience & shop!=general & shop!=bakery & shop!=bakers & shop!=butcher & shop!=organic [0x2e00 resolution 24]
text


**TYP-типы на удаление:** `0x2e01`, `0x2e04`, `0x2e07`, `0x2e08`, `0x2e09`, `0x2e0b`, `0x2f03`, `0x2f07`, `0x2f0d`, `0x2f10`, `0x2f13` (для мотор-транспорта), и другие

---

### Пункт 16: Локализация английских названий

**Файл:** `inc/name`

**Действие:** Заменить английские названия на русские.

**Было:**

'Embassy' → 'Embassy'
'Services' → 'Services'
'Telephone' → 'Telephone'
'Toilets' → 'Toilets'
'Diesel/LPG' → 'Diesel/LPG'
text


**Стало:**

'Embassy' → 'Посольство'
'Services' → 'Сервис'
'Telephone' → 'Телефон'
'Toilets' → 'Туалет'
'Diesel/LPG' → 'Дизель/Газ'
text


---

### Пункт 17: Удаление `overlays`

**Файл:** `overlays`

**Действие:** Удалить пустой файл.

---

## 5. ЧТО НЕ МЕНЯЕМ

| № | Что | Причина |
|---|-----|---------|
| 1 | XPM-текстуры | Отложено до визуального контроля |
| 2 | Жёсткие списки имён (реки, вершины, М-5) | Намеренный LOD |
| 3 | `cycle-map` | Оставляем |
| 4 | Речная маршрутизация через `taxi` | Полезно для водных туристов |
| 5 | Нерелевантные страны | Оставляем на будущее |
| 6 | `length()` правила | Намеренная генерализация |
| 7 | `highway=path → cycleway` при `bicycle=designated` | Намеренная вело-логика |

---

## 6. ПОРЯДОК ВНЕСЕНИЯ ПРАВОК

### Этап 1: Критические баги (пункты 1-4)
1. Исправить `lines` — убрать `surface=paved`
2. Исправить `points` — добавить `continue` к АЗС, удалить мёртвые правила
3. Исправить `points` — добавить фолбэки для memorial и signpost
4. Исправить `uralla.txt` — удалить дубликат `0x10f09`

### Этап 2: TYP и важные изменения (пункты 5-6, 12)
5. Исправить `uralla.txt` — разнести типы, добавить `0x10f1a` и `0x10f1b`
6. Исправить `uralla.txt` — удалить ночные варианты
7. Пересохранить `uralla.txt` в Windows-1251

### Этап 3: Консолидация POI (пункты 13-15)
8. Исправить `points` — консолидировать рестораны
9. Исправить `points` — консолидировать продукты
10. Исправить `points` — консолидировать прочие магазины

### Этап 4: Мелкие правки (пункты 10, 16, 17)
11. Исправить `inc/name` — локализовать английские названия
12. Исправить `uralla.args` и `uralla-no-dem.args` — удалить `make-cycleways`
13. Удалить `overlays`

### Этап 5: Чистка мёртвого кода (пункт 8)
14. Исправить `points` — собрать закомментированные правила в конце
15. Исправить `lines` — собрать закомментированные правила в конце
16. Исправить `polygons` — собрать закомментированные правила в конце

### Этап 6: Проверка и компиляция
17. Проверить все изменения
18. Перекомпилировать TYP из `uralla.txt` в `uralla.typ`
19. Провести тестовую сборку карты

---

## 7. ТАБЛИЦА ВСЕХ ИЗМЕНЕНИЙ

| № | Пункт | Файл | Действие | Статус |
|---|-------|------|----------|--------|
| 1 | surface=paved | lines | Убрать surface=paved | ✅ |
| 2 | АЗС без continue | points | Добавить continue, удалить мёртвые | ✅ |
| 3 | Пустые имена | points | Добавить фолбэки | ✅ |
| 4 | Дубликат TYP | uralla.txt | Удалить второе вхождение | ✅ |
| 5 | Polygon vs line | lines, polygons, uralla.txt | Разнести типы, добавить 0x10f1a, 0x10f1b | ✅ |
| 6 | Кодировки TYP | uralla.txt | Пересохранить в Windows-1251 | ✅ |
| 7 | XPM-текстуры | uralla.txt | ОТЛОЖЕНО | ⏳ |
| 8 | Мёртвый код | points, lines, polygons | Собрать в конце с категориями | ✅ |
| 9 | cycle-map | uralla.args, uralla-no-dem.args | Оставить | ✅ |
| 10 | make-cycleways | uralla.args, uralla-no-dem.args | Удалить | ✅ |
| 11 | waterway=fuel | points | Объединить с amenity=fuel | ✅ |
| 12 | Ночные варианты TYP | uralla.txt | Удалить полностью | ✅ |
| 13 | Рестораны | points | Консолидировать в 0x2a00 | ✅ |
| 14 | Продукты | points | Консолидировать в 0x2e02 | ✅ |
| 15 | Прочие магазины | points | Консолидировать, оставить аптеку и велосипеды | ✅ |
| 16 | Локализация | inc/name | Заменить на русские | ✅ |
| 17 | overlays | overlays | Удалить файл | ✅ |

---

## 8. КОНТРОЛЬНЫЙ СПИСОК

- [ ] `surface=paved` удалён из списков гравийки и грунтовки (`lines`)
- [ ] АЗС объединены с `continue` (`points`)
- [ ] Фолбэки для memorial и signpost добавлены (`points`)
- [ ] Дубликат `0x10f09` удалён из `_drawOrder` (`uralla.txt`)
- [ ] Добавлены новые типы `0x10f1a` и `0x10f1b` (`uralla.txt`, `lines`)
- [ ] Старые `_line` секции для `0x10f09` и `0x10f05` удалены (`uralla.txt`)
- [ ] Ночные варианты удалены (`uralla.txt`)
- [ ] `uralla.txt` пересохранён в Windows-1251
- [ ] Рестораны консолидированы (`points`)
- [ ] Продуктовые магазины консолидированы (`points`)
- [ ] Прочие магазины консолидированы (`points`)
- [ ] Английские названия локализованы (`inc/name`)
- [ ] `make-cycleways` удалён (`uralla.args`, `uralla-no-dem.args`)
- [ ] `overlays` удалён
- [ ] Закомментированные правила собраны в конце файлов (`points`, `lines`, `polygons`)

---

**Конец брифа.**