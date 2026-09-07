#!/usr/bin/env python3
import argparse
import csv
import re
from collections import Counter
from pathlib import Path

import osmium


WORD_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁё]+(?:[-’'][0-9A-Za-zА-Яа-яЁё]+)*")


class RouteCollector(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.names = Counter()
        self.words = Counter()
        self.route_types = Counter()

    def relation(self, relation):
        tags = relation.tags
        if tags.get("type") != "route":
            return

        name = tags.get("name")
        if not name:
            return

        route = tags.get("route", "")
        ref = tags.get("ref", "")
        network = tags.get("network", "")

        self.rows.append((relation.id, route, network, ref, name))
        self.names[name] += 1
        self.route_types[route or "(без route=*)"] += 1

        for word in WORD_RE.findall(name):
            self.words[word.casefold()] += 1


def main():
    parser = argparse.ArgumentParser(
        description="Собрать названия всех type=route relations из OSM PBF."
    )
    parser.add_argument("pbf", type=Path, help="Например: russia-latest.osm.pbf")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("route_names_analysis"),
        help="Каталог результатов (по умолчанию route_names_analysis)",
    )
    args = parser.parse_args()

    if not args.pbf.is_file():
        raise SystemExit(f"Файл не найден: {args.pbf}")

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    collector = RouteCollector()
    print(f"Читаю {args.pbf} ...")
    collector.apply_file(str(args.pbf), locations=False)

    rows = sorted(
        collector.rows,
        key=lambda item: (item[1].casefold(), item[4].casefold(), item[0]),
    )

    with (out / "routes.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["relation_id", "route", "network", "ref", "name"])
        writer.writerows(rows)

    with (out / "route_names_unique.txt").open("w", encoding="utf-8") as handle:
        for name in sorted(collector.names, key=str.casefold):
            handle.write(f"{collector.names[name]}\t{name}\n")

    with (out / "route_name_words.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["count", "word"])
        for word, count in collector.words.most_common():
            writer.writerow([count, word])

    with (out / "route_types.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["count", "route"])
        for route, count in collector.route_types.most_common():
            writer.writerow([count, route])

    print(f"Готово. Именованных route-relations: {len(rows):,}")
    print(f"Уникальных названий: {len(collector.names):,}")
    print(f"Результаты: {out.resolve()}")
    print("  routes.tsv             — полный список")
    print("  route_names_unique.txt — уникальные названия + число повторов")
    print("  route_name_words.tsv   — частота слов в названиях")
    print("  route_types.tsv        — статистика по route=*")


if __name__ == "__main__":
    main()
