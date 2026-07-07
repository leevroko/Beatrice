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
    cmd_search, cmd_neighbors, cmd_orphans, cmd_roots, cmd_frontier,
    cmd_islands, cmd_louvain, cmd_ring,
    cmd_intersect, cmd_union, cmd_diff, cmd_symdiff,    cmd_add_node, cmd_rm_node,
    cmd_add_edge, cmd_rm_edge, cmd_edit_node, cmd_render,
    cmd_tag_add, cmd_tag_rm, cmd_tag_ls, cmd_tag_clear, apply_tag_filter)


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
        self.tag = []
        self.tag_mode = "any"
        self.output_format = "text"
        self.counts = False
        self.by_community = False
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

# ─────────────────────────────────────────────────────────
# Edit Node
# ─────────────────────────────────────────────────────────

class TestEditNode(GraphTestCase):
    """Команда edit-node."""

    def test_edit_label(self):
        args = FakeArgs(graph=self.path, ids=["kafka"],
                        label="Apache Kafka", type=None, desc=None,
                        color=None, size=None)
        cmd_edit_node(args)
        G = load_graph(self.path)
        self.assertEqual(G.nodes["kafka"]["label"], "Apache Kafka")
        self.assertEqual(G.nodes["kafka"]["type"], "брокер")

    def test_edit_multiple_attrs(self):
        args = FakeArgs(graph=self.path, ids=["kafka"],
                        label="Apache Kafka", type="streaming",
                        desc="New desc", color="#FF0000", size=15.0)
        cmd_edit_node(args)
        G = load_graph(self.path)
        self.assertEqual(G.nodes["kafka"]["label"], "Apache Kafka")
        self.assertEqual(G.nodes["kafka"]["type"], "streaming")
        self.assertEqual(G.nodes["kafka"]["desc"], "New desc")
        self.assertEqual(G.nodes["kafka"]["color"], "#FF0000")
        self.assertEqual(G.nodes["kafka"]["size"], 15.0)

    def test_edit_multiple_nodes(self):
        """Редактирование нескольких узлов одной командой."""
        args = FakeArgs(graph=self.path, ids=["kafka", "zk"],
                        label="Edited", type=None, desc=None,
                        color=None, size=None)
        cmd_edit_node(args)
        G = load_graph(self.path)
        self.assertEqual(G.nodes["kafka"]["label"], "Edited")
        self.assertEqual(G.nodes["zk"]["label"], "Edited")

    def test_edit_nonexistent(self):
        """Несуществующий узел пропускается с предупреждением, не exit."""
        args = FakeArgs(graph=self.path, ids=["no-such"],
                        label="X", type=None, desc=None,
                        color=None, size=None)
        with capture_stdout() as out:
            cmd_edit_node(args)
        self.assertIn("Предупреждение", out.getvalue())

    def test_edit_no_changes(self):
        args = FakeArgs(graph=self.path, ids=["kafka"],
                        label=None, type=None, desc=None,
                        color=None, size=None)
        with capture_stdout() as out:
            cmd_edit_node(args)
        self.assertIn("Ничего не изменено", out.getvalue())
        G = load_graph(self.path)
        self.assertEqual(G.nodes["kafka"]["label"], "Kafka")

    def test_edit_clear_field(self):
        args = FakeArgs(graph=self.path, ids=["kafka"],
                        label=None, type="", desc=None,
                        color=None, size=None)
        cmd_edit_node(args)
        G = load_graph(self.path)
        self.assertEqual(G.nodes["kafka"]["type"], "")
        self.assertEqual(G.nodes["kafka"]["label"], "Kafka")


# ─────────────────────────────────────────────────────────
# Islands
# ─────────────────────────────────────────────────────────

