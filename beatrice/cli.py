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
from argparse import ArgumentParser, RawDescriptionHelpFormatter, Namespace
import shlex

# Добавляем корень проекта в sys.path для импорта модулей
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import networkx as nx


class BeatriceError(Exception):
    """Пользовательская ошибка Beatrice с человекочитаемым сообщением."""
    pass


def err(*args, **kwargs):
    """Печать в stderr."""
    print(*args, file=sys.stderr, **kwargs)


def output_graph(G, matched_nodes, fmt):
    """Вывести подграф (или весь граф) в заданном формате в stdout."""
    if fmt == "text":
        return
    sub = G.subgraph(matched_nodes) if matched_nodes is not None else G
    data = nx.node_link_data(sub)
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    print()


def save_or_output(G, path: str) -> None:
    """Сохранить граф на диск или вывести в stdout (если path == '-')."""
    if path == "-":
        data = nx.node_link_data(G)
        json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        save_graph(G, path)


def load_graph(path: str) -> nx.DiGraph:
    """Читает JSON-граф, возвращает NetworkX граф.

    Если path == "-", читает из stdin.
    Raises:
        BeatriceError: если файл не найден, битый JSON или не является графом.
    """
    if path == "-":
        try:
            data = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            raise BeatriceError(f"Ошибка парсинга JSON из stdin: {e}") from e
        try:
            return nx.node_link_graph(data, directed=True, multigraph=False)
        except (nx.NetworkXError, KeyError, TypeError) as e:
            raise BeatriceError(f"Данные из stdin не содержат валидного графа: {e}") from e
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


def apply_tag_filter(G: nx.DiGraph, tags: list[str], mode: str) -> set[str]:
    """Вернуть множество id узлов, проходящих фильтр по тегам.

    Если tags пуст — возвращает все узлы.
    mode='any' — узел подходит, если совпадает хотя бы один тег.
    mode='all' — должны совпасть все теги.
    """
    if not tags:
        return set(G.nodes())
    result = set()
    query_tags = set(tags)
    for n in G.nodes():
        node_tags = set(G.nodes[n].get("tags", []))
        if mode == "any":
            if node_tags & query_tags:
                result.add(n)
        elif mode == "all":
            if query_tags <= node_tags:
                result.add(n)
        elif mode == "none":
            if not (node_tags & query_tags):
                result.add(n)
    return result


def apply_note_filter(G: nx.DiGraph, mode: str) -> set[str]:
    """Вернуть множество id узлов, проходящих фильтр по note.

    Если mode пуст — возвращает все узлы.
    mode='with' — только узлы с note.
    mode='without' — только узлы без note.
    """
    if not mode:
        return set(G.nodes())
    if mode == "with":
        return {n for n in G.nodes() if G.nodes[n].get("note", "")}
    return {n for n in G.nodes() if not G.nodes[n].get("note", "")}


def cmd_init(args):
    """Создать новый пустой граф."""
    G = nx.DiGraph()
    G.graph["beatrice_counter"] = 0
    if args.graph == "-":
        data = nx.node_link_data(G)
        json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return
    try:
        p = Path(args.graph)
        if p.exists():
            raise BeatriceError(f"Файл уже существует: {args.graph}")
        save_graph(G, args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)
    print(f"Граф инициализирован: {args.graph}")


def cmd_tag_add(args):
    """Добавить теги к узлу (узлам)."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)
    any_work = False
    for nid in args.ids:
        if nid not in G:
            print(f"Предупреждение: узел «{nid}» не найден — пропускаю")
            continue
        tags = set(G.nodes[nid].get("tags", []))
        before = len(tags)
        tags.update(args.tags)
        G.nodes[nid]["tags"] = list(tags)
        added = len(tags) - before
        any_work = True
        print(f"  {nid}: добавлено {added} тегов")
    if any_work:
        try:
            save_or_output(G, args.graph)
        except BeatriceError as e:
            print(f"Ошибка при сохранении: {e}")
            sys.exit(1)


def cmd_tag_rm(args):
    """Удалить теги из узла (узлов)."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)
    any_work = False
    tags_to_rm = set(args.tags)
    for nid in args.ids:
        if nid not in G:
            print(f"Предупреждение: узел «{nid}» не найден — пропускаю")
            continue
        tags = set(G.nodes[nid].get("tags", []))
        before = len(tags)
        tags -= tags_to_rm
        removed = before - len(tags)
        if removed:
            G.nodes[nid]["tags"] = list(tags)
            any_work = True
            print(f"  {nid}: удалено {removed} тегов")
        else:
            print(f"  {nid}: ничего не удалено")
    if any_work:
        try:
            save_or_output(G, args.graph)
        except BeatriceError as e:
            print(f"Ошибка при сохранении: {e}")
            sys.exit(1)


