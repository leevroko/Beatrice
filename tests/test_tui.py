"""Тесты для TUI-модуля Beatrice."""

import json
import os
import tempfile
import unittest
from pathlib import Path

import networkx as nx

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from beatrice.tui.graph_manager import GraphManager
from beatrice.tui.messages import (
    NodeSelected, NodeSaved, NodeAdded, NodeDeleted,
    LinkAdded, LinkDeleted, StatusMessage,
)
from beatrice.cli import BeatriceError


def make_test_graph() -> nx.DiGraph:
    G = nx.DiGraph()
    nodes = [
        ("kafka",   {"label": "Kafka",        "type": "брокер",      "desc": "event streaming"}),
        ("zk",      {"label": "ZooKeeper",    "type": "координатор", "desc": "cluster mgmt"}),
        ("sr",      {"label": "Schema Reg",   "type": "сервис",      "desc": "schemas"}),
        ("connect", {"label": "Kafka Connect","type": "сервис",      "desc": "integration"}),
        ("orphan",  {"label": "Сирота",       "type": "unknown",     "desc": "нет связей"}),
    ]
    G.add_nodes_from(nodes)
    edges = [
        ("kafka", "zk",   {"relation": "использует"}),
        ("kafka", "sr",   {"relation": "использует"}),
        ("connect", "kafka", {"relation": "пишет в"}),
    ]
    G.add_edges_from(edges)
    return G