class TestIslands(GraphTestCase):
    """Команда islands."""

    def test_multiple_islands(self):
        args = FakeArgs(graph=self.path)
        with capture_stdout() as out:
            cmd_islands(args)
        text = out.getvalue()
        self.assertIn("Остров #1", text)
        self.assertIn("kafka", text)
        self.assertIn("Остров #2", text)
        self.assertIn("orphan", text)
        self.assertIn("Всего островов: 2", text)

    def test_single_island(self):
        """После удаления сироты — один остров."""
        G = load_graph(self.path)
        G.remove_node("orphan")
        save_graph(G, self.path)
        args = FakeArgs(graph=self.path)
        with capture_stdout() as out:
            cmd_islands(args)
        text = out.getvalue()
        self.assertIn("Остров #1 (4 узла)", text)
        self.assertIn("Всего островов: 1", text)

    def test_all_orphans(self):
        """Все узлы — сироты = каждый узел свой остров."""
        G = nx.DiGraph()
        for i in range(3):
            G.add_node(f"n{i}", label=f"Node{i}")
        save_graph(G, self.path)
        args = FakeArgs(graph=self.path)
        with capture_stdout() as out:
            cmd_islands(args)
        text = out.getvalue()
        self.assertIn("👻 сирота", text)
        self.assertIn("Всего островов: 3", text)

    def test_empty_graph(self):
        G = nx.DiGraph()
        save_graph(G, self.path)
        args = FakeArgs(graph=self.path)
        with capture_stdout() as out:
            cmd_islands(args)
        self.assertIn("Граф пуст", out.getvalue())


# ─────────────────────────────────────────────────────────
# Roots + Frontier
# ─────────────────────────────────────────────────────────

class TestRoots(GraphTestCase):
    """Команда roots."""

    def test_roots_found(self):
        """connect ссылается на kafka, на connect никто не ссылается."""
        args = FakeArgs(graph=self.path)
        with capture_stdout() as out:
            cmd_roots(args)
        text = out.getvalue()
        self.assertIn("connect", text)
        self.assertNotIn("kafka", text)

    def test_roots_none(self):
        """После удаления connect — kafka становится корнем. Полностью изолируем."""
        G = load_graph(self.path)
        G.remove_node("kafka")
        G.remove_node("connect")
        save_graph(G, self.path)
        args = FakeArgs(graph=self.path)
        with capture_stdout() as out:
            cmd_roots(args)
        self.assertIn("нет", out.getvalue())


class TestFrontier(GraphTestCase):
    """Команда frontier."""

    def test_frontier_found(self):
        """zk и sr — на них ссылаются, но сами никуда не ссылаются."""
        args = FakeArgs(graph=self.path)
        with capture_stdout() as out:
            cmd_frontier(args)
        text = out.getvalue()
        self.assertIn("zk", text)
        self.assertIn("sr", text)
        self.assertNotIn("kafka", text)
        self.assertNotIn("connect", text)

    def test_frontier_orphan_excluded(self):
        """orphan не имеет in_degree, не входит в frontier."""
        args = FakeArgs(graph=self.path)
        with capture_stdout() as out:
            cmd_frontier(args)
        self.assertNotIn("orphan", out.getvalue())


# ─────────────────────────────────────────────────────────
# Set operations: intersect, union, diff, symdiff
# ─────────────────────────────────────────────────────────