def cmd_tag_ls(args):
    """Показать теги (всех узлов или конкретного)."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)

    if args.id:
        # Теги одного узла
        nid = args.id
        if nid not in G:
            print(f"Ошибка: узел «{nid}» не найден в графе")
            sys.exit(1)
        tags = G.nodes[nid].get("tags", [])
        if not tags:
            print(f"У узла «{nid}» нет тегов")
            return
        print(f"Теги узла «{nid}»:")
        for t in sorted(tags):
            print(f"  {t}")
        return

    from collections import Counter

    # --by-community
    if args.by_community:
        from networkx.algorithms.community import louvain_communities
        try:
            communities = list(louvain_communities(G.to_undirected(), seed=42))
        except Exception as e:
            print(f"Ошибка при вычислении сообществ: {e}")
            sys.exit(1)
        if not communities:
            print("Граф пуст")
            return
        for i, comm in enumerate(communities, 1):
            comm_counter: Counter[str] = Counter()
            for n in comm:
                for t in G.nodes[n].get("tags", []):
                    comm_counter[t] += 1
            # Определяем имя сообщества из первого подходящего type
            first_node = next(iter(comm))
            comm_label = f"Сообщество #{i}"
            print(f"\n{comm_label} ({len(comm)} узлов):")
            for t, cnt in sorted(comm_counter.items(), key=lambda x: -x[1]):
                print(f"  {t:<25s} {cnt}")
        return

    # Сбор тегов
    counter: Counter[str] = Counter()
    for n in G.nodes():
        for t in G.nodes[n].get("tags", []):
            counter[t] += 1

    if not counter and not args.untagged:
        print("В графе нет тегов")
        return

    # --tag T1 T2 — пересечение (сколько узлов имеют ВСЕ указанные теги)
    if args.tag:
        query = set(args.tag)
        if args.list:
            # Просто список ID узлов
            for n in G.nodes():
                node_tags = set(G.nodes[n].get("tags", []))
                if query <= node_tags:
                    print(n)
            return
        if args.counts:
            total = 0
            for n in G.nodes():
                node_tags = set(G.nodes[n].get("tags", []))
                if query <= node_tags:
                    total += 1
            tag_list = ", ".join(args.tag)
            print(f"Узлы с тегами [{tag_list}]: {total}")
            return

    # --untagged — узлы без тегов
    if args.untagged:
        untagged = [n for n in G.nodes() if not G.nodes[n].get("tags", [])]
        if not untagged:
            print("Все узлы имеют хотя бы один тег")
            return
        print(f"Узлы без тегов ({len(untagged)}):")
        for n in sorted(untagged):
            label = G.nodes[n].get("label", n)
            type_str = G.nodes[n].get("type", "")
            print(f"  {n:<25s} «{label}»" + (f"  {type_str}" if type_str else ""))
        return

    # --without TAG — узлы, у которых нет указанного тега
    if args.without and not args.tag and not args.untagged:
        without_set = set(args.without)
        result = [
            n for n in G.nodes()
            if not (without_set & set(G.nodes[n].get("tags", [])))
        ]
        tags_str = ", ".join(args.without)
        print(f"Узлы без тега «{tags_str}» ({len(result)}):")
        for n in sorted(result):
            label = G.nodes[n].get("label", n)
            type_str = G.nodes[n].get("type", "")
            print(f"  {n:<25s} «{label}»" + (f"  {type_str}" if type_str else ""))
        return

    # --counts (без --tag)
    if args.counts:
        for t, cnt in sorted(counter.items(), key=lambda x: -x[1]):
            print(f"{t}: {cnt}")
        return

    # Обычный вывод
    print(f"{len(counter)} тегов в графе:")
    for t, cnt in sorted(counter.items(), key=lambda x: -x[1]):
        print(f"  {t:<25s} ({cnt} узел{'а' if 2 <= cnt <= 4 else 'ов' if cnt >= 5 else ''})")


def cmd_tag_clear(args):
    """Очистить все теги узла."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)
    for nid in args.ids:
        if nid not in G:
            print(f"Предупреждение: узел «{nid}» не найден — пропускаю")
            continue
        G.nodes[nid]["tags"] = []
        print(f"  {nid}: теги очищены")
    try:
        save_or_output(G, args.graph)
    except BeatriceError as e:
        print(f"Ошибка при сохранении: {e}")
        sys.exit(1)


def cmd_note_add(args):
    """Задать note (Obsidian-ссылку) узлу."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)
    for nid in args.ids:
        if nid not in G:
            print(f"Предупреждение: узел «{nid}» не найден — пропускаю")
            continue
        G.nodes[nid]["note"] = args.uri
        print(f"  {nid}: note задан")
    try:
        save_or_output(G, args.graph)
    except BeatriceError as e:
        print(f"Ошибка при сохранении: {e}")
        sys.exit(1)


def cmd_note_rm(args):
    """Очистить note у узла."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)
    for nid in args.ids:
        if nid not in G:
            print(f"Предупреждение: узел «{nid}» не найден — пропускаю")
            continue
        G.nodes[nid]["note"] = ""
        print(f"  {nid}: note очищен")
    try:
        save_or_output(G, args.graph)
    except BeatriceError as e:
        print(f"Ошибка при сохранении: {e}")
        sys.exit(1)


def cmd_note_ls(args):
    """Показать информацию о note (статистику или конкретного узла)."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)

    if args.id:
        nid = args.id
        if nid not in G:
            print(f"Ошибка: узел «{nid}» не найден")
            sys.exit(1)
        note = G.nodes[nid].get("note", "")
        if note:
            print(f"📝 {nid}: {note}")
        else:
            print(f"У узла «{nid}» нет конспекта")
        return

    notes = {n for n in G.nodes() if G.nodes[n].get("note", "")}
    no_notes = {n for n in G.nodes() if not G.nodes[n].get("note", "")}

    if args.with_:
        for n in sorted(notes):
            label = G.nodes[n].get("label", n)
            type_str = G.nodes[n].get("type", "")
            print(f"  {n:<25s} «{label}»" + (f"  {type_str}" if type_str else ""))
        return

    if args.without:
        for n in sorted(no_notes):
            label = G.nodes[n].get("label", n)
            type_str = G.nodes[n].get("type", "")
            print(f"  {n:<25s} «{label}»" + (f"  {type_str}" if type_str else ""))
        return

    total = G.number_of_nodes()
    n_with = len(notes)
    n_without = len(no_notes)
    pct = round(n_with / total * 100) if total else 0
    print(f"📝 Конспекты: {n_with}/{total} узлов ({pct}%)")
    print(f"  С конспектом:  {n_with}")
    print(f"  Без конспекта: {n_without}")


def cmd_search(args):
    """Найти узлы, чей id или label содержит строку или соответствует regex."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)

    tag_filter = apply_tag_filter(G, args.tag, args.tag_mode)
    note_filter = apply_note_filter(G, getattr(args, 'note', ''))
    combined = tag_filter & note_filter

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
            n for n in G.nodes() if n in combined
            if matcher.search(n) or (
                G.nodes[n].get("label")
                and matcher.search(str(G.nodes[n]["label"]))
            )
        ]
    else:
        plow = args.pattern.lower()
        matches = [
            n for n in G.nodes() if n in combined
            if plow in n.lower()
            or plow in G.nodes[n].get("label", "").lower()
        ]
    if args.output_format == "json":
        output_graph(G, set(matches), "json")
        return
    print(f"Найдено узлов: {len(matches)}")
    for n in sorted(matches):
        label = G.nodes[n].get("label", n)
        desc = G.nodes[n].get("desc", "")
        print(f"  {n:<25s} «{label}»   {desc}")
    if args.output_format == "json":
        output_graph(G, set(matches), "json")


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

    tag_filter = apply_tag_filter(G, args.tag, args.tag_mode)
    note_filter = apply_note_filter(G, getattr(args, 'note', ''))
    combined = tag_filter & note_filter
    direction = args.direction

    if direction in ("out", "all"):
        if args.output_format != "json":
            print(f"\n→ Исходящие (на кого указывает «{args.node}»):")
        for _, tgt, data in G.out_edges(args.node, data=True):
            if tgt not in combined:
                continue
            if args.output_format != "json":
                label = G.nodes[tgt].get("label", tgt)
                rel = data.get("relation", "")
                print(f"  → {tgt:<20s} «{label}»   [{rel}]")

    if direction in ("in", "all"):
        if args.output_format != "json":
            print(f"\n← Входящие (кто указывает на «{args.node}»):")
        for src, _, data in G.in_edges(args.node, data=True):
            if src not in combined:
                continue
            if args.output_format != "json":
                label = G.nodes[src].get("label", src)
                rel = data.get("relation", "")
                print(f"  ← {src:<20s} «{label}»   [{rel}]")

    if direction == "all":
        total = G.degree(args.node)
        if args.output_format != "json":
            print(f"\nВсего связей: {total}")
    if args.output_format == "json":
        nbrs = {args.node}
        for _, tgt, _ in G.out_edges(args.node, data=True):
            nbrs.add(tgt)
        for src, _, _ in G.in_edges(args.node, data=True):
            nbrs.add(src)
        output_graph(G, nbrs, "json")


