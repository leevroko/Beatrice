#!/usr/bin/env python3
"""
Beatrice CLI — транзактные операции над графом знаний.

Формат хранения: JSON node-link (nx.node_link_data / nx.node_link_graph).
Все команды: читают JSON → NetworkX → модифицируют → пишут JSON.
"""

import json
import re
import sys
from pathlib import Path
from argparse import ArgumentParser, RawDescriptionHelpFormatter

# Добавляем корень проекта в sys.path для импорта модулей
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import networkx as nx


class BeatriceError(Exception):
    """Пользовательская ошибка Beatrice с человекочитаемым сообщением."""
    pass


def load_graph(path: str) -> nx.DiGraph:
    """Читает JSON-граф, возвращает NetworkX граф.

    Raises:
        BeatriceError: если файл не найден, битый JSON или не является графом.
    """
    p = Path(path)
    if not p.exists():
        raise BeatriceError(f"Файл не найден: {path}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise BeatriceError(f"Ошибка парсинга JSON: {e}") from e
    try:
        return nx.node_link_graph(data, directed=True, multigraph=False)
    except (nx.NetworkXError, KeyError, TypeError) as e:
        raise BeatriceError(f"Файл не содержит валидного графа: {e}") from e


def save_graph(G: nx.DiGraph, path: str) -> None:
    """Записывает граф в JSON-файл в формате node-link.

    Raises:
        BeatriceError: если нет прав на запись или директория не создаётся.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = nx.node_link_data(G)
    try:
        p.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except (OSError, PermissionError) as e:
        raise BeatriceError(f"Не удалось записать файл {path}: {e}") from e


def cmd_search(args):
    """Найти узлы, чей id или label содержит строку или соответствует regex."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)

    try:
        if args.regex:
            matcher = re.compile(args.pattern)
        else:
            matcher = None
    except re.error as e:
        print(f"Ошибка: невалидное регулярное выражение: {e}")
        sys.exit(1)

    if matcher:
        matches = [
            n for n in G.nodes()
            if matcher.search(n) or (
                G.nodes[n].get("label")
                and matcher.search(str(G.nodes[n]["label"]))
            )
        ]
    else:
        plow = args.pattern.lower()
        matches = [
            n for n in G.nodes()
            if plow in n.lower()
            or plow in G.nodes[n].get("label", "").lower()
        ]
    print(f"Найдено узлов: {len(matches)}")
    for n in sorted(matches):
        label = G.nodes[n].get("label", n)
        desc = G.nodes[n].get("desc", "")
        print(f"  {n:<25s} «{label}»   {desc}")


def cmd_neighbors(args):
    """Показать соседей узла."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)
    if args.node not in G:
        print(f"Ошибка: узел «{args.node}» не найден в графе")
        sys.exit(1)

    direction = args.direction

    if direction in ("out", "all"):
        print(f"\n→ Исходящие (на кого указывает «{args.node}»):")
        for _, tgt, data in G.out_edges(args.node, data=True):
            label = G.nodes[tgt].get("label", tgt)
            rel = data.get("relation", "")
            print(f"  → {tgt:<20s} «{label}»   [{rel}]")

    if direction in ("in", "all"):
        print(f"\n← Входящие (кто указывает на «{args.node}»):")
        for src, _, data in G.in_edges(args.node, data=True):
            label = G.nodes[src].get("label", src)
            rel = data.get("relation", "")
            print(f"  ← {src:<20s} «{label}»   [{rel}]")

    if direction == "all":
        total = G.degree(args.node)
        print(f"\nВсего связей: {total}")


def cmd_orphans(args):
    """Показать узлы-сироты (без связей)."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)

    orphans = [n for n, d in G.degree() if d == 0]

    if not orphans:
        print("Сирот нет — все узлы имеют хотя бы одну связь.")
        return

    print(f"Найдено сирот: {len(orphans)}\n")
    for n in sorted(orphans):
        label = G.nodes[n].get("label", n)
        desc = G.nodes[n].get("desc", "")
        print(f"  {n:<25s} «{label}»   {desc}")


def cmd_add_node(args):
    """Добавить узел (узлы)."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)
    ids_added = []
    for nid in args.ids:
        if nid in G:
            print(f"Предупреждение: узел «{nid}» уже существует — пропускаю")
            continue
        attrs = {}
        if args.label:
            attrs["label"] = args.label
        if args.type:
            attrs["type"] = args.type
        if args.desc:
            attrs["desc"] = args.desc
        if args.color:
            attrs["color"] = args.color
        if args.size:
            attrs["size"] = args.size
        G.add_node(nid, **attrs)
        ids_added.append(nid)

    if ids_added:
        try:
            save_graph(G, args.graph)
        except BeatriceError as e:
            print(f"Ошибка при сохранении: {e}")
            sys.exit(1)
        print(f"Добавлено узлов: {len(ids_added)}")
        for nid in ids_added:
            print(f"  + {nid}")
    else:
        print("Новых узлов не добавлено")


def cmd_rm_node(args):
    """Удалить узел (узлы) и все связанные рёбра."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)
    removed = []
    for nid in args.ids:
        if nid not in G:
            print(f"Предупреждение: узел «{nid}» не найден — пропускаю")
            continue
        G.remove_node(nid)
        removed.append(nid)

    if removed:
        try:
            save_graph(G, args.graph)
        except BeatriceError as e:
            print(f"Ошибка при сохранении: {e}")
            sys.exit(1)
        print(f"Удалено узлов: {len(removed)}")
        for nid in removed:
            print(f"  - {nid}")
    else:
        print("Ничего не удалено")


def cmd_add_edge(args):
    """Добавить ребро (рёбра)."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)

    if len(args.sources) != len(args.targets):
        print(f"Ошибка: количество источников ({len(args.sources)}) не совпадает с количеством целей ({len(args.targets)})")
        sys.exit(1)

    pairs = list(zip(args.sources, args.targets))
    added = []
    for src, tgt in pairs:
        if src not in G:
            print(f"Ошибка: узел-источник «{src}» не найден")
            continue
        if tgt not in G:
            print(f"Ошибка: узел-цель «{tgt}» не найден")
            continue
        if G.has_edge(src, tgt):
            print(f"Предупреждение: ребро {src}→{tgt} уже существует — пропускаю")
            continue
        attrs = {}
        if args.relation:
            attrs["relation"] = args.relation
        if args.weight:
            attrs["weight"] = args.weight
        G.add_edge(src, tgt, **attrs)
        added.append((src, tgt))

    if added:
        try:
            save_graph(G, args.graph)
        except BeatriceError as e:
            print(f"Ошибка при сохранении: {e}")
            sys.exit(1)
        print(f"Добавлено рёбер: {len(added)}")
        for src, tgt in added:
            rel = args.relation or ""
            print(f"  + {src} → {tgt}  [{rel}]")
    else:
        print("Новых рёбер не добавлено")


def cmd_rm_edge(args):
    """Удалить ребро (рёбра)."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)

    if len(args.sources) != len(args.targets):
        print(f"Ошибка: количество источников ({len(args.sources)}) не совпадает с количеством целей ({len(args.targets)})")
        sys.exit(1)

    pairs = list(zip(args.sources, args.targets))
    removed = []
    for src, tgt in pairs:
        if not G.has_edge(src, tgt):
            print(f"Предупреждение: ребро {src}→{tgt} не найдено — пропускаю")
            continue
        G.remove_edge(src, tgt)
        removed.append((src, tgt))

    if removed:
        try:
            save_graph(G, args.graph)
        except BeatriceError as e:
            print(f"Ошибка при сохранении: {e}")
            sys.exit(1)
        print(f"Удалено рёбер: {len(removed)}")
        for src, tgt in removed:
            print(f"  - {src} → {tgt}")
    else:
        print("Ничего не удалено")


def cmd_islands(args):
    """Показать изолированные кластеры (компоненты слабой связности)."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)

    from networkx.algorithms.components import weakly_connected_components

    orphans_set = set(n for n, d in G.degree() if d == 0)
    components = sorted(
        weakly_connected_components(G),
        key=len,
        reverse=True,
    )

    if not components:
        print("Граф пуст — нет узлов")
        return

    for i, comp in enumerate(components, 1):
        size = len(comp)
        is_orphan = all(n in orphans_set for n in comp)
        size_word = "узел" if size == 1 else "узла" if 2 <= size <= 4 else "узлов"
        orphan_tag = " 👻 сирота" if is_orphan else ""
        print(f"\nОстров #{i} ({size} {size_word}{orphan_tag}):")
        for n in sorted(comp):
            label = G.nodes[n].get("label", n)
            type_str = G.nodes[n].get("type", "")
            print(f"  {n:<20s} «{label}»" + (f"  {type_str}" if type_str else ""))

    print(f"\nВсего островов: {len(components)}")


def cmd_ring(args):
    """Показать узлы на диапазоне глубин вокруг узла (BFS + XOR слоёв)."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)

    if args.node not in G:
        print(f"Ошибка: узел «{args.node}» не найден в графе")
        sys.exit(1)

    if args.min < 0:
        print("Ошибка: --min не может быть отрицательным")
        sys.exit(1)

    if args.max < args.min:
        print("Ошибка: --max не может быть меньше --min")
        sys.exit(1)

    from collections import deque

    # BFS от source node, собираем {node: depth}
    depths: dict[str, int] = {}
    q = deque()
    q.append((args.node, 0))

    while q:
        cur, d = q.popleft()
        if cur in depths:
            continue
        depths[cur] = d
        if d >= args.max:
            continue
        if args.direction in ("omnidirectional", "descending"):
            for nxt in G.successors(cur):
                if nxt not in depths:
                    q.append((nxt, d + 1))
        if args.direction in ("omnidirectional", "ascending"):
            for nxt in G.predecessors(cur):
                if nxt not in depths:
                    q.append((nxt, d + 1))

    # Убираем сам node (глубина 0), фильтруем по диапазону
    by_depth: dict[int, list[str]] = {}
    for nid, d in depths.items():
        if d == 0:
            continue
        if args.min < d <= args.max:
            by_depth.setdefault(d, []).append(nid)

    if not by_depth:
        dir_label = {"descending": "нисходящем", "ascending": "восходящем", "omnidirectional": "всенаправленном"}
        print(f"Нет узлов на глубинах {args.min + 1}–{args.max} от узла «{args.node}» ({dir_label[args.direction]})")
        return

    dir_label = {"descending": "descending", "ascending": "ascending", "omnidirectional": "all"}
    print(f"\nКольца {args.min + 1}–{args.max} от узла «{args.node}» ({dir_label[args.direction]}):")

    total = 0
    for depth in sorted(by_depth.keys()):
        nodes = sorted(by_depth[depth])
        print(f"\nГлубина {depth}:")
        for n in nodes:
            label = G.nodes[n].get("label", n)
            type_str = G.nodes[n].get("type", "")
            print(f"  {n:<20s} «{label}»" + (f"  {type_str}" if type_str else ""))
        total += len(nodes)

    print(f"\nНайдено: {total} узлов")


def cmd_edit_node(args):
    """Изменить атрибуты существующего узла (patch-only)."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)

    if args.id not in G:
        print(f"Ошибка: узел «{args.id}» не найден в графе")
        sys.exit(1)

    # Собираем только те атрибуты, что явно переданы
    changes = {}
    if args.label is not None:
        changes["label"] = args.label
    if args.type is not None:
        changes["type"] = args.type
    if args.desc is not None:
        changes["desc"] = args.desc
    if args.color is not None:
        changes["color"] = args.color
    if args.size is not None:
        changes["size"] = args.size

    if not changes:
        print("Ничего не изменено")
        return

    # Запоминаем старые значения для diff
    old = {k: G.nodes[args.id].get(k, "") for k in changes}

    # Применяем изменения
    G.nodes[args.id].update(changes)

    try:
        save_graph(G, args.graph)
    except BeatriceError as e:
        print(f"Ошибка при сохранении: {e}")
        sys.exit(1)

    # Выводим diff
    print(f"Изменён узел {args.id}:")
    for k in changes:
        old_val = str(old[k]) if old[k] else "(пусто)"
        new_val = str(changes[k]) if changes[k] else "(пусто)"
        print(f"  {k:<8s} {old_val} → {new_val}")


def main():
    parser = ArgumentParser(
        prog="beatrice",
        description="Beatrice — CLI для графов знаний",
        formatter_class=RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  beatrice graph search graph.json  kafka
  beatrice graph search graph.json  "kaf.*"  --regex
  beatrice graph neighbors graph.json  kafka  --direction all
  beatrice graph add-node graph.json  redis  --label Redis --type БД --desc "In-memory cache"
  beatrice graph rm-node graph.json  orphan1 orphan2
  beatrice graph add-edge graph.json  kafka zookeeper  --relation использует
  beatrice graph rm-edge graph.json  kafka zookeeper
  beatrice graph edit-node graph.json  kafka  --label "Apache Kafka" --desc "New description"
  beatrice graph islands graph.json
  beatrice graph components graph.json
  beatrice graph ring graph.json  kafka  --min 2 --max 4 --direction omnidirectional
  beatrice graph rng graph.json  kafka  --min 0 --max 1 --direction descending
""",
    )

    sub = parser.add_subparsers(dest="command")
    sub.required = True

    # --- graph (все операции с графом) ---
    graph = sub.add_parser("graph", help="Операции с графом")

    gsub = graph.add_subparsers(dest="action")
    gsub.required = True

    # search
    p_search = gsub.add_parser("search", help="Найти узлы по строке или regex")
    p_search.add_argument("graph", help="Путь к JSON-файлу графа")
    p_search.add_argument("pattern", help="Строка или регулярное выражение для поиска")
    p_search.add_argument("--regex", "-r", action="store_true", help="Интерпретировать pattern как regex")
    p_search.set_defaults(func=cmd_search)

    # neighbors
    p_nei = gsub.add_parser("neighbors", aliases=["nei", "nbr"],
                            help="Показать соседей узла")
    p_nei.add_argument("graph", help="Путь к JSON-файлу графа")
    p_nei.add_argument("node", help="ID узла")
    p_nei.add_argument("--direction", "-d",
                       choices=["out", "in", "all"], default="all",
                       help="Направление: out (на кого указывает), in (кто указывает), all (все)")
    p_nei.set_defaults(func=cmd_neighbors)

    # orphans
    p_orph = gsub.add_parser("orphans", aliases=["orph"],
                              help="Показать узлы-сироты (без связей)")
    p_orph.add_argument("graph", help="Путь к JSON-файлу графа")
    p_orph.set_defaults(func=cmd_orphans)

    # islands
    p_islands = gsub.add_parser("islands", aliases=["isl", "components"],
                                help="Показать изолированные кластеры (компоненты связности)")
    p_islands.add_argument("graph", help="Путь к JSON-файлу графа")
    p_islands.set_defaults(func=cmd_islands)

    # ring
    p_ring = gsub.add_parser("ring", aliases=["rng"],
                              help="Показать узлы на диапазоне глубин вокруг узла (XOR слоёв)")
    p_ring.add_argument("graph", help="Путь к JSON-файлу графа")
    p_ring.add_argument("node", help="ID узла")
    p_ring.add_argument("--min", type=int, required=True, help="Минимальная глубина (≥0)")
    p_ring.add_argument("--max", type=int, required=True, help="Максимальная глубина (≥min)")
    p_ring.add_argument("--direction", choices=["descending", "ascending", "omnidirectional"],
                        default="omnidirectional", help="Направление обхода")
    p_ring.set_defaults(func=cmd_ring)

    # add-node
    p_addn = gsub.add_parser("add-node", aliases=["an"],
                              help="Добавить узел(ы)")
    p_addn.add_argument("graph", help="Путь к JSON-файлу графа")
    p_addn.add_argument("ids", nargs="+", help="ID узла (узлов) для добавления")
    p_addn.add_argument("--label", "-l", help="Метка узла")
    p_addn.add_argument("--type", "-t", help="Тип узла (брокер, сервис, ...)")
    p_addn.add_argument("--desc", "-d", help="Описание узла")
    p_addn.add_argument("--color", "-c", help="Цвет узла (hex)")
    p_addn.add_argument("--size", type=float, help="Размер узла")
    p_addn.set_defaults(func=cmd_add_node)

    # rm-node
    p_rmn = gsub.add_parser("rm-node", aliases=["rn"],
                            help="Удалить узел(ы) и все их связи")
    p_rmn.add_argument("graph", help="Путь к JSON-файлу графа")
    p_rmn.add_argument("ids", nargs="+", help="ID узла (узлов) для удаления")
    p_rmn.set_defaults(func=cmd_rm_node)

    # edit-node
    p_editn = gsub.add_parser("edit-node", aliases=["en"],
                              help="Изменить атрибуты узла (patch-only)")
    p_editn.add_argument("graph", help="Путь к JSON-файлу графа")
    p_editn.add_argument("id", help="ID узла для редактирования")
    p_editn.add_argument("--label", "-l", help="Новая метка узла")
    p_editn.add_argument("--type", "-t", help="Новый тип узла")
    p_editn.add_argument("--desc", "-d", help="Новое описание узла")
    p_editn.add_argument("--color", "-c", help="Новый цвет узла (hex)")
    p_editn.add_argument("--size", type=float, help="Новый размер узла")
    p_editn.set_defaults(func=cmd_edit_node)

    # add-edge
    p_adde = gsub.add_parser("add-edge", aliases=["ae"],
                              help="Добавить ребро (рёбра)")
    p_adde.add_argument("graph", help="Путь к JSON-файлу графа")
    p_adde.add_argument("sources", nargs="+", help="ID узлов-источников")
    p_adde.add_argument("targets", nargs="+", help="ID узлов-целей")
    p_adde.add_argument("--relation", "-r", help="Тип связи")
    p_adde.add_argument("--weight", type=float, default=1.0, help="Вес связи")
    p_adde.set_defaults(func=cmd_add_edge)

    # rm-edge
    p_rme = gsub.add_parser("rm-edge", aliases=["re"],
                            help="Удалить ребро (рёбра)")
    p_rme.add_argument("graph", help="Путь к JSON-файлу графа")
    p_rme.add_argument("sources", nargs="+", help="ID узлов-источников")
    p_rme.add_argument("targets", nargs="+", help="ID узлов-целей")
    p_rme.set_defaults(func=cmd_rm_edge)

    # render
    p_render = gsub.add_parser("render", aliases=["viz"],
                                help="Сгенерировать standalone HTML-визуализацию")
    p_render.add_argument("graph", help="Путь к JSON-файлу графа")
    p_render.add_argument("output", nargs="?", default=None,
                          help="Путь для сохранения HTML (по умолчанию граф + .html)")
    p_render.add_argument("--engine", choices=["d3"], default="d3",
                          help="Движок визуализации (d3 — сейчас, sigma — позже)")
    p_render.add_argument("--theme", choices=["dark", "light"], default="dark",
                          help="Тема оформления")
    p_render.set_defaults(func=cmd_render)

    # tui
    p_tui = sub.add_parser("tui", help="Запустить TUI для графа знаний")
    p_tui.add_argument("graph", help="Путь к JSON-файлу графа")
    p_tui.set_defaults(func=cmd_tui)

    # --- stat (сокращение для быстрого просмотра) ---
    stat = sub.add_parser("stat", help="Статистика графа")
    stat.add_argument("graph", help="Путь к JSON-файлу графа")
    stat.set_defaults(func=cmd_stat)

    args = parser.parse_args()
    args.func(args)