class TestSetOps(GraphTestCase):
    """Операции над множествами графов."""

    def setUp(self):
        super().setUp()
        # G1: тестовый граф из make_test_graph() — 5 узлов
        # G2: создаём второй граф с пересекающимися узлами
        self.path2 = self.path + ".g2.json"
        G2 = nx.DiGraph()
        G2.add_node("kafka", label="Kafka", type="брокер")
        G2.add_node("redis", label="Redis", type="БД")
        G2.add_edge("kafka", "redis", relation="использует")
        save_graph(G2, self.path2)

    def tearDown(self):
        super().tearDown()
        from pathlib import Path
        Path(self.path2).unlink(missing_ok=True)

    def _capture(self, cmd, **kwargs):
        """Выполнить команду, вернуть parsed JSON."""
        with capture_stdout() as out:
            cmd(FakeArgs(graph1=self.path, graph2=self.path2))
        return json.loads(out.getvalue())

    def test_intersect(self):
        """kafka есть в обоих графах."""
        data = self._capture(cmd_intersect)
        ids = [n["id"] for n in data["nodes"]]
        self.assertIn("kafka", ids)
        self.assertNotIn("redis", ids)
        self.assertNotIn("zk", ids)

    def test_union(self):
        """Все узлы из обоих графов."""
        data = self._capture(cmd_union)
        ids = [n["id"] for n in data["nodes"]]
        self.assertIn("kafka", ids)
        self.assertIn("redis", ids)
        self.assertIn("zk", ids)
        # kafka→redis должен быть
        self.assertTrue(any(e["source"] == "kafka" and e["target"] == "redis" for e in data["edges"]))

    def test_diff(self):
        """Узлы из G1, которых нет в G2: zk, sr, connect, orphan."""
        data = self._capture(cmd_diff)
        ids = [n["id"] for n in data["nodes"]]
        self.assertNotIn("kafka", ids)
        self.assertIn("zk", ids)
        self.assertIn("sr", ids)
        self.assertIn("connect", ids)
        self.assertIn("orphan", ids)

    def test_symdiff(self):
        """Узлы только в одном из графов: zk, sr, connect, orphan, redis (kafka в обоих)."""
        data = self._capture(cmd_symdiff)
        ids = [n["id"] for n in data["nodes"]]
        self.assertNotIn("kafka", ids)  # в обоих — не попадает
        self.assertIn("redis", ids)      # только в G2
        self.assertIn("zk", ids)         # только в G1


# ─────────────────────────────────────────────────────────
# Output format: --json
# ─────────────────────────────────────────────────────────

class TestOutputFormat(GraphTestCase):
    """Тесты для --json / --output-format json."""

    def test_search_json(self):
        args = FakeArgs(graph=self.path, pattern="", regex=False,
                        output_format="json", tag=[], tag_mode="any")
        with capture_stdout() as out:
            cmd_search(args)
        import json
        data = json.loads(out.getvalue())
        self.assertIn("nodes", data)
        self.assertIn("edges", data)
        self.assertGreater(len(data["nodes"]), 0)

    def test_roots_json(self):
        args = FakeArgs(graph=self.path, output_format="json")
        with capture_stdout() as out:
            cmd_roots(args)
        import json
        data = json.loads(out.getvalue())
        self.assertIn("nodes", data)
        self.assertGreater(len(data["nodes"]), 0)

    def test_frontier_json(self):
        args = FakeArgs(graph=self.path, output_format="json")
        with capture_stdout() as out:
            cmd_frontier(args)
        import json
        data = json.loads(out.getvalue())
        self.assertIn("nodes", data)
        self.assertIn("edges", data)

    def test_search_no_match_json(self):
        """Пустой результат — пустой граф."""
        args = FakeArgs(graph=self.path, pattern="__nosuch__", regex=False,
                        output_format="json", tag=[], tag_mode="any")
        with capture_stdout() as out:
            cmd_search(args)
        import json
        data = json.loads(out.getvalue())
        self.assertEqual(len(data["nodes"]), 0)
        self.assertEqual(len(data["edges"]), 0)

    def test_stdin_load(self):
        """Проверить, что load_graph('-') читает JSON из stdin."""
        import io
        G = nx.DiGraph()
        G.add_node("test", label="Test")
        input_json = json.dumps(nx.node_link_data(G))
        old_stdin = sys.stdin
        sys.stdin = io.StringIO(input_json)
        try:
            loaded = load_graph("-")
            self.assertIn("test", loaded)
        finally:
            sys.stdin = old_stdin