def cmd_orphans(args):
    """Показать узлы-сироты (без связей)."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)

    note_filter = apply_note_filter(G, getattr(args, 'note', ''))
    orphans = [n for n, d in G.degree() if d == 0 and n in note_filter]

    if args.output_format == "json":
        output_graph(G, set(orphans), "json")
        return

    if not orphans:
        print("Сирот нет — все узлы имеют хотя бы одну связь.")
        return

    print(f"Найдено сирот: {len(orphans)}\n")
    for n in sorted(orphans):
        label = G.nodes[n].get("label", n)
        desc = G.nodes[n].get("desc", "")
        print(f"  {n:<25s} «{label}»   {desc}")
    if args.output_format == "json":
        output_graph(G, set(orphans), "json")


def cmd_roots(args):
    """Показать корневые узлы (out>0, in=0 — сами ссылаются, на них нет)."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)

    note_filter = apply_note_filter(G, getattr(args, 'note', ''))
    roots = [n for n in G.nodes() if G.out_degree(n) > 0 and G.in_degree(n) == 0 and n in note_filter]

    roots = [n for n in G.nodes() if G.out_degree(n) > 0 and G.in_degree(n) == 0]

    if args.output_format == "json":
        output_graph(G, set(roots), "json")
        return

    if not roots:
        print("Корневых узлов нет — каждый узел на кого-то ссылается и на него ссылаются.")
        return

    print(f"Найдено корневых узлов: {len(roots)}\n")
    for n in sorted(roots):
        label = G.nodes[n].get("label", n)
        type_str = G.nodes[n].get("type", "")
        print(f"  {n:<25s} «{label}»" + (f"  {type_str}" if type_str else ""))


def cmd_frontier(args):
    """Показать пограничные узлы (in>0, out=0 — на них ссылаются, сами нет)."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)

    note_filter = apply_note_filter(G, getattr(args, 'note', ''))
    frontier = [n for n in G.nodes() if G.in_degree(n) > 0 and G.out_degree(n) == 0 and n in note_filter]

    if args.output_format == "json":
        output_graph(G, set(frontier), "json")
        return

    if not frontier:
        print("Пограничных узлов нет — каждый узел на кого-то ссылается и на него ссылаются.")
        if args.output_format == "json":
            output_graph(G, set(), "json")
        return

    print(f"Найдено пограничных узлов: {len(frontier)}\n")
    for n in sorted(frontier):
        label = G.nodes[n].get("label", n)
        type_str = G.nodes[n].get("type", "")
        print(f"  {n:<25s} «{label}»" + (f"  {type_str}" if type_str else ""))

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
        if getattr(args, 'note', None):
            attrs["note"] = args.note
        G.add_node(nid, **attrs)
        ids_added.append(nid)

    if ids_added:
        try:
            save_or_output(G, args.graph)
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
            save_or_output(G, args.graph)
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
            save_or_output(G, args.graph)
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
            save_or_output(G, args.graph)
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

    tag_filter = apply_tag_filter(G, args.tag, args.tag_mode)
    note_filter = apply_note_filter(G, getattr(args, 'note', ''))
    combined = tag_filter & note_filter
    subgraph = G.subgraph(combined)

    orphans_set = set(n for n, d in subgraph.degree() if d == 0)
    components = sorted(
        weakly_connected_components(subgraph),
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
    if args.output_format == "json":
        output_graph(G, None, "json")


def cmd_louvain(args):
    """Показать Louvain-сообщества (кластеризация по плотности связей)."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)

    from networkx.algorithms.community import louvain_communities

    try:
        communities = list(louvain_communities(G.to_undirected(), seed=args.seed))
    except Exception as e:
        print(f"Ошибка при вычислении сообществ: {e}")
        sys.exit(1)

    if not communities:
        print("Граф пуст — нет узлов")
        return

    communities.sort(key=len, reverse=True)

    for i, comm in enumerate(communities, 1):
        size = len(comm)
        size_word = "узел" if size == 1 else "узла" if 2 <= size <= 4 else "узлов"
        print(f"\nСообщество #{i} ({size} {size_word}):")
        for n in sorted(comm):
            label = G.nodes[n].get("label", n)
            type_str = G.nodes[n].get("type", "")
            print(f"  {n:<20s} «{label}»" + (f"  {type_str}" if type_str else ""))

    print(f"\nВсего сообществ: {len(communities)}")
    if args.output_format == "json":
        output_graph(G, None, "json")


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

    tag_filter = apply_tag_filter(G, args.tag, args.tag_mode)
    note_filter = apply_note_filter(G, getattr(args, 'note', ''))
    combined = tag_filter & note_filter

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
    if args.output_format == "json":
        ring_nodes = set()
        for nodes in by_depth.values():
            ring_nodes.update(nodes)
        output_graph(G, ring_nodes, "json")


def cmd_intersect(args):
    """Пересечение двух графов: узлы, присутствующие в обоих."""
    try:
        G1 = load_graph(args.graph1)
        G2 = load_graph(args.graph2)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)
    common = set(G1.nodes()) & set(G2.nodes())
    sub = G1.subgraph(common)
    data = nx.node_link_data(sub)
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    print()


def cmd_union(args):
    """Объединение двух графов: все узлы из обоих."""
    try:
        G1 = load_graph(args.graph1)
        G2 = load_graph(args.graph2)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)
    all_nodes = set(G1.nodes()) | set(G2.nodes())
    G = nx.DiGraph()
    for n in all_nodes:
        attrs = {}
        if n in G1:
            attrs = dict(G1.nodes[n])
        elif n in G2:
            attrs = dict(G2.nodes[n])
        G.add_node(n, **attrs)
    # Рёбра из обоих графов
    for s, t, d in G1.edges(data=True):
        G.add_edge(s, t, **d)
    for s, t, d in G2.edges(data=True):
        G.add_edge(s, t, **dict(d))
    data = nx.node_link_data(G)
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    print()