def cmd_stat(args):
    """Показать статистику графа."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)
    orphans = [n for n, d in G.degree() if d == 0]
    print(f"Узлов:  {G.number_of_nodes()}")
    print(f"Рёбер:  {G.number_of_edges()}")
    print(f"Плотность:  {nx.density(G):.4f}")
    print(f"Сирот:  {len(orphans)}")
    if orphans:
        print(f"         {', '.join(orphans)}")

    from networkx.algorithms.community import louvain_communities
    try:
        comms = louvain_communities(G.to_undirected(), seed=42)
        print(f"Сообществ (Louvain): {len(comms)}")
    except Exception:
        pass

    from networkx.algorithms.components import weakly_connected_components
    islands = list(weakly_connected_components(G))
    print(f"Островов:  {len(islands)}")

    ranks = nx.pagerank(G)
    top5 = sorted(ranks.items(), key=lambda x: -x[1])[:5]
    print(f"PageRank топ-5:")
    for n, r in top5:
        print(f"  {n:<20s} {r:.4f}")


def cmd_tui(args):
    """Запустить TUI для графа."""
    from beatrice.tui.app import run_tui
    run_tui(args.graph)


def cmd_render(args):
    """Сгенерировать standalone HTML-визуализацию графа."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)

    output = args.output or (args.graph.rsplit(".", 1)[0] + ".html")
    theme = args.theme

    orphans = [n for n, d in G.degree() if d == 0]

    if theme == "light":
        bg = "#ffffff"; fg = "#333333"; panel_bg = "#f5f5f5"
        panel_border = "#ddd"; edge_color = "#999"; label_color = "#666"
    else:
        bg = "#1a1a2e"; fg = "#eee"; panel_bg = "#16213e"
        panel_border = "#0f3460"; edge_color = "#555"; label_color = "#888"

    nodes_data = []
    for n in G.nodes():
        nodes_data.append({
            "id": n,
            "label": G.nodes[n].get("label", n),
            "type": G.nodes[n].get("type", ""),
            "desc": G.nodes[n].get("desc", ""),
            "color": G.nodes[n].get("color", "#999"),
            "size": G.nodes[n].get("size", 10),
            "isOrphan": n in orphans,
        })

    edges_data = []
    for s, t, d in G.edges(data=True):
        edges_data.append({
            "source": s, "target": t,
            "relation": d.get("relation", ""),
        })

    types = {}
    for n in G.nodes():
        t = G.nodes[n].get("type", "unknown") or "unknown"
        c = G.nodes[n].get("color", "#999")
        if t not in types:
            types[t] = c

    import json
    json_nodes = json.dumps(nodes_data, ensure_ascii=False)
    json_edges = json.dumps(edges_data, ensure_ascii=False)
    json_orphans = json.dumps(list(orphans))
    json_types = json.dumps(types, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Beatrice — Knowledge Graph</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:{bg}; font-family:'Segoe UI',sans-serif; overflow:hidden; color:{fg}; }}
  #graph {{ width:100vw; height:100vh; }}
  .controls {{ position:absolute; top:16px; left:16px; z-index:10; display:flex; gap:8px; flex-wrap:wrap; }}
  .controls button {{
    background:{panel_bg}; color:{fg}; border:1px solid {panel_border};
    padding:8px 14px; border-radius:6px; cursor:pointer; font-size:13px;
    transition:background .2s;
  }}
  .controls button:hover {{ background:{panel_border}; }}
  .tooltip {{
    position:absolute; padding:12px 16px; background:{panel_bg}; border:1px solid {panel_border};
    border-radius:8px; font-size:13px; pointer-events:none; max-width:300px;
    display:none; z-index:20; line-height:1.5;
  }}
  .tooltip .title {{ font-weight:bold; font-size:15px; color:#e94560; margin-bottom:4px; }}
  .tooltip .sub {{ color:#aaa; font-size:12px; }}
  .legend {{
    position:absolute; bottom:24px; left:24px; z-index:10;
    background:{panel_bg}cc; padding:12px 16px; border-radius:8px;
    font-size:12px; border:1px solid {panel_border};
  }}
  .legend-item {{ display:flex; align-items:center; gap:8px; margin:4px 0; }}
  .legend-dot {{ width:12px; height:12px; border-radius:50%; flex-shrink:0; }}
  .info {{ position:absolute; bottom:24px; right:24px; font-size:11px; color:{label_color}; z-index:5; }}
</style>
</head>
<body>
<div id="graph"></div>
<div class="controls">
  <button onclick="resetZoom()">⟲ Сбросить</button>
  <button onclick="toggleOrphans()">👻 Сироты</button>
  <button onclick="toggleDirection()">↔ Направления</button>
</div>
<div class="legend" id="legend"></div>
<div class="tooltip" id="tooltip"></div>
<div class="info" id="info"></div>
<script>
const nodesData = {json_nodes};
const edgesData = {json_edges};
const orphans = {json_orphans};
const typeColors = {json_types};
const width = window.innerWidth, height = window.innerHeight;
document.getElementById('info').textContent =
  `${{nodesData.length}} узлов · ${{edgesData.length}} рёбер · ${{orphans.length}} сирот`;
const svg = d3.select("#graph").append("svg")
    .attr("width", width).attr("height", height)
    .call(d3.zoom().scaleExtent([0.1,10]).on("zoom",(e)=>{{container.attr("transform",e.transform);}}));
const container = svg.append("g");
const tooltip = d3.select("#tooltip");
const simulation = d3.forceSimulation(nodesData)
    .force("link", d3.forceLink(edgesData).id(d=>d.id).distance(150))
    .force("charge", d3.forceManyBody().strength(-400))
    .force("center", d3.forceCenter(width/2,height/2))
    .force("collision", d3.forceCollide().radius(d=>d.size+15));
const link = container.append("g").selectAll("line").data(edgesData).join("line")
    .attr("stroke","{edge_color}").attr("stroke-width",1.5).attr("stroke-opacity",0.6)
    .attr("marker-end","url(#arrow)");
const edgeLabel = container.append("g").selectAll("text").data(edgesData).join("text")
    .text(d=>d.relation).attr("font-size",9).attr("fill","{label_color}").attr("text-anchor","middle");
const node = container.append("g").selectAll("g").data(nodesData).join("g")
    .call(d3.drag()
        .on("start",(e,d)=>{{if(!e.active)simulation.alphaTarget(0.3).restart();d.fx=d.x;d.fy=d.y;}})
        .on("drag",(e,d)=>{{d.fx=e.x;d.fy=e.y;}})
        .on("end",(e,d)=>{{if(!e.active)simulation.alphaTarget(0);d.fx=null;d.fy=null;}}))
    .on("click",(e,d)=>{{
        tooltip.style("display","block").style("left",(e.pageX+16)+"px").style("top",(e.pageY-10)+"px")
            .html('<div class="title">'+d.label+'</div>'
                +(d.desc?'<div class="sub">'+d.desc+'</div>':'')
                +'<div class="sub" style="margin-top:4px">Тип: '+(d.type||'—')+'</div>'
                +(d.isOrphan?'<div class="sub" style="color:#ff6b6b;margin-top:4px">👻 Сирота</div>':''));
    }})
    .on("dblclick",(e,d)=>{{d.fx=null;d.fy=null;simulation.alpha(0.3).restart();}});
node.append("circle")
    .attr("r",d=>d.size||10).attr("fill",d=>d.color||"#666")
    .attr("stroke",d=>d.isOrphan?"#ff6b6b":"#fff").attr("stroke-width",d=>d.isOrphan?3:1.5)
    .style("cursor","pointer");
node.append("text").text(d=>d.label).attr("dx",0).attr("dy",d=>-(d.size||10)-6)
    .attr("text-anchor","middle").attr("font-size",12).attr("fill","#fff")
    .style("pointer-events","none");
svg.select("defs").remove();
const defs = svg.append("defs");
defs.append("marker").attr("id","arrow").attr("viewBox","0 -5 10 10")
    .attr("refX",25).attr("refY",0).attr("markerWidth",8).attr("markerHeight",8)
    .attr("orient","auto").append("path").attr("d","M0,-5L10,0L0,5").attr("fill","{edge_color}");
simulation.on("tick",()=>{{
    link.attr("x1",d=>d.source.x).attr("y1",d=>d.source.y)
        .attr("x2",d=>d.target.x).attr("y2",d=>d.target.y);
    edgeLabel.attr("x",d=>(d.source.x+d.target.x)/2).attr("y",d=>(d.source.y+d.target.y)/2-6);
    node.attr("transform",d=>`translate(${{d.x}},${{d.y}})`);
}});
d3.select("#legend").html(
    Object.entries(typeColors).filter(([k])=>k!=='unknown').map(([t,c])=>
        `<div class="legend-item"><span class="legend-dot" style="background:${{c}}"></span>${{t}}</div>`
    ).join(''));
function resetZoom(){{svg.transition().duration(750).call(d3.zoom().transform,d3.zoomIdentity);}}
let showOrphans=true;
function toggleOrphans(){{showOrphans=!showOrphans;node.style("opacity",d=>showOrphans?1:(d.isOrphan?0:1));}}
let showDir=true;
function toggleDirection(){{showDir=!showDir;link.attr("marker-end",showDir?"url(#arrow)":null);}}
d3.select("body").on("click",(e)=>{{if(!e.target.closest("g"))tooltip.style("display","none");}});
window.addEventListener("resize",()=>{{
    const w=window.innerWidth,h=window.innerHeight;
    svg.attr("width",w).attr("height",h);
    simulation.force("center",d3.forceCenter(w/2,h/2));
}});
</script>
</body>
</html>"""

    Path(output).write_text(html, encoding="utf-8")
    print(f"✅ HTML: {Path(output).resolve()}")
    print(f"   Узлов: {len(nodes_data)}, Рёбер: {len(edges_data)}, Сирот: {len(orphans)}")


if __name__ == "__main__":
    main()