# ─────────────────────────────────────────────────────────
# Tags — CRUD
# ─────────────────────────────────────────────────────────

class TestTagCRUD(GraphTestCase):
    """Команда tag: add, rm, ls, clear."""

    def test_tag_add(self):
        cmd_tag_add(FakeArgs(graph=self.path, ids=["kafka"],
                             tags=["streaming", "kafka-экосистема"]))
        G = load_graph(self.path)
        self.assertCountEqual(G.nodes["kafka"]["tags"],
                              ["streaming", "kafka-экосистема"])

    def test_tag_add_multiple_nodes(self):
        cmd_tag_add(FakeArgs(graph=self.path, ids=["kafka", "zk"],
                             tags=["test"]))
        G = load_graph(self.path)
        self.assertIn("test", G.nodes["kafka"]["tags"])
        self.assertIn("test", G.nodes["zk"]["tags"])

    def test_tag_rm(self):
        cmd_tag_add(FakeArgs(graph=self.path, ids=["kafka"],
                             tags=["streaming", "temp"]))
        cmd_tag_rm(FakeArgs(graph=self.path, ids=["kafka"],
                            tags=["temp"]))
        G = load_graph(self.path)
        self.assertIn("streaming", G.nodes["kafka"]["tags"])
        self.assertNotIn("temp", G.nodes["kafka"]["tags"])

    def test_tag_ls_node(self):
        cmd_tag_add(FakeArgs(graph=self.path, ids=["kafka"],
                             tags=["streaming"]))
        with capture_stdout() as out:
            cmd_tag_ls(FakeArgs(graph=self.path, id="kafka"))
        self.assertIn("streaming", out.getvalue())

    def test_tag_ls_all(self):
        cmd_tag_add(FakeArgs(graph=self.path, ids=["kafka"],
                             tags=["a"]))
        cmd_tag_add(FakeArgs(graph=self.path, ids=["zk"],
                             tags=["b"]))
        with capture_stdout() as out:
            cmd_tag_ls(FakeArgs(graph=self.path, id=None))
        text = out.getvalue()
        self.assertIn("a", text)
        self.assertIn("b", text)

    def test_tag_clear(self):
        cmd_tag_add(FakeArgs(graph=self.path, ids=["kafka"],
                             tags=["x", "y"]))
        cmd_tag_clear(FakeArgs(graph=self.path, ids=["kafka"]))
        G = load_graph(self.path)
        self.assertEqual(G.nodes["kafka"]["tags"], [])

    def test_tag_nonexistent_node(self):
        cmd_tag_add(FakeArgs(graph=self.path, ids=["no-such"],
                             tags=["x"]))
        G = load_graph(self.path)
        self.assertEqual(G.number_of_nodes(), 5)


# ─────────────────────────────────────────────────────────
# Tags — filter on search/islands/neighbors/ring
# ─────────────────────────────────────────────────────────