def create_temp_graph() -> str:
    """Создать временный JSON-граф, вернуть путь."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    path = tmp.name
    G = make_test_graph()
    data = nx.node_link_data(G)
    tmp.write(json.dumps(data, ensure_ascii=False))
    tmp.close()
    return path


class TestGraphManagerLoad(unittest.TestCase):
    """Загрузка графа."""

    def setUp(self):
        self.path = create_temp_graph()

    def tearDown(self):
        os.unlink(self.path)

    def test_load(self):
        gm = GraphManager()
        gm.load(self.path)
        self.assertEqual(gm.node_count, 5)
        self.assertEqual(gm.edge_count, 3)
        self.assertEqual(gm.orphan_count, 1)

    def test_load_invalid_path(self):
        gm = GraphManager()
        with self.assertRaises(BeatriceError):
            gm.load("/no/such/file.json")


class TestGraphManagerCRUD(unittest.TestCase):
    """Мутация графа."""

    def setUp(self):
        self.path = create_temp_graph()
        self.gm = GraphManager()
        self.gm.load(self.path)

    def tearDown(self):
        os.unlink(self.path)

    def test_add_node(self):
        self.gm.add_node("redis", label="Redis", type="БД")
        self.assertIn("redis", self.gm.all_nodes())
        self.assertEqual(self.gm.node_attrs("redis")["label"], "Redis")

    def test_remove_node(self):
        self.gm.remove_node("orphan")
        self.assertNotIn("orphan", self.gm.all_nodes())
        self.assertEqual(self.gm.orphan_count, 0)

    def test_update_node(self):
        self.gm.update_node("kafka", label="Apache Kafka")
        self.assertEqual(self.gm.node_attrs("kafka")["label"], "Apache Kafka")

    def test_add_edge(self):
        self.gm.add_edge("kafka", "orphan", relation="тест")
        self.assertTrue(self.gm.has_edge("kafka", "orphan"))

    def test_remove_edge(self):
        self.gm.remove_edge("kafka", "zk")
        self.assertFalse(self.gm.has_edge("kafka", "zk"))

    def test_update_edge(self):
        self.gm.update_edge("kafka", "zk", relation="новое")
        self.assertEqual(
            self.gm.G.edges["kafka", "zk"]["relation"], "новое"
        )

    def test_orphans_list(self):
        self.assertEqual(self.gm.orphans, ["orphan"])

    def test_neighbors_out(self):
        out = self.gm.neighbors_out("kafka")
        ids = [t for t, _ in out]
        self.assertIn("zk", ids)
        self.assertIn("sr", ids)

    def test_neighbors_in(self):
        inp = self.gm.neighbors_in("kafka")
        ids = [s for s, _ in inp]
        self.assertIn("connect", ids)


class TestHistory(unittest.TestCase):
    """Undo/Redo."""

    def setUp(self):
        self.path = create_temp_graph()
        self.gm = GraphManager()
        self.gm.load(self.path)

    def tearDown(self):
        os.unlink(self.path)

    def test_undo_redo_add_node(self):
        self.gm.add_node("test")
        self.assertIn("test", self.gm.all_nodes())
        self.assertTrue(self.gm.can_undo)

        self.gm.undo()
        self.assertNotIn("test", self.gm.all_nodes())
        self.assertTrue(self.gm.can_redo)

        self.gm.redo()
        self.assertIn("test", self.gm.all_nodes())

    def test_undo_redo_remove(self):
        self.gm.remove_node("orphan")
        self.assertNotIn("orphan", self.gm.all_nodes())
        self.gm.undo()
        self.assertIn("orphan", self.gm.all_nodes())

    def test_undo_redo_edge(self):
        self.gm.add_edge("kafka", "orphan")
        self.assertTrue(self.gm.has_edge("kafka", "orphan"))
        self.gm.undo()
        self.assertFalse(self.gm.has_edge("kafka", "orphan"))
        self.gm.redo()
        self.assertTrue(self.gm.has_edge("kafka", "orphan"))

    def test_undo_redo_limit(self):
        """Проверить, что лимит 25 срабатывает (старые снимки отбрасываются)."""
        for i in range(30):
            self.gm.add_node(f"n{i}")
        # После 30 добавлений в истории только 25 снимков
        # Откатываемся до конца — должны вернуться к тому, что было 25 шагов назад
        while self.gm.can_undo:
            self.gm.undo()
        # Старых снимков (n0..n4) уже нет, поэтому узлов больше, чем 5
        self.assertGreater(self.gm.node_count, 5)
        self.assertLess(self.gm.node_count, 12)

    def test_undo_redo_available(self):
        self.assertFalse(self.gm.can_undo)
        self.assertFalse(self.gm.can_redo)
        self.gm.add_node("x")
        self.assertTrue(self.gm.can_undo)
        self.assertFalse(self.gm.can_redo)
        self.gm.undo()
        self.assertFalse(self.gm.can_undo)
        self.assertTrue(self.gm.can_redo)


class TestGraphManagerSave(unittest.TestCase):
    """Сохранение на диск."""

    def setUp(self):
        self.path = create_temp_graph()
        self.gm = GraphManager()
        self.gm.load(self.path)

    def tearDown(self):
        os.unlink(self.path)

    def test_save(self):
        self.gm.add_node("new_node")
        self.gm.save()
        self.assertFalse(self.gm.dirty)
        # Перезагрузить и проверить
        gm2 = GraphManager()
        gm2.load(self.path)
        self.assertIn("new_node", gm2.all_nodes())

    def test_save_as(self):
        path2 = self.path + ".new.json"
        try:
            self.gm.add_node("saved")
            self.gm.save_as(path2)
            gm2 = GraphManager()
            gm2.load(path2)
            self.assertIn("saved", gm2.all_nodes())
        finally:
            Path(path2).unlink(missing_ok=True)


class TestMessages(unittest.TestCase):
    """Сообщения."""

    def test_node_selected(self):
        m = NodeSelected("kafka")
        self.assertEqual(m.node_id, "kafka")

    def test_link_added(self):
        m = LinkAdded("a", "b", "knows")
        self.assertEqual(m.source, "a")
        self.assertEqual(m.target, "b")
        self.assertEqual(m.relation, "knows")

    def test_status_message(self):
        m = StatusMessage("hello", "error")
        self.assertEqual(m.text, "hello")
        self.assertEqual(m.severity, "error")


if __name__ == "__main__":
    unittest.main()