def cmd_diff(args):
    """Разность двух графов: узлы из graph1, которых нет в graph2."""
    try:
        G1 = load_graph(args.graph1)
        G2 = load_graph(args.graph2)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)
    diff_nodes = set(G1.nodes()) - set(G2.nodes())
    sub = G1.subgraph(diff_nodes)
    data = nx.node_link_data(sub)
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    print()


def cmd_symdiff(args):
    """Симметрическая разность двух графов: узлы, присутствующие только в одном из них."""
    try:
        G1 = load_graph(args.graph1)
        G2 = load_graph(args.graph2)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)
    sym = set(G1.nodes()) ^ set(G2.nodes())
    all_nodes = list(sym)
    G = nx.DiGraph()
    for n in all_nodes:
        if n in G1:
            G.add_node(n, **dict(G1.nodes[n]))
        else:
            G.add_node(n, **dict(G2.nodes[n]))
    for s, t, d in G1.edges(data=True):
        if s in sym and t in sym:
            G.add_edge(s, t, **d)
    for s, t, d in G2.edges(data=True):
        if s in sym and t in sym:
            G.add_edge(s, t, **dict(d))
    data = nx.node_link_data(G)
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    print()


def cmd_mv(args):
    """Переименовать узел с сохранением атрибутов и рёбер."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
        sys.exit(1)

    if args.old not in G:
        print(f"Ошибка: узел «{args.old}» не найден в графе")
        sys.exit(1)
    if args.new in G:
        print(f"Ошибка: узел «{args.new}» уже существует")
        sys.exit(1)

    nx.relabel_nodes(G, {args.old: args.new}, copy=False)

    try:
        save_or_output(G, args.graph)
    except BeatriceError as e:
        print(f"Ошибка при сохранении: {e}")
        sys.exit(1)
    print(f"{args.old} → {args.new}")


def cmd_edit_node(args):
    """Изменить атрибуты узлов (patch-only)."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}")
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
    if getattr(args, 'note', None) is not None:
        changes["note"] = args.note

    if not changes:
        print("Ничего не изменено")
        return

    edited = []
    for nid in args.ids:
        if nid not in G:
            print(f"Предупреждение: узел «{nid}» не найден — пропускаю")
            continue
        old = {k: G.nodes[nid].get(k, "") for k in changes}
        G.nodes[nid].update(changes)
        edited.append((nid, old))

    if not edited:
        print("Ничего не изменено")
        return

    try:
        save_or_output(G, args.graph)
    except BeatriceError as e:
        print(f"Ошибка при сохранении: {e}")
        sys.exit(1)

    for nid, old in edited:
        print(f"Изменён узел {nid}:")
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
  beatrice graph louvain graph.json
  beatrice graph lv graph.json
  beatrice graph tag add graph.json kafka streaming kafka-экосистема
  beatrice graph tag ls graph.json
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

    # init
    p_init = gsub.add_parser("init", help="Создать новый пустой граф")
    p_init.add_argument("graph", help="Путь к JSON-файлу графа (или '-' для stdout)")
    p_init.set_defaults(func=cmd_init)

    # search
    p_search = gsub.add_parser("search", help="Найти узлы по строке или regex")
    p_search.add_argument("graph", help="Путь к JSON-файлу графа")
    p_search.add_argument("pattern", help="Строка или регулярное выражение для поиска")
    p_search.add_argument("--regex", "-r", action="store_true", help="Интерпретировать pattern как regex")
    p_search.add_argument("--tag", action="append", default=[],
                          help="Фильтр по тегу (можно несколько)")
    p_search.add_argument("--tag-mode", choices=["any", "all", "none"], default="any",
                          help="Режим фильтрации тегов: any (любой) или all (все)")
    p_search.add_argument("--output-format", choices=["text", "json"], default="text",
                          help="Формат вывода")
    p_search.add_argument("--json", action="store_const", dest="output_format", const="json",
                          help="Сокращение для --output-format json")
    p_search.add_argument("--note", choices=["with", "without"], default="",
                          help="Фильтр по наличию конспекта: with/without")
    p_search.set_defaults(func=cmd_search)

    # neighbors
    p_nei = gsub.add_parser("neighbors", aliases=["nei", "nbr"],
                            help="Показать соседей узла")
    p_nei.add_argument("graph", help="Путь к JSON-файлу графа")
    p_nei.add_argument("node", help="ID узла")
    p_nei.add_argument("--direction", "-d",
                       choices=["out", "in", "all"], default="all",
                       help="Направление: out (на кого указывает), in (кто указывает), all (все)")
    p_nei.add_argument("--tag", action="append", default=[],
                       help="Фильтр по тегу (можно несколько)")
    p_nei.add_argument("--tag-mode", choices=["any", "all", "none"], default="any",
                       help="Режим фильтрации тегов: any (любой) или all (все)")
    p_nei.add_argument("--output-format", choices=["text", "json"], default="text",
                       help="Формат вывода")
    p_nei.add_argument("--json", action="store_const", dest="output_format", const="json",
                       help="Сокращение для --output-format json")
    p_nei.add_argument("--note", choices=["with", "without"], default="",
                       help="Фильтр по наличию конспекта: with/without")
    p_nei.set_defaults(func=cmd_neighbors)

    # orphans
    p_orph = gsub.add_parser("orphans", aliases=["orph"],
                              help="Показать узлы-сироты (без связей)")
    p_orph.add_argument("graph", help="Путь к JSON-файлу графа")
    p_orph.add_argument("graph", help="Путь к JSON-файлу графа")
    p_orph.add_argument("--output-format", choices=["text", "json"], default="text",
                        help="Формат вывода")
    p_orph.add_argument("--json", action="store_const", dest="output_format", const="json",
                        help="Сокращение для --output-format json")
    p_orph.add_argument("--note", choices=["with", "without"], default="",
                        help="Фильтр по наличию конспекта: with/without")
    p_orph.set_defaults(func=cmd_orphans)

    # roots
    p_roots = gsub.add_parser("roots",
                              help="Показать корневые узлы (out>0, in=0)")
    p_roots.add_argument("graph", help="Путь к JSON-файлу графа")
    p_roots.add_argument("--output-format", choices=["text", "json"], default="text",
                         help="Формат вывода")
    p_roots.add_argument("--json", action="store_const", dest="output_format", const="json",
                         help="Сокращение для --output-format json")
    p_roots.add_argument("--note", choices=["with", "without"], default="",
                         help="Фильтр по наличию конспекта: with/without")
    p_roots.set_defaults(func=cmd_roots)

    # frontier
    p_frontier = gsub.add_parser("frontier", aliases=["front"],
                                 help="Показать пограничные узлы (in>0, out=0)")
    p_frontier.add_argument("graph", help="Путь к JSON-файлу графа")
    p_frontier.add_argument("--output-format", choices=["text", "json"], default="text",
                            help="Формат вывода")
    p_frontier.add_argument("--json", action="store_const", dest="output_format", const="json",
                            help="Сокращение для --output-format json")
    p_frontier.add_argument("--note", choices=["with", "without"], default="",
                            help="Фильтр по наличию конспекта: with/without")
    p_frontier.set_defaults(func=cmd_frontier)

    # islands
    p_islands = gsub.add_parser("islands", aliases=["isl", "components"],
                                help="Показать изолированные кластеры (компоненты связности)")
    p_islands.add_argument("graph", help="Путь к JSON-файлу графа")
    p_islands.add_argument("--tag", action="append", default=[],
                          help="Фильтр по тегу (можно несколько)")
    p_islands.add_argument("--tag-mode", choices=["any", "all", "none"], default="any",
                          help="Режим фильтрации тегов: any (любой) или all (все)")
    p_islands.add_argument("--output-format", choices=["text", "json"], default="text",
                           help="Формат вывода")
    p_islands.add_argument("--json", action="store_const", dest="output_format", const="json",
                           help="Сокращение для --output-format json")
    p_islands.add_argument("--note", choices=["with", "without"], default="",
                           help="Фильтр по наличию конспекта: with/without")
    p_islands.set_defaults(func=cmd_islands)

    # louvain
    p_louvain = gsub.add_parser("louvain", aliases=["lv"],
                                help="Показать Louvain-сообщества (кластеризация по плотности связей)")
    p_louvain.add_argument("graph", help="Путь к JSON-файлу графа")
    p_louvain.add_argument("--seed", type=int, default=42,
                           help="Seed для воспроизводимости (по умолч. 42)")
    p_louvain.add_argument("--output-format", choices=["text", "json"], default="text",
                           help="Формат вывода")
    p_louvain.add_argument("--json", action="store_const", dest="output_format", const="json",
                           help="Сокращение для --output-format json")
    p_louvain.set_defaults(func=cmd_louvain)

    # ring
    p_ring = gsub.add_parser("ring", aliases=["rng"],
                              help="Показать узлы на диапазоне глубин вокруг узла (XOR слоёв)")
    p_ring.add_argument("graph", help="Путь к JSON-файлу графа")
    p_ring.add_argument("node", help="ID узла")
    p_ring.add_argument("--min", type=int, required=True, help="Минимальная глубина (≥0)")
    p_ring.add_argument("--max", type=int, required=True, help="Максимальная глубина (≥min)")
    p_ring.add_argument("--direction", choices=["descending", "ascending", "omnidirectional"],
                        default="omnidirectional", help="Направление обхода")
    p_ring.add_argument("--tag", action="append", default=[],
                        help="Фильтр по тегу (можно несколько)")
    p_ring.add_argument("--tag-mode", choices=["any", "all", "none"], default="any",
                        help="Режим фильтрации тегов: any (любой) или all (все)")
    p_ring.add_argument("--output-format", choices=["text", "json"], default="text",
                        help="Формат вывода")
    p_ring.add_argument("--json", action="store_const", dest="output_format", const="json",
                        help="Сокращение для --output-format json")
    p_ring.add_argument("--note", choices=["with", "without"], default="",
                        help="Фильтр по наличию конспекта: with/without")
    p_ring.set_defaults(func=cmd_ring)

    # set operations
    for op, op_help in [
        ("intersect", "Пересечение двух графов: узлы, присутствующие в обоих"),
        ("union", "Объединение двух графов: все узлы из обоих"),
        ("diff", "Разность двух графов: узлы из первого, которых нет во втором"),
        ("symdiff", "Симметрическая разность: узлы, присутствующие только в одном"),
    ]:
        p_op = gsub.add_parser(op, help=op_help)
        p_op.add_argument("graph1", help="Путь к первому JSON-графу")
        p_op.add_argument("graph2", help="Путь ко второму JSON-графу")
        p_op.set_defaults(func={
            "intersect": cmd_intersect,
            "union": cmd_union,
            "diff": cmd_diff,
            "symdiff": cmd_symdiff,
        }[op])

    # note
    p_note = gsub.add_parser("note",
                            help="Управление Obsidian-конспектами узлов")
    nsub = p_note.add_subparsers(dest="note_action")
    nsub.required = True

    p_note_add = nsub.add_parser("add", help="Задать note узлу")
    p_note_add.add_argument("graph", help="Путь к JSON-файлу графа")
    p_note_add.add_argument("ids", nargs="+", help="ID узла (узлов)")
    p_note_add.add_argument("uri", help="Obsidian URI")
    p_note_add.set_defaults(func=cmd_note_add)

    p_note_rm = nsub.add_parser("rm", help="Очистить note узла")
    p_note_rm.add_argument("graph", help="Путь к JSON-файлу графа")
    p_note_rm.add_argument("ids", nargs="+", help="ID узла (узлов)")
    p_note_rm.set_defaults(func=cmd_note_rm)

    p_note_ls = nsub.add_parser("ls", help="Показать информацию о note")
    p_note_ls.add_argument("graph", help="Путь к JSON-файлу графа")
    p_note_ls.add_argument("id", nargs="?", default=None, help="ID узла (опционально)")
    p_note_ls.add_argument("--with", dest="with_", action="store_true",
                           help="Список узлов с note")
    p_note_ls.add_argument("--without", action="store_true",
                           help="Список узлов без note")
    p_note_ls.set_defaults(func=cmd_note_ls)

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
    p_editn.add_argument("--ids", nargs="+", required=True, help="ID узлов для редактирования")
    p_editn.add_argument("--label", "-l", help="Новая метка узла")
    p_editn.add_argument("--type", "-t", help="Новый тип узла")
    p_editn.add_argument("--desc", "-d", help="Новое описание узла")
    p_editn.add_argument("--color", "-c", help="Новый цвет узла (hex)")
    p_editn.add_argument("--size", type=float, help="Новый размер узла")
    p_editn.set_defaults(func=cmd_edit_node)

    # mv
    p_mv = gsub.add_parser("mv",
                           help="Переименовать узел с сохранением атрибутов и рёбер")
    p_mv.add_argument("graph", help="Путь к JSON-файлу графа")
    p_mv.add_argument("old", help="Текущий ID узла")
    p_mv.add_argument("new", help="Новый ID узла")
    p_mv.set_defaults(func=cmd_mv)

    # tag
    p_tag = gsub.add_parser("tag",
                            help="Управление тегами узлов")
    tsub = p_tag.add_subparsers(dest="tag_action")
    tsub.required = True

    p_tag_add = tsub.add_parser("add", help="Добавить теги к узлу")
    p_tag_add.add_argument("graph", help="Путь к JSON-файлу графа")
    p_tag_add.add_argument("ids", nargs="+", help="ID узла (узлов)")
    p_tag_add.add_argument("tags", nargs="+", metavar="tag", help="Теги для добавления")
    p_tag_add.set_defaults(func=cmd_tag_add)

    p_tag_rm = tsub.add_parser("rm", help="Удалить теги из узла")
    p_tag_rm.add_argument("graph", help="Путь к JSON-файлу графа")
    p_tag_rm.add_argument("ids", nargs="+", help="ID узла (узлов)")
    p_tag_rm.add_argument("tags", nargs="+", metavar="tag", help="Теги для удаления")
    p_tag_rm.set_defaults(func=cmd_tag_rm)

    p_tag_ls = tsub.add_parser("ls", help="Показать теги")
    p_tag_ls.add_argument("graph", help="Путь к JSON-файлу графа")
    p_tag_ls.add_argument("id", nargs="?", default=None, help="ID узла (опционально)")
    p_tag_ls.add_argument("--counts", action="store_true",
                          help="Показать теги в формате tag: count (по одному на строку)")
    p_tag_ls.add_argument("--tag", action="append", default=[],
                          help="Фильтр: показать пересечение указанных тегов")
    p_tag_ls.add_argument("--by-community", action="store_true",
                          help="Показать теги по Louvain-сообществам")
    p_tag_ls.add_argument("--list", action="store_true",
                          help="Вывести ID узлов с указанными тегами (по одному на строку)")
    p_tag_ls.add_argument("--untagged", action="store_true",
                          help="Показать узлы без тегов")
    p_tag_ls.add_argument("--without", action="append", default=[],
                          metavar="TAG",
                          help="Показать узлы без указанного тега (можно несколько)")
    p_tag_ls.set_defaults(func=cmd_tag_ls)

    p_tag_clear = tsub.add_parser("clear", help="Очистить все теги узла")
    p_tag_clear.add_argument("graph", help="Путь к JSON-файлу графа")
    p_tag_clear.add_argument("ids", nargs="+", help="ID узла (узлов)")
    p_tag_clear.set_defaults(func=cmd_tag_clear)

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

    # serve
    p_serve = sub.add_parser("serve", help="Запустить Web GUI (FastAPI + React)")
    p_serve.add_argument("graph", help="Путь к JSON-файлу графа")
    p_serve.add_argument("--host", default="127.0.0.1", help="Хост сервера")
    p_serve.add_argument("--port", type=int, default=8576, help="Порт сервера")
    p_serve.add_argument("--dev", action="store_true", help="Режим разработки (CORS для Vite dev server)")
    p_serve.set_defaults(func=cmd_serve)

    # batch
    p_batch = sub.add_parser("batch", help="Пакетное выполнение операций над графом")
    p_batch.add_argument("graph", help="Путь к JSON-файлу графа")
    p_batch.add_argument("commands", help="Файл с командами или «-» для stdin")
    p_batch.set_defaults(func=cmd_batch)

    # snapshot
    p_snap = sub.add_parser("snapshot", help="Создать копию графа (снапшот)")
    p_snap.add_argument("source", help="Путь к исходному JSON-графу")
    p_snap.add_argument("dest", help="Путь для сохранения снапшота")
    p_snap.set_defaults(func=cmd_snapshot)

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
    notes = [n for n in G.nodes() if G.nodes[n].get("note", "")]
    n_with = len(notes)
    total = G.number_of_nodes()
    pct = round(n_with / total * 100) if total else 0
    print(f"Конспекты:  {n_with}/{total} ({pct}%)")

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