class TestTagFilter(GraphTestCase):
    """Фильтрация по тегам."""

    def setUp(self):
        super().setUp()
        cmd_tag_add(FakeArgs(graph=self.path, ids=["kafka", "zk", "sr"],
                             tags=["kafka-экосистема"]))
        cmd_tag_add(FakeArgs(graph=self.path, ids=["connect"],
                             tags=["integration"]))

    def test_search_tag_filter(self):
        """Поиск только среди узлов с тегом kafka-экосистема."""
        args = FakeArgs(graph=self.path, pattern="", regex=False,
                        tag=["kafka-экосистема"], tag_mode="any")
        with capture_stdout() as out:
            cmd_search(args)
        text = out.getvalue()
        self.assertIn("kafka", text)
        self.assertIn("zk", text)
        self.assertNotIn("orphan", text)
        self.assertNotIn("connect", text)

    def test_search_tag_mode_all(self):
        """Поиск с tag-mode=all (должен быть и kafka-экосистема, и что-то ещё)."""
        G = load_graph(self.path)
        G.nodes["kafka"]["tags"] = ["kafka-экосистема", "extra"]
        save_graph(G, self.path)
        args = FakeArgs(graph=self.path, pattern="", regex=False,
                        tag=["kafka-экосистема", "extra"], tag_mode="all")
        with capture_stdout() as out:
            cmd_search(args)
        text = out.getvalue()
        self.assertIn("kafka", text)
        self.assertNotIn("zk", text)

    def test_islands_tag_filter(self):
        """Острова только среди узлов с тегом kafka-экосистема."""
        args = FakeArgs(graph=self.path, tag=["kafka-экосистема"], tag_mode="any")
        with capture_stdout() as out:
            cmd_islands(args)
        text = out.getvalue()
        self.assertIn("kafka", text)
        self.assertNotIn("connect", text)

    def test_neighbors_tag_filter(self):
        """Соседи Kafka, только если у них есть тег."""
        args = FakeArgs(graph=self.path, node="kafka", direction="out",
                        tag=["kafka-экосистема"], tag_mode="any")
        with capture_stdout() as out:
            cmd_neighbors(args)
        # У zk есть тег, у sr есть тег
        self.assertIn("zk", out.getvalue())

    def test_ring_no_tag(self):
        """Без --tag работает как обычно."""
        args = FakeArgs(graph=self.path, node="kafka", min=0, max=1,
                        direction="omnidirectional", tag=[], tag_mode="any")
        with capture_stdout() as out:
            cmd_ring(args)
        self.assertIn("Глубина 1", out.getvalue())
        self.assertIn("zk", out.getvalue())


# ─────────────────────────────────────────────────────────
# Louvain communities
# ─────────────────────────────────────────────────────────

class TestLouvain(GraphTestCase):
    """Команда louvain."""

    def test_louvain_communities(self):
        """Проверить, что сообщества найдены."""
        args = FakeArgs(graph=self.path, seed=42)
        with capture_stdout() as out:
            cmd_louvain(args)
        text = out.getvalue()
        self.assertIn("Сообщество #1", text)
        self.assertIn("Всего сообществ", text)
        # Убедимся, что узлы из графа отображаются
        self.assertIn("kafka", text)
        self.assertIn("orphan", text)

    def test_louvain_single_node(self):
        """Граф из одного узла — одно сообщество."""
        G = nx.DiGraph()
        G.add_node("single", label="Solo")
        save_graph(G, self.path)
        args = FakeArgs(graph=self.path, seed=42)
        with capture_stdout() as out:
            cmd_louvain(args)
        text = out.getvalue()
        self.assertIn("Сообщество #1", text)
        self.assertIn("single", text)
        self.assertIn("Всего сообществ: 1", text)

    def test_louvain_empty(self):
        """Пустой граф."""
        G = nx.DiGraph()
        save_graph(G, self.path)
        args = FakeArgs(graph=self.path, seed=42)
        with capture_stdout() as out:
            cmd_louvain(args)
        self.assertIn("Граф пуст", out.getvalue())

    def test_louvain_deterministic_seed(self):
        """Одинаковый seed → одинаковый результат."""
        args1 = FakeArgs(graph=self.path, seed=42)
        args2 = FakeArgs(graph=self.path, seed=42)
        with capture_stdout() as out1:
            cmd_louvain(args1)
        with capture_stdout() as out2:
            cmd_louvain(args2)
        self.assertEqual(out1.getvalue(), out2.getvalue())


# ─────────────────────────────────────────────────────────
# Ring
# ─────────────────────────────────────────────────────────

