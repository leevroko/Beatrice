"""Управление графом для TUI.

Обёртка над load_graph/save_graph с историей изменений (snapshots).
"""

from pathlib import Path
from typing import Optional
import json

import networkx as nx

from beatrice.cli import load_graph, save_graph, BeatriceError


class GraphManager:
    """Загружает, хранит и сохраняет граф. Ведёт историю snapshots для undo/redo."""

    MAX_SNAPSHOTS = 25

    def __init__(self):
        self.G: nx.DiGraph = nx.DiGraph()
        self.path: Optional[str] = None
        self._dirty: bool = False
        self._snapshots: list[dict] = []  # список nx.node_link_data() снимков
        self._snapshot_index: int = -1     # текущая позиция в истории (-1 = нет снимков)
        self._counter: int = 0             # счётчик для автогенерации node id

    # ────── Загрузка / сохранение ──────

    def load(self, path: str) -> None:
        """Загрузить граф из JSON-файла."""
        self.G = load_graph(path)
        self.path = path
        self._dirty = False
        self._snapshots = []
        self._snapshot_index = -1
        # Восстанавливаем счётчик из мета-данных графа
        self._counter = self.G.graph.get("beatrice_counter", 0)
        self._push_snapshot()

    def save(self) -> None:
        """Сохранить текущее состояние графа на диск."""
        if self.path is None:
            raise BeatriceError("Путь к файлу не указан")
        # Сохраняем счётчик в мета-данные графа перед записью
        self.G.graph["beatrice_counter"] = self._counter
        save_graph(self.G, self.path)
        self._dirty = False

    def save_as(self, path: str) -> None:
        """Сохранить граф в новый файл."""
        self.path = path
        self.save()

    # ────── Свойства ──────

    @property
    def dirty(self) -> bool:
        return self._dirty

    @property
    def node_count(self) -> int:
        return self.G.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self.G.number_of_edges()

    @property
    def orphan_count(self) -> int:
        return sum(1 for _, d in self.G.degree() if d == 0)

    @property
    def orphans(self) -> list[str]:
        return [n for n, d in self.G.degree() if d == 0]

    def node_labels(self) -> dict[str, str]:
        """Вернуть {id: label} для всех узлов."""
        return {
            n: data.get("label", n)
            for n, data in self.G.nodes(data=True)
        }

    # ────── Мутация (все изменения через эти методы) ──────

    def add_node(self, node_id: str, **attrs) -> None:
        """Добавить узел. Если существует — обновить атрибуты."""
        self.G.add_node(node_id, **attrs)
        self._mark_changed()

    def next_node_id(self) -> str:
        """Сгенерировать уникальный ID узла (node1, node2, ...)."""
        self._counter += 1
        nid = f"node{self._counter}"
        # Гарантия уникальности — если коллизия, продолжаем инкремент
        while self.G.has_node(nid):
            self._counter += 1
            nid = f"node{self._counter}"
        return nid

    def remove_node(self, node_id: str) -> None:
        """Удалить узел и все его связи."""
        self.G.remove_node(node_id)
        self._mark_changed()

    def add_edge(self, source: str, target: str, **attrs) -> None:
        """Добавить ребро."""
        self.G.add_edge(source, target, **attrs)
        self._mark_changed()

    def remove_edge(self, source: str, target: str) -> None:
        """Удалить ребро."""
        self.G.remove_edge(source, target)
        self._mark_changed()

    def update_node(self, node_id: str, **attrs) -> None:
        """Обновить атрибуты узла (мерж с существующими)."""
        for key, value in attrs.items():
            self.G.nodes[node_id][key] = value
        self._mark_changed()

    def update_edge(self, source: str, target: str, **attrs) -> None:
        """Обновить атрибуты ребра (мерж с существующими)."""
        for key, value in attrs.items():
            self.G.edges[source, target][key] = value
        self._mark_changed()

    def node_attrs(self, node_id: str) -> dict:
        """Вернуть атрибуты узла."""
        return dict(self.G.nodes[node_id])

    def neighbors_out(self, node_id: str) -> list[tuple[str, dict]]:
        """Вернуть [(target, data)] для исходящих связей."""
        return [
            (tgt, dict(data))
            for _, tgt, data in self.G.out_edges(node_id, data=True)
        ]

    def neighbors_in(self, node_id: str) -> list[tuple[str, dict]]:
        """Вернуть [(source, data)] для входящих связей."""
        return [
            (src, dict(data))
            for src, _, data in self.G.in_edges(node_id, data=True)
        ]

    def has_node(self, node_id: str) -> bool:
        return self.G.has_node(node_id)

    def has_edge(self, source: str, target: str) -> bool:
        return self.G.has_edge(source, target)

    def all_nodes(self) -> list[str]:
        """Вернуть список всех id узлов."""
        return list(self.G.nodes())

    def all_edges(self) -> list[tuple[str, str, dict]]:
        """Вернуть [(source, target, data)] для всех рёбер."""
        return [(s, t, dict(d)) for s, t, d in self.G.edges(data=True)]

    def degree(self, node_id: str) -> int:
        return self.G.degree(node_id)

    # ────── Undo/Redo ──────

    def _push_snapshot(self) -> None:
        """Сохранить текущее состояние как snapshot (вызывается при каждом изменении)."""
        # Удаляем всё, что после текущей позиции (если мы откатились и сделали новое действие)
        if self._snapshot_index < len(self._snapshots) - 1:
            self._snapshots = self._snapshots[:self._snapshot_index + 1]
        snap = nx.node_link_data(self.G)
        self._snapshots.append(snap)
        if len(self._snapshots) > self.MAX_SNAPSHOTS:
            self._snapshots.pop(0)
        self._snapshot_index = len(self._snapshots) - 1

    def _restore_snapshot(self, index: int) -> bool:
        """Восстановить состояние из snapshot. Вернуть True если удалось."""
        if 0 <= index < len(self._snapshots):
            self.G = nx.node_link_graph(
                self._snapshots[index], directed=True, multigraph=False
            )
            self._snapshot_index = index
            self._dirty = True
            return True
        return False

    def undo(self) -> bool:
        """Откатиться на шаг назад. Вернуть True если удалось."""
        return self._restore_snapshot(self._snapshot_index - 1)

    def redo(self) -> bool:
        """Вернуть отменённое изменение. Вернуть True если удалось."""
        return self._restore_snapshot(self._snapshot_index + 1)

    @property
    def can_undo(self) -> bool:
        return self._snapshot_index > 0

    @property
    def can_redo(self) -> bool:
        return self._snapshot_index < len(self._snapshots) - 1

    def _mark_changed(self) -> None:
        """Пометить граф как изменённый и сохранить snapshot."""
        self._dirty = True
        self._push_snapshot()