def cmd_serve(args):
    """Запустить Web GUI (FastAPI + React SPA)."""
    from beatrice.web_gui.server import run_server
    run_server(args.graph, host=args.host, port=args.port, dev=args.dev)


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

    # Louvain-сообщества для опциональной раскраски
    try:
        from networkx.algorithms.community import louvain_communities
        communities = list(louvain_communities(G.to_undirected(), seed=42))
        # Узлу → номер сообщества
        node_community = {}
        for i, comm in enumerate(communities):
            for n in comm:
                node_community[n] = i
        louvain_available = True
    except Exception:
        node_community = {}
        louvain_available = False

    # Палитра цветов для сообществ (12 оттенков, циклически)
    louvain_palette = [
        "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4",
        "#42d4f4", "#f032e6", "#bfef45", "#fabed4", "#469990", "#dcbeff",
    ]

    # Все уникальные теги в графе для подсветки
    from collections import Counter
    tag_counter: Counter[str] = Counter()
    for n in G.nodes():
        for t in G.nodes[n].get("tags", []):
            tag_counter[t] += 1
    all_tags = sorted(tag_counter.keys())

    nodes_data = []
    for n in G.nodes():
        comm_idx = node_community.get(n, 0)
        nodes_data.append({
            "id": n,
            "label": G.nodes[n].get("label", n),
            "type": G.nodes[n].get("type", ""),
            "desc": G.nodes[n].get("desc", ""),
            "color": G.nodes[n].get("color", "#999"),
            "size": G.nodes[n].get("size", 10),
            "isOrphan": n in orphans,
            "community": comm_idx,
            "communityColor": louvain_palette[comm_idx % len(louvain_palette)],
            "tags": G.nodes[n].get("tags", []),
            "note": G.nodes[n].get("note", ""),
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
    json_louvain = json.dumps(louvain_available)
    json_all_tags = json.dumps(all_tags, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Beatrice — Knowledge Graph</title>
<script>
D3_CODE_PLACEHOLDER
</script>
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
  .controls select {{
    background:{panel_bg}; color:{fg}; border:1px solid {panel_border};
    padding:8px 14px; border-radius:6px; cursor:pointer; font-size:13px;
  }}
  .controls select:hover {{ background:{panel_border}; }}
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
  <button onclick="toggleLouvain()">🧬 Сообщества</button>
  <select id="community-select" onchange="selectCommunity(this.value)" style="display:none">
    <option value="">— Все сообщества —</option>
  </select>
  <select id="tag-select" onchange="applyTagHighlight()">
    <option value="">— Тег —</option>
  </select>
  <input type="color" id="tag-color" value="#e94560" oninput="applyTagHighlight()" style="width:36px;height:36px;padding:2px;border:1px solid {panel_border};border-radius:6px;background:{panel_bg};cursor:pointer;">
</div>
<div class="legend" id="legend"></div>
<div class="tooltip" id="tooltip"></div>
<div class="info" id="info"></div>
<script>
const nodesData = {json_nodes};
const edgesData = {json_edges};
const orphans = {json_orphans};
const typeColors = {json_types};
const louvainAvailable = {json_louvain};
const allTags = {json_all_tags};
const tagSelect = document.getElementById("tag-select");
allTags.forEach(t => {{
    const opt = document.createElement("option");
    opt.value = t;
    opt.textContent = t;
    tagSelect.appendChild(opt);
}});
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
                +(d.note?'<div class="sub" style="margin-top:4px">📝 <a href="'+d.note+'" target="_blank">Конспект</a></div>':'')
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
function toggleOrphans(){{
    showOrphans=!showOrphans;
    updateVisibility();
}}
let showDir=true;
function toggleDirection(){{showDir=!showDir;link.attr("marker-end",showDir?"url(#arrow)":null);}}
let showLouvain=false;
let focusCommunity=null;
let tagHighlightActive=false;
let tagHighlightColor="#e94560";

// Заполняем select сообществ
const commSelect = document.getElementById("community-select");
const usedComms = [...new Set(nodesData.map(d=>d.community))].sort((a,b)=>a-b);
usedComms.forEach(i =>{{
    const opt = document.createElement("option");
    opt.value = i;
    opt.textContent = `Сообщество #${{i+1}}`;
    commSelect.appendChild(opt);
}});

function selectCommunity(val){{
    focusCommunity = val ? parseInt(val) : null;
    updateVisibility();
}}

function updateVisibility(){{
    node.each(function(d){{
        const g = d3.select(this);
        const circle = g.select("circle");
        let visible = true;
        if(showLouvain && focusCommunity!==null && d.community!==focusCommunity){{
            visible = false;
        }}
        if(visible && !showOrphans && d.isOrphan){{
            visible = false;
        }}
        g.style("display", visible ? null : "none");
        if(visible && showLouvain){{
            circle.attr("fill", d.communityColor);
        }}else if(visible){{
            circle.attr("fill", d.color);
        }}
    }});
}}

function applyTagHighlight(){{
    const sel = document.getElementById("tag-select").value;
    const color = document.getElementById("tag-color").value;
    tagHighlightColor = color;
    if(!sel){{
        tagHighlightActive=false;
        node.selectAll("circle").transition().duration(300)
            .attr("fill",d=>showLouvain?d.communityColor:d.color);
        return;
    }}
    tagHighlightActive=true;
    node.selectAll("circle").transition().duration(300)
        .attr("fill",d=>d.tags&&d.tags.includes(sel)?color:(showLouvain?d.communityColor:d.color));
}}

function toggleLouvain(){{
    showLouvain=!showLouvain;
    const commSelect = document.getElementById("community-select");
    if(showLouvain){{
        commSelect.style.display = "inline";
        const palette = {json.dumps(louvain_palette, ensure_ascii=False)};
        d3.select("#legend").html(
            usedComms.map(i=>`<div class="legend-item"><span class="legend-dot" style="background:${{palette[i%palette.length]}}"></span>Сообщество #${{i+1}}</div>`).join(''));
    }}else{{
        commSelect.style.display = "none";
        focusCommunity = null;
        commSelect.value = "";
        d3.select("#legend").html(
            Object.entries(typeColors).filter(([k])=>k!=='unknown').map(([t,c])=>
                `<div class="legend-item"><span class="legend-dot" style="background:${{c}}"></span>${{t}}</div>`
            ).join(''));
    }}
    updateVisibility();
}}
d3.select("body").on("click",(e)=>{{if(!e.target.closest("g"))tooltip.style("display","none");}});
window.addEventListener("resize",()=>{{
    const w=window.innerWidth,h=window.innerHeight;
    svg.attr("width",w).attr("height",h);
    simulation.force("center",d3.forceCenter(w/2,h/2));
}});
</script>
</body>
</html>"""

    # Встраиваем D3.js вместо CDN-ссылки (работает без интернета, file://)
    d3_path = Path(__file__).resolve().parent / "d3.v7.min.js"
    if d3_path.exists():
        d3_code = d3_path.read_text(encoding="utf-8")
        html = html.replace("D3_CODE_PLACEHOLDER", d3_code)
    else:
        # fallback: CDN
        html = html.replace("D3_CODE_PLACEHOLDER",
            f"""const d3 = await import('https://d3js.org/d3.v7.min.js');""")

    Path(output).write_text(html, encoding="utf-8")
    print(f"✅ HTML: {Path(output).resolve()}")
    print(f"   Узлов: {len(nodes_data)}, Рёбер: {len(edges_data)}, Сирот: {len(orphans)}")


def cmd_snapshot(args):
    """Создать копию графа (снапшот)."""
    import shutil
    src = Path(args.source)
    dst = Path(args.dest)
    if not src.exists():
        print(f"Ошибка: файл не найден: {args.source}", file=sys.stderr)
        sys.exit(1)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), str(dst))
    print(f"✅ Снапшот: {src.resolve()} → {dst.resolve()}")


def cmd_batch(args):
    """Пакетное выполнение операций над графом."""
    try:
        G = load_graph(args.graph)
    except BeatriceError as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        sys.exit(1)

    if args.commands == "-":
        lines = sys.stdin.readlines()
    else:
        lines = Path(args.commands).read_text(encoding="utf-8").splitlines()

    known_commands = {
        "add-node": cmd_add_node,
        "rm-node": cmd_rm_node,
        "edit-node": cmd_edit_node,
        "add-edge": cmd_add_edge,
        "rm-edge": cmd_rm_edge,
        "tag": None,
    }

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = shlex.split(line)
        if not parts:
            continue
        cmd_name = parts[0]

        if cmd_name not in known_commands:
            print(f"Предупреждение: неизвестная команда «{cmd_name}» — пропускаю", file=sys.stderr)
            print(f"  Строка: {line}", file=sys.stderr)
            continue

        # Строим FakeArgs для subparser marshalling
        # batch всегда оперирует над загруженным графом в памяти, запись — один раз в конце
        fake = Namespace()
        fake.graph = args.graph  # все команды используют args.graph

        if cmd_name == "add-node":
            parser = ArgumentParser()
            parser.add_argument("ids", nargs="+")
            parser.add_argument("--label", "-l", default=None)
            parser.add_argument("--type", "-t", default=None)
            parser.add_argument("--desc", "-d", default=None)
            parser.add_argument("--color", "-c", default=None)
            parser.add_argument("--size", type=float, default=None)
            parser.add_argument("--note", "-n", default=None)
            subargs = parser.parse_args(parts[1:])
            fake.ids = subargs.ids
            fake.label = subargs.label
            fake.type = subargs.type
            fake.desc = subargs.desc
            fake.color = subargs.color
            fake.size = subargs.size
            fake.note = subargs.note
            _batch_cmd_add_node(G, fake)

        elif cmd_name == "add-edge":
            parser = ArgumentParser()
            parser.add_argument("sources", nargs="+")
            parser.add_argument("targets", nargs="+")
            parser.add_argument("--relation", "-r", default=None)
            parser.add_argument("--weight", type=float, default=None)
            subargs = parser.parse_args(parts[1:])
            fake.sources = subargs.sources
            fake.targets = subargs.targets
            fake.relation = subargs.relation
            fake.weight = subargs.weight
            _batch_cmd_add_edge(G, fake)

        elif cmd_name == "rm-node":
            parser = ArgumentParser()
            parser.add_argument("ids", nargs="+")
            subargs = parser.parse_args(parts[1:])
            for nid in subargs.ids:
                if nid not in G:
                    print(f"Предупреждение: узел «{nid}» не найден — пропускаю")
                    continue
                G.remove_node(nid)
                print(f"  - {nid}")

        elif cmd_name == "rm-edge":
            parser = ArgumentParser()
            parser.add_argument("sources", nargs="+")
            parser.add_argument("targets", nargs="+")
            subargs = parser.parse_args(parts[1:])
            for src, tgt in zip(subargs.sources, subargs.targets):
                if not G.has_edge(src, tgt):
                    print(f"Предупреждение: ребро {src}→{tgt} не найдено — пропускаю")
                    continue
                G.remove_edge(src, tgt)
                print(f"  - {src} → {tgt}")

        elif cmd_name == "edit-node":
            parser = ArgumentParser()
            parser.add_argument("--ids", nargs="+", required=True)
            parser.add_argument("--label", "-l", default=None)
            parser.add_argument("--type", "-t", default=None)
            parser.add_argument("--desc", "-d", default=None)
            parser.add_argument("--color", "-c", default=None)
            parser.add_argument("--size", type=float, default=None)
            subargs = parser.parse_args(parts[1:])
            fake.ids = subargs.ids
            fake.label = subargs.label
            fake.type = subargs.type
            fake.desc = subargs.desc
            fake.color = subargs.color
            fake.size = subargs.size
            _batch_cmd_edit_node(G, fake)

        elif cmd_name == "tag":
            parser = ArgumentParser()
            parser.add_argument("subcmd", choices=["add", "rm", "clear"])
            parser.add_argument("--ids", nargs="+", required=True)
            parser.add_argument("--tags", nargs="*", default=[], metavar="tag")
            subargs = parser.parse_args(parts[1:])
            if subargs.subcmd == "add":
                for nid in subargs.ids:
                    if nid not in G:
                        print(f"Предупреждение: узел «{nid}» не найден — пропускаю", file=sys.stderr)
                        continue
                    tags = set(G.nodes[nid].get("tags", []))
                    before = len(tags)
                    tags.update(subargs.tags)
                    G.nodes[nid]["tags"] = list(tags)
                    added = len(tags) - before
                    print(f"  {nid}: добавлено {added} тегов")
            elif subargs.subcmd == "rm":
                tags_to_rm = set(subargs.tags)
                for nid in subargs.ids:
                    if nid not in G:
                        print(f"Предупреждение: узел «{nid}» не найден — пропускаю", file=sys.stderr)
                        continue
                    tags = set(G.nodes[nid].get("tags", []))
                    before = len(tags)
                    tags -= tags_to_rm
                    removed = before - len(tags)
                    if removed:
                        G.nodes[nid]["tags"] = list(tags)
                        print(f"  {nid}: удалено {removed} тегов")
                    else:
                        print(f"  {nid}: ничего не удалено")
            elif subargs.subcmd == "clear":
                for nid in subargs.ids:
                    if nid not in G:
                        print(f"Предупреждение: узел «{nid}» не найден — пропускаю", file=sys.stderr)
                        continue
                    G.nodes[nid]["tags"] = []
                    print(f"  {nid}: теги очищены")

    # Сохраняем
    try:
        save_or_output(G, args.graph)
    except BeatriceError as e:
        print(f"Ошибка при сохранении: {e}", file=sys.stderr)
        sys.exit(1)


def _batch_cmd_add_node(G, fake):
    """Добавить узлы (batch — сразу в G, без save)."""
    for nid in fake.ids:
        if nid in G:
            print(f"Предупреждение: узел «{nid}» уже существует — пропускаю")
            continue
        attrs = {}
        if fake.label:
            attrs["label"] = fake.label
        if fake.type:
            attrs["type"] = fake.type
        if fake.desc:
            attrs["desc"] = fake.desc
        if fake.color:
            attrs["color"] = fake.color
        if fake.size:
            attrs["size"] = fake.size
        if getattr(fake, 'note', None):
            attrs["note"] = fake.note
        G.add_node(nid, **attrs)
        print(f"  + {nid}")


def _batch_cmd_add_edge(G, fake):
    """Добавить рёбра (batch — сразу в G, без save)."""
    if len(fake.sources) != len(fake.targets):
        print(f"Ошибка: количество источников ({len(fake.sources)}) не совпадает с количеством целей ({len(fake.targets)})")
        return
    for src, tgt in zip(fake.sources, fake.targets):
        if src not in G:
            print(f"Предупреждение: узел-источник «{src}» не найден — пропускаю")
            continue
        if tgt not in G:
            print(f"Предупреждение: узел-цель «{tgt}» не найден — пропускаю")
            continue
        if G.has_edge(src, tgt):
            print(f"Предупреждение: ребро {src}→{tgt} уже существует — пропускаю")
            continue
        attrs = {}
        if fake.relation:
            attrs["relation"] = fake.relation
        if fake.weight:
            attrs["weight"] = fake.weight
        G.add_edge(src, tgt, **attrs)
        rel = fake.relation or ""
        print(f"  + {src} → {tgt}  [{rel}]")


def _batch_cmd_edit_node(G, fake):
    """Изменить узлы (batch — сразу в G, без save)."""
    changes = {}
    if fake.label is not None:
        changes["label"] = fake.label
    if fake.type is not None:
        changes["type"] = fake.type
    if fake.desc is not None:
        changes["desc"] = fake.desc
    if fake.color is not None:
        changes["color"] = fake.color
    if fake.size is not None:
        changes["size"] = fake.size
    if not changes:
        return
    for nid in fake.ids:
        if nid not in G:
            print(f"Предупреждение: узел «{nid}» не найден — пропускаю")
            continue
        G.nodes[nid].update(changes)
        print(f"  ✎ {nid}")


if __name__ == "__main__":
    main()