class TestRing(unittest.TestCase):
    """Команда ring."""

    def setUp(self):
        """Цепочка: a → b → c → d → e."""
        self.tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        self.path = self.tmp.name
        G = nx.DiGraph()
        G.add_node("a", label="A")
        G.add_node("b", label="B")
        G.add_node("c", label="C")
        G.add_node("d", label="D")
        G.add_node("e", label="E")
        G.add_edge("a", "b", relation="→")
        G.add_edge("b", "c", relation="→")
        G.add_edge("c", "d", relation="→")
        G.add_edge("d", "e", relation="→")
        save_graph(G, self.path)

    def tearDown(self):
        os.unlink(self.path)

    def test_range_depth(self):
        """Глубины 2–4 от a (all) = c, d (a→b→c→d—глуб.4 только d).
        depths: a=0, b=1, c=2, d=3, e=4
        --min=2, --max=4 → XOR(глуб.1-4 vs глуб.1-2) = глуб.3-4 → d, e
        """
        args = FakeArgs(graph=self.path, node="a",
                        min=2, max=4, direction="omnidirectional")
        with capture_stdout() as out:
            cmd_ring(args)
        text = out.getvalue()
        self.assertIn("Кольца 3–4", text)
        self.assertIn("d", text)
        self.assertIn("e", text)
        self.assertNotIn("b", text)
        self.assertNotIn("c", text)
        self.assertIn("Найдено: 2", text)

    def test_immediate_neighbors(self):
        """Глубины 0–1 от a = только b."""
        args = FakeArgs(graph=self.path, node="a",
                        min=0, max=1, direction="omnidirectional")
        with capture_stdout() as out:
            cmd_ring(args)
        text = out.getvalue()
        self.assertIn("Глубина 1", text)
        self.assertIn("b", text)
        self.assertNotIn("c", text)
        self.assertIn("Найдено: 1", text)

    def test_no_nodes_in_range(self):
        """Диапазон глубже, чем есть узлов."""
        args = FakeArgs(graph=self.path, node="a",
                        min=10, max=20, direction="omnidirectional")
        with capture_stdout() as out:
            cmd_ring(args)
        self.assertIn("Нет узлов", out.getvalue())

    def test_min_equals_max(self):
        """min == max — результат всегда пуст (XOR одинаковых множеств)."""
        args = FakeArgs(graph=self.path, node="a",
                        min=2, max=2, direction="omnidirectional")
        with capture_stdout() as out:
            cmd_ring(args)
        self.assertIn("Нет узлов", out.getvalue())

    def test_direction_descending(self):
        """Только нисходящие (successors). a→b→c: depths a=0,b=1,c=2."""
        args = FakeArgs(graph=self.path, node="a",
                        min=0, max=2, direction="descending")
        with capture_stdout() as out:
            cmd_ring(args)
        text = out.getvalue()
        self.assertIn("b", text)
        self.assertIn("c", text)

    def test_direction_ascending(self):
        """Только восходящие (predecessors). Из e: e→d→c."""
        args = FakeArgs(graph=self.path, node="e",
                        min=0, max=2, direction="ascending")
        with capture_stdout() as out:
            cmd_ring(args)
        text = out.getvalue()
        self.assertIn("d", text)
        self.assertIn("c", text)
        self.assertNotIn("b", text)

    def test_nonexistent_node(self):
        args = FakeArgs(graph=self.path, node="no-such",
                        min=0, max=1, direction="omnidirectional")
        with capture_stdout() as out:
            with self.assertRaises(SystemExit):
                cmd_ring(args)
        self.assertIn("не найден", out.getvalue())

    def test_negative_min(self):
        args = FakeArgs(graph=self.path, node="a",
                        min=-1, max=2, direction="omnidirectional")
        with capture_stdout() as out:
            with self.assertRaises(SystemExit):
                cmd_ring(args)
        self.assertIn("отрицательным", out.getvalue())

    def test_min_greater_than_max(self):
        args = FakeArgs(graph=self.path, node="a",
                        min=5, max=3, direction="omnidirectional")
        with capture_stdout() as out:
            with self.assertRaises(SystemExit):
                cmd_ring(args)
        self.assertIn("меньше --min", out.getvalue())


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
