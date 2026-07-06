#!/usr/bin/env python3
"""Юнит-тесты для CLI-операций Beatrice."""

import json
import os
import tempfile
import unittest
import io
import sys
from contextlib import contextmanager
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from beatrice.cli import (BeatriceError, load_graph, save_graph,
    cmd_search, cmd_neighbors, cmd_orphans, cmd_add_node, cmd_rm_node,
    cmd_add_edge, cmd_rm_edge, cmd_render)


@contextmanager
def capture_stdout():
    old = sys.stdout
    buf = io.StringIO()
    sys.stdout = buf
    try:
        yield buf
    finally:
        sys.stdout = old


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


class FakeArgs:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# ─────────────────────────────────────────────────────────
# Path helper — создаёт временный .json файл с тестовым графом
# ─────────────────────────────────────────────────────────

class GraphTestCase(unittest.TestCase):
    """Базовый класс — создаёт временный граф в setUp, чистит в tearDown."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        self.path = self.tmp.name
        save_graph(make_test_graph(), self.path)

    def tearDown(self):
        os.unlink(self.path)


# ─────────────────────────────────────────────────────────
# Load / Save
# ─────────────────────────────────────────────────────────

class TestLoadSaveGraph(GraphTestCase):
    """Загрузка и сохранение графа."""

    def test_roundtrip(self):
        G1 = make_test_graph()
        save_graph(G1, self.path)
        G2 = load_graph(self.path)
        self.assertEqual(G1.number_of_nodes(), G2.number_of_nodes())
        self.assertEqual(G1.number_of_edges(), G2.number_of_edges())
        self.assertEqual(set(G1.nodes()), set(G2.nodes()))
        self.assertTrue(G2.has_edge("kafka", "zk"))

    def test_load_invalid_json(self):
        Path(self.path).write_text("not valid json")
        with self.assertRaises(BeatriceError):
            load_graph(self.path)

    def test_save_produces_valid_json(self):
        data = json.loads(Path(self.path).read_text(encoding="utf-8"))
        self.assertIn("nodes", data)
        self.assertIn("edges", data)
        self.assertTrue(data["directed"])


# ─────────────────────────────────────────────────────────
# Search
# ─────────────────────────────────────────────────────────

class TestSearch(GraphTestCase):

    def test_search_by_id(self):
        args = FakeArgs(graph=self.path, pattern="kaf", regex=False)
        with capture_stdout() as out:
            cmd_search(args)
        self.assertIn("kafka", out.getvalue())

    def test_search_by_label(self):
        args = FakeArgs(graph=self.path, pattern="zoo", regex=False)
        with capture_stdout() as out:
            cmd_search(args)
        self.assertIn("zk", out.getvalue())

    def test_search_no_match(self):
        args = FakeArgs(graph=self.path, pattern="zzzzz", regex=False)
        with capture_stdout() as out:
            cmd_search(args)
        self.assertIn("0", out.getvalue())

    def test_search_regex(self):
        args = FakeArgs(graph=self.path, pattern=".*kafka.*|.*Kafka.*", regex=True)
        with capture_stdout() as out:
            cmd_search(args)
        self.assertIn("kafka", out.getvalue())

    def test_search_empty_pattern(self):
        args = FakeArgs(graph=self.path, pattern="", regex=False)
        with capture_stdout() as out:
            cmd_search(args)
        self.assertIn("5", out.getvalue())


# ─────────────────────────────────────────────────────────
# Neighbors
# ─────────────────────────────────────────────────────────

class TestNeighbors(GraphTestCase):

    def test_out_neighbors(self):
        args = FakeArgs(graph=self.path, node="kafka", direction="out")
        with capture_stdout() as out:
            cmd_neighbors(args)
        self.assertIn("zk", out.getvalue())
        self.assertIn("sr", out.getvalue())

    def test_in_neighbors(self):
        args = FakeArgs(graph=self.path, node="kafka", direction="in")
        with capture_stdout() as out:
            cmd_neighbors(args)
        self.assertIn("connect", out.getvalue())

    def test_all_neighbors(self):
        args = FakeArgs(graph=self.path, node="kafka", direction="all")
        with capture_stdout() as out:
            cmd_neighbors(args)
        self.assertIn("zk", out.getvalue())
        self.assertIn("sr", out.getvalue())
        self.assertIn("connect", out.getvalue())

    def test_neighbors_orphan(self):
        args = FakeArgs(graph=self.path, node="orphan", direction="all")
        with capture_stdout() as out:
            cmd_neighbors(args)
        # У сироты 0 связей — проверяем через общее число
        self.assertIn("Всего связей: 0", out.getvalue())

    def test_neighbors_nonexistent(self):
        args = FakeArgs(graph=self.path, node="no-such-node", direction="all")
        with capture_stdout() as out:
            with self.assertRaises(SystemExit):
                cmd_neighbors(args)
        self.assertIn("не найден", out.getvalue())


class TestOrphans(GraphTestCase):
    """Команда orphans."""

    def test_orphans_found(self):
        args = FakeArgs(graph=self.path)
        with capture_stdout() as out:
            cmd_orphans(args)
        text = out.getvalue()
        self.assertIn("1", text)
        self.assertIn("orphan", text)

    def test_orphans_none(self):
        """После удаления сироты их не остаётся."""
        G = load_graph(self.path)
        G.remove_node("orphan")
        save_graph(G, self.path)
        args = FakeArgs(graph=self.path)
        with capture_stdout() as out:
            cmd_orphans(args)
        self.assertIn("нет", out.getvalue())


# ─────────────────────────────────────────────────────────
# Add / Remove Node
# ─────────────────────────────────────────────────────────

class TestAddNode(GraphTestCase):

    def test_add_single_node(self):
        args = FakeArgs(graph=self.path, ids=["redis"],
                        label="Redis", type="БД", desc="In-memory cache",
                        color="#FF0000", size=20)
        cmd_add_node(args)
        G = load_graph(self.path)
        self.assertIn("redis", G)
        self.assertEqual(G.nodes["redis"]["label"], "Redis")
        self.assertEqual(G.nodes["redis"]["type"], "БД")
        self.assertEqual(G.nodes["redis"]["desc"], "In-memory cache")
        self.assertEqual(G.nodes["redis"]["color"], "#FF0000")
        self.assertEqual(G.nodes["redis"]["size"], 20)

    def test_add_multiple_nodes(self):
        args = FakeArgs(graph=self.path, ids=["a", "b", "c"],
                        label=None, type=None, desc=None,
                        color=None, size=None)
        cmd_add_node(args)
        G = load_graph(self.path)
        for nid in ("a", "b", "c"):
            self.assertIn(nid, G)

    def test_add_existing_node(self):
        args = FakeArgs(graph=self.path, ids=["kafka"],
                        label=None, type=None, desc=None,
                        color=None, size=None)
        cmd_add_node(args)
        self.assertEqual(load_graph(self.path).number_of_nodes(), 5)


class TestRemoveNode(GraphTestCase):

    def test_remove_single_node(self):
        cmd_rm_node(FakeArgs(graph=self.path, ids=["orphan"]))
        G = load_graph(self.path)
        self.assertNotIn("orphan", G)
        self.assertEqual(G.number_of_nodes(), 4)

    def test_remove_node_with_connections(self):
        cmd_rm_node(FakeArgs(graph=self.path, ids=["kafka"]))
        self.assertEqual(load_graph(self.path).number_of_edges(), 0)

    def test_remove_multiple_nodes(self):
        cmd_rm_node(FakeArgs(graph=self.path, ids=["orphan", "connect"]))
        G = load_graph(self.path)
        self.assertNotIn("orphan", G)
        self.assertNotIn("connect", G)

    def test_remove_nonexistent_node(self):
        cmd_rm_node(FakeArgs(graph=self.path, ids=["no-such"]))
        self.assertEqual(load_graph(self.path).number_of_nodes(), 5)


# ─────────────────────────────────────────────────────────
# Add / Remove Edge
# ─────────────────────────────────────────────────────────

class TestAddEdge(GraphTestCase):

    def test_add_single_edge(self):
        args = FakeArgs(graph=self.path,
                        sources=["kafka"], targets=["connect"],
                        relation="тест", weight=0.5)
        cmd_add_edge(args)
        G = load_graph(self.path)
        self.assertTrue(G.has_edge("kafka", "connect"))
        self.assertEqual(G.edges["kafka", "connect"]["relation"], "тест")
        self.assertEqual(G.edges["kafka", "connect"]["weight"], 0.5)

    def test_add_multiple_edges(self):
        args = FakeArgs(graph=self.path,
                        sources=["orphan", "orphan"],
                        targets=["kafka", "connect"],
                        relation="тест", weight=1.0)
        cmd_add_edge(args)
        G = load_graph(self.path)
        self.assertTrue(G.has_edge("orphan", "kafka"))
        self.assertTrue(G.has_edge("orphan", "connect"))

    def test_add_existing_edge(self):
        args = FakeArgs(graph=self.path, sources=["kafka"], targets=["zk"],
                        relation="дубль", weight=1.0)
        cmd_add_edge(args)
        G = load_graph(self.path)
        # должно быть ровно одно ребро kafka→zk (редакция не дублируется)
        pairs = [(s, t) for s, t in G.edges() if s == "kafka" and t == "zk"]
        self.assertEqual(len(pairs), 1)

    def test_add_edge_missing_source(self):
        cmd_add_edge(FakeArgs(graph=self.path,
            sources=["no-such"], targets=["kafka"], relation="x", weight=1.0))
        self.assertFalse(load_graph(self.path).has_edge("no-such", "kafka"))

    def test_add_edge_missing_target(self):
        cmd_add_edge(FakeArgs(graph=self.path,
            sources=["kafka"], targets=["no-such"], relation="x", weight=1.0))
        self.assertFalse(load_graph(self.path).has_edge("kafka", "no-such"))


class TestRemoveEdge(GraphTestCase):

    def test_remove_single_edge(self):
        cmd_rm_edge(FakeArgs(graph=self.path, sources=["kafka"], targets=["zk"]))
        self.assertFalse(load_graph(self.path).has_edge("kafka", "zk"))

    def test_remove_multiple_edges(self):
        cmd_rm_edge(FakeArgs(graph=self.path,
            sources=["kafka", "kafka"], targets=["zk", "sr"]))
        G = load_graph(self.path)
        self.assertFalse(G.has_edge("kafka", "zk"))
        self.assertFalse(G.has_edge("kafka", "sr"))

    def test_remove_nonexistent_edge(self):
        cmd_rm_edge(FakeArgs(graph=self.path,
            sources=["kafka"], targets=["orphan"]))
        self.assertTrue(load_graph(self.path).has_edge("kafka", "zk"))


# ─────────────────────────────────────────────────────────
# Render
# ─────────────────────────────────────────────────────────

class TestRender(GraphTestCase):

    def test_render_creates_html(self):
        html_path = self.path.rsplit(".", 1)[0] + ".html"
        try:
            args = FakeArgs(graph=self.path, output=None, engine="d3", theme="dark")
            cmd_render(args)
            self.assertTrue(Path(html_path).exists())
            content = Path(html_path).read_text(encoding="utf-8")
            self.assertIn("<!DOCTYPE html>", content)
            self.assertIn("forceSimulation", content)
            self.assertIn("kafka", content)
        finally:
            Path(html_path).unlink(missing_ok=True)

    def test_render_custom_output(self):
        out = Path(self.path).parent / "custom.html"
        try:
            args = FakeArgs(graph=self.path, output=str(out), engine="d3", theme="light")
            cmd_render(args)
            self.assertTrue(out.exists())
            content = out.read_text(encoding="utf-8")
            self.assertIn("#ffffff", content)  # светлая тема
        finally:
            out.unlink(missing_ok=True)

    def test_render_orphans_detected(self):
        html_path = self.path.rsplit(".", 1)[0] + ".html"
        try:
            args = FakeArgs(graph=self.path, output=None, engine="d3", theme="dark")
            with capture_stdout() as out:
                cmd_render(args)
            self.assertIn("Сирот: 1", out.getvalue())
        finally:
            Path(html_path).unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────
# Error handling — load_graph
# ─────────────────────────────────────────────────────────

class TestLoadGraphErrors(unittest.TestCase):
    """Ошибки загрузки графа."""

    def test_file_not_found(self):
        with self.assertRaises(BeatriceError) as ctx:
            load_graph("/no/such/file.json")
        self.assertIn("не найден", str(ctx.exception))

    def test_invalid_json(self):
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        path = tmp.name
        tmp.write("not valid json")
        tmp.close()
        try:
            with self.assertRaises(BeatriceError) as ctx:
                load_graph(path)
            self.assertIn("JSON", str(ctx.exception))
        finally:
            os.unlink(path)

    def test_not_a_graph(self):
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        path = tmp.name
        tmp.write('{"hello": "world"}')
        tmp.close()
        try:
            with self.assertRaises(BeatriceError) as ctx:
                load_graph(path)
            self.assertIn("графа", str(ctx.exception))
        finally:
            os.unlink(path)


# ─────────────────────────────────────────────────────────
# Error handling — search
# ─────────────────────────────────────────────────────────

class TestSearchErrors(GraphTestCase):
    """Ошибки поиска."""

    def test_invalid_regex(self):
        """Невалидный regex."""
        args = FakeArgs(graph=self.path, pattern="[", regex=True)
        with capture_stdout() as out:
            with self.assertRaises(SystemExit):
                cmd_search(args)
        self.assertIn("регулярное", out.getvalue())


# ─────────────────────────────────────────────────────────
# Error handling — add-edge / rm-edge mismatched lengths
# ─────────────────────────────────────────────────────────

class TestEdgeMismatch(GraphTestCase):
    """Несовпадение длин массивов sources/targets."""

    def test_add_edge_mismatch(self):
        args = FakeArgs(graph=self.path,
                        sources=["kafka", "zk"], targets=["zk"],
                        relation="x", weight=1.0)
        with capture_stdout() as out:
            with self.assertRaises(SystemExit):
                cmd_add_edge(args)
        self.assertIn("количество", out.getvalue())

    def test_rm_edge_mismatch(self):
        args = FakeArgs(graph=self.path,
                        sources=["kafka", "zk"], targets=["zk"],
                        relation="x", weight=1.0)
        with capture_stdout() as out:
            with self.assertRaises(SystemExit):
                cmd_rm_edge(args)
        self.assertIn("количество", out.getvalue())


if __name__ == "__main__":
    unittest.main()
