"""FastAPI-сервер для Beatrice Web GUI.

WebSocket JSON-RPC протокол.
"""

import json
import sys
import asyncio
from pathlib import Path
from typing import Any, Optional
from collections import Counter

import networkx as nx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from beatrice.cli import load_graph, save_graph, BeatriceError

# ────── Graph Manager ──────


class WebGraphManager:
    """Управление графом для Web GUI.

    Обёртка над NetworkX с методами, аналогичными TUI GraphManager,
    без undo/redo (WebSocket инкрементальные события вместо этого).
    """

    def __init__(self):
        self.G: nx.DiGraph = nx.DiGraph()
        self.path: Optional[str] = None
        self._dirty: bool = False
        self._counter: int = 0

    def load(self, path: str) -> None:
        self.G = load_graph(path)
        self.path = path
        self._dirty = False
        self._counter = self.G.graph.get("beatrice_counter", 0)

    def save(self) -> None:
        if self.path is None:
            raise BeatriceError("Путь к файлу не указан")
        self.G.graph["beatrice_counter"] = self._counter
        save_graph(self.G, self.path)
        self._dirty = False

    def reload(self) -> None:
        if self.path is None:
            raise BeatriceError("Путь к файлу не указан")
        self.load(self.path)

    @property
    def dirty(self) -> bool:
        return self._dirty

    # ────── Узлы ──────

    def add_node(self, node_id: str, **attrs) -> dict:
        if self.G.has_node(node_id):
            raise BeatriceError(f"Узел «{node_id}» уже существует")
        self.G.add_node(node_id, **attrs)
        self._dirty = True
        return self._node_data(node_id)

    def remove_node(self, node_id: str) -> None:
        if not self.G.has_node(node_id):
            raise BeatriceError(f"Узел «{node_id}» не найден")
        self.G.remove_node(node_id)
        self._dirty = True

    def update_node(self, node_id: str, **attrs) -> dict:
        if not self.G.has_node(node_id):
            raise BeatriceError(f"Узел «{node_id}» не найден")
        for key, value in attrs.items():
            if value is not None:
                self.G.nodes[node_id][key] = value
        self._dirty = True
        return self._node_data(node_id)

    def get_node(self, node_id: str) -> dict:
        if not self.G.has_node(node_id):
            raise BeatriceError(f"Узел «{node_id}» не найден")
        return self._node_data(node_id)

    def list_nodes(self) -> list[dict]:
        return [self._node_data(n) for n in self.G.nodes()]

    def search_nodes(self, pattern: str) -> list[dict]:
        plow = pattern.lower()
        matches = []
        for n in self.G.nodes():
            label = self.G.nodes[n].get("label", "")
            if plow in n.lower() or plow in label.lower():
                matches.append(self._node_data(n))
        return matches

    def move_node(self, old_id: str, new_id: str) -> None:
        if not self.G.has_node(old_id):
            raise BeatriceError(f"Узел «{old_id}» не найден")
        if self.G.has_node(new_id):
            raise BeatriceError(f"Узел «{new_id}» уже существует")
        nx.relabel_nodes(self.G, {old_id: new_id}, copy=False)
        self._dirty = True

    # ────── Связи ──────

    def add_edge(self, source: str, target: str, **attrs) -> dict:
        if not self.G.has_node(source):
            raise BeatriceError(f"Узел-источник «{source}» не найден")
        if not self.G.has_node(target):
            raise BeatriceError(f"Узел-цель «{target}» не найден")
        if self.G.has_edge(source, target):
            raise BeatriceError(f"Ребро {source}→{target} уже существует")
        self.G.add_edge(source, target, **attrs)
        self._dirty = True
        return self._edge_data(source, target)

    def remove_edge(self, source: str, target: str) -> None:
        if not self.G.has_edge(source, target):
            raise BeatriceError(f"Ребро {source}→{target} не найдено")
        self.G.remove_edge(source, target)
        self._dirty = True

    def update_edge(self, source: str, target: str, **attrs) -> dict:
        if not self.G.has_edge(source, target):
            raise BeatriceError(f"Ребро {source}→{target} не найдено")
        for key, value in attrs.items():
            if value is not None:
                self.G.edges[source, target][key] = value
        self._dirty = True
        return self._edge_data(source, target)

    def list_edges(self) -> list[dict]:
        return [self._edge_data(s, t) for s, t in self.G.edges()]

    def list_edges_for_node(self, node_id: str) -> dict:
        if not self.G.has_node(node_id):
            raise BeatriceError(f"Узел «{node_id}» не найден")
        outgoing = []
        for _, tgt, data in self.G.out_edges(node_id, data=True):
            outgoing.append({
                "source": node_id,
                "target": tgt,
                "relation": data.get("relation", ""),
                "weight": data.get("weight", 1.0),
                "target_label": self.G.nodes[tgt].get("label", tgt),
                "target_type": self.G.nodes[tgt].get("type", ""),
            })
        incoming = []
        for src, _, data in self.G.in_edges(node_id, data=True):
            incoming.append({
                "source": src,
                "target": node_id,
                "relation": data.get("relation", ""),
                "weight": data.get("weight", 1.0),
                "source_label": self.G.nodes[src].get("label", src),
                "source_type": self.G.nodes[src].get("type", ""),
            })
        return {"outgoing": outgoing, "incoming": incoming}

    # ────── Теги ──────

    def tag_add(self, node_ids: list[str], tags: list[str]) -> dict:
        results = {}
        for nid in node_ids:
            if not self.G.has_node(nid):
                results[nid] = {"error": f"Узел «{nid}» не найден"}
                continue
            existing = set(self.G.nodes[nid].get("tags", []))
            existing.update(tags)
            self.G.nodes[nid]["tags"] = list(existing)
            self._dirty = True
            results[nid] = {"tags": list(existing)}
        return results

    def tag_remove(self, node_ids: list[str], tags: list[str]) -> dict:
        results = {}
        tags_to_rm = set(tags)
        for nid in node_ids:
            if not self.G.has_node(nid):
                results[nid] = {"error": f"Узел «{nid}» не найден"}
                continue
            existing = set(self.G.nodes[nid].get("tags", []))
            existing -= tags_to_rm
            self.G.nodes[nid]["tags"] = list(existing)
            self._dirty = True
            results[nid] = {"tags": list(existing)}
        return results

    def tag_clear(self, node_ids: list[str]) -> dict:
        results = {}
        for nid in node_ids:
            if not self.G.has_node(nid):
                results[nid] = {"error": f"Узел «{nid}» не найден"}
                continue
            self.G.nodes[nid]["tags"] = []
            self._dirty = True
            results[nid] = {"tags": []}
        return results

    def tag_list(self, node_id: Optional[str] = None) -> Any:
        if node_id:
            if not self.G.has_node(node_id):
                raise BeatriceError(f"Узел «{node_id}» не найден")
            return {
                "node_id": node_id,
                "tags": self.G.nodes[node_id].get("tags", []),
            }
        counter: Counter[str] = Counter()
        for n in self.G.nodes():
            for t in self.G.nodes[n].get("tags", []):
                counter[t] += 1
        return {
            "tags": [
                {"tag": t, "count": c}
                for t, c in sorted(counter.items(), key=lambda x: -x[1])
            ]
        }

    def tag_nodes(self, tags: list[str], mode: str = "any") -> list[dict]:
        query = set(tags)
        result = []
        for n in self.G.nodes():
            node_tags = set(self.G.nodes[n].get("tags", []))
            if mode == "any" and (node_tags & query):
                result.append(self._node_data(n))
            elif mode == "all" and (query <= node_tags):
                result.append(self._node_data(n))
            elif mode == "none" and not (node_tags & query):
                result.append(self._node_data(n))
        return result

    # ────── Граф (визуализация) ──────

    def get_graph_state(self) -> dict:
        """Полный дамп графа для инициализации клиента."""
        orphans = [n for n, d in self.G.degree() if d == 0]

        # Louvain
        try:
            from networkx.algorithms.community import louvain_communities
            communities = list(louvain_communities(self.G.to_undirected(), seed=42))
            node_community = {}
            for i, comm in enumerate(communities):
                for n in comm:
                    node_community[n] = i
            louvain_available = True
        except Exception:
            node_community = {}
            louvain_available = False

        nodes = []
        for n in self.G.nodes():
            nd = self._node_data(n)
            nd["community"] = node_community.get(n, 0)
            nd["isOrphan"] = n in orphans
            nd["degree"] = self.G.degree(n)
            nodes.append(nd)

        edges = [self._edge_data(s, t) for s, t in self.G.edges()]

        types = {}
        for n in self.G.nodes():
            t = self.G.nodes[n].get("type", "") or "unknown"
            c = self.G.nodes[n].get("color", "#999")
            if t not in types:
                types[t] = c

        return {
            "nodes": nodes,
            "edges": edges,
            "orphans": orphans,
            "types": types,
            "louvainAvailable": louvain_available,
            "stats": self.get_graph_stats(),
        }

    def get_graph_stats(self) -> dict:
        orphans = [n for n, d in self.G.degree() if d == 0]
        stats = {
            "nodes": self.G.number_of_nodes(),
            "edges": self.G.number_of_edges(),
            "density": round(nx.density(self.G), 4),
            "orphans": len(orphans),
        }
        try:
            from networkx.algorithms.community import louvain_communities
            comms = louvain_communities(self.G.to_undirected(), seed=42)
            stats["louvainCommunities"] = len(comms)
        except Exception:
            pass
        try:
            from networkx.algorithms.components import weakly_connected_components
            islands = list(weakly_connected_components(self.G))
            stats["islands"] = len(islands)
        except Exception:
            pass
        try:
            ranks = nx.pagerank(self.G)
            top5 = sorted(ranks.items(), key=lambda x: -x[1])[:5]
            stats["pagerankTop5"] = [{"id": n, "rank": round(r, 4)} for n, r in top5]
        except Exception:
            pass
        return stats

    def get_louvain(self) -> dict:
        from networkx.algorithms.community import louvain_communities
        communities = list(louvain_communities(self.G.to_undirected(), seed=42))
        palette = [
            "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4",
            "#42d4f4", "#f032e6", "#bfef45", "#fabed4", "#469990", "#dcbeff",
        ]
        comms = []
        for i, comm in enumerate(communities):
            comms.append({
                "id": i,
                "color": palette[i % len(palette)],
                "size": len(comm),
                "members": sorted(comm),
            })
        return {"communities": comms}

    def get_neighbors(self, node_id: str, direction: str = "all") -> dict:
        if not self.G.has_node(node_id):
            raise BeatriceError(f"Узел «{node_id}» не найден")
        result: dict[str, list] = {"outgoing": [], "incoming": []}
        if direction in ("out", "all"):
            for _, tgt, data in self.G.out_edges(node_id, data=True):
                result["outgoing"].append({
                    "id": tgt,
                    "label": self.G.nodes[tgt].get("label", tgt),
                    "type": self.G.nodes[tgt].get("type", ""),
                    "relation": data.get("relation", ""),
                })
        if direction in ("in", "all"):
            for src, _, data in self.G.in_edges(node_id, data=True):
                result["incoming"].append({
                    "id": src,
                    "label": self.G.nodes[src].get("label", src),
                    "type": self.G.nodes[src].get("type", ""),
                    "relation": data.get("relation", ""),
                })
        return result

    def get_ring(self, node_id: str, min_depth: int, max_depth: int,
                 direction: str = "omnidirectional") -> dict:
        if not self.G.has_node(node_id):
            raise BeatriceError(f"Узел «{node_id}» не найден")
        from collections import deque
        depths: dict[str, int] = {}
        q = deque()
        q.append((node_id, 0))
        while q:
            cur, d = q.popleft()
            if cur in depths:
                continue
            depths[cur] = d
            if d >= max_depth:
                continue
            if direction in ("omnidirectional", "descending"):
                for nxt in self.G.successors(cur):
                    if nxt not in depths:
                        q.append((nxt, d + 1))
            if direction in ("omnidirectional", "ascending"):
                for nxt in self.G.predecessors(cur):
                    if nxt not in depths:
                        q.append((nxt, d + 1))
        result = []
        for nid, d in depths.items():
            if d == 0:
                continue
            if min_depth < d <= max_depth:
                result.append({
                    "id": nid,
                    "depth": d,
                    "label": self.G.nodes[nid].get("label", nid),
                    "type": self.G.nodes[nid].get("type", ""),
                })
        return {"rings": result, "node": node_id}

    def get_islands(self) -> dict:
        from networkx.algorithms.components import weakly_connected_components
        components = sorted(
            weakly_connected_components(self.G),
            key=len, reverse=True,
        )
        orphans_set = set(n for n, d in self.G.degree() if d == 0)
        islands = []
        for i, comp in enumerate(components, 1):
            is_orphan = all(n in orphans_set for n in comp)
            islands.append({
                "id": i,
                "size": len(comp),
                "isOrphan": is_orphan,
                "members": [
                    {"id": n, "label": self.G.nodes[n].get("label", n),
                     "type": self.G.nodes[n].get("type", "")}
                    for n in sorted(comp)
                ],
            })
        return {"islands": islands}

    def get_roots(self) -> list[dict]:
        roots = [
            n for n in self.G.nodes()
            if self.G.out_degree(n) > 0 and self.G.in_degree(n) == 0
        ]
        return [self._node_data(n) for n in roots]

    def get_frontier(self) -> list[dict]:
        frontier = [
            n for n in self.G.nodes()
            if self.G.in_degree(n) > 0 and self.G.out_degree(n) == 0
        ]
        return [self._node_data(n) for n in frontier]

    # ────── Helpers ──────

    def _node_data(self, node_id: str) -> dict:
        nd = self.G.nodes[node_id]
        return {
            "id": node_id,
            "label": nd.get("label", node_id),
            "type": nd.get("type", ""),
            "desc": nd.get("desc", ""),
            "color": nd.get("color", "#999"),
            "size": nd.get("size", 10),
            "tags": nd.get("tags", []),
            "note": nd.get("note", ""),
        }

    def _edge_data(self, source: str, target: str) -> dict:
        ed = self.G.edges[source, target]
        return {
            "source": source,
            "target": target,
            "relation": ed.get("relation", ""),
            "weight": ed.get("weight", 1.0),
        }

    def _ensure_counter(self) -> str:
        self._counter += 1
        nid = f"node{self._counter}"
        while self.G.has_node(nid):
            self._counter += 1
            nid = f"node{self._counter}"
        return nid


# ────── FastAPI приложение ──────

def create_app(manager: WebGraphManager, dev: bool = False) -> FastAPI:
    """Создать FastAPI-приложение с WebSocket endpoint."""

    app = FastAPI(title="Beatrice Web GUI")

    # CORS для Vite dev server
    if dev:
        from fastapi.middleware.cors import CORSMiddleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Статика (production) — монтируем только /assets/
    # SPA catch-all добавляется после /ws, см. конец create_app
    static_dir = Path(__file__).resolve().parent / "frontend" / "dist"
    assets_dir = static_dir / "assets"
    _static_index_path = static_dir / "index.html"  # for SPA catch-all
    _has_static = assets_dir.exists()
    if _has_static:
        from fastapi.staticfiles import StaticFiles
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # ────── WebSocket менеджер ──────

    class ConnectionManager:
        def __init__(self):
            self.active: list[WebSocket] = []

        async def connect(self, ws: WebSocket):
            await ws.accept()
            self.active.append(ws)

        def disconnect(self, ws: WebSocket):
            if ws in self.active:
                self.active.remove(ws)

        async def broadcast(self, event: dict):
            dead = []
            for ws in self.active:
                try:
                    await ws.send_json(event)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.disconnect(ws)

    cm = ConnectionManager()

    # ────── WebSocket endpoint ──────

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await cm.connect(ws)
        try:
            while True:
                raw = await ws.receive_text()
                try:
                    req = json.loads(raw)
                except json.JSONDecodeError:
                    await ws.send_json({
                        "jsonrpc": "2.0",
                        "error": {"code": -32700, "message": "Parse error"},
                        "id": None,
                    })
                    continue

                req_id = req.get("id")
                method = req.get("method", "")
                params = req.get("params", {})

                try:
                    result = await _handle_method(method, params, manager)
                    # Отправляем ответ
                    await ws.send_json({
                        "jsonrpc": "2.0",
                        "result": result,
                        "id": req_id,
                    })

                    # Если это мутирующий метод — отправляем событие всем
                    event = _get_event(method, params, result)
                    if event:
                        await cm.broadcast({
                            "jsonrpc": "2.0",
                            "method": "event",
                            "params": event,
                        })

                except BeatriceError as e:
                    await ws.send_json({
                        "jsonrpc": "2.0",
                        "error": {"code": -32000, "message": str(e)},
                        "id": req_id,
                    })
                except Exception as e:
                    await ws.send_json({
                        "jsonrpc": "2.0",
                        "error": {"code": -32603, "message": f"Internal error: {e}"},
                        "id": req_id,
                    })
        except WebSocketDisconnect:
            cm.disconnect(ws)
        except Exception:
            cm.disconnect(ws)

    # ────── SPA catch-all (после /ws) ──────
    if _has_static and _static_index_path.exists():
        from starlette.responses import FileResponse
        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            return FileResponse(str(_static_index_path))

    return app


# ────── RPC Method handlers ──────

async def _handle_method(method: str, params: dict, mgr: WebGraphManager) -> Any:
    p = params  # shorthand

    # Узлы
    if method == "add_node":
        return mgr.add_node(p["id"], **{k: v for k, v in p.items() if k != "id"})
    if method == "remove_node":
        return mgr.remove_node(p["id"])
    if method == "update_node":
        return mgr.update_node(p["id"], **{k: v for k, v in p.items() if k != "id"})
    if method == "get_node":
        return mgr.get_node(p["id"])
    if method == "list_nodes":
        return mgr.list_nodes()
    if method == "search_nodes":
        return mgr.search_nodes(p["pattern"])
    if method == "move_node":
        return mgr.move_node(p["old_id"], p["new_id"])

    # Связи
    if method == "add_edge":
        return mgr.add_edge(p["source"], p["target"],
                            **{k: v for k, v in p.items() if k not in ("source", "target")})
    if method == "remove_edge":
        return mgr.remove_edge(p["source"], p["target"])
    if method == "update_edge":
        return mgr.update_edge(p["source"], p["target"],
                               **{k: v for k, v in p.items() if k not in ("source", "target")})
    if method == "list_edges":
        return mgr.list_edges()
    if method == "list_edges_for_node":
        return mgr.list_edges_for_node(p["id"])

    # Теги
    if method == "tag_add":
        return mgr.tag_add(p["node_ids"], p["tags"])
    if method == "tag_remove":
        return mgr.tag_remove(p["node_ids"], p["tags"])
    if method == "tag_clear":
        return mgr.tag_clear(p["node_ids"])
    if method == "tag_list":
        return mgr.tag_list(p.get("id"))
    if method == "tag_nodes":
        return mgr.tag_nodes(p["tags"], p.get("mode", "any"))

    # Граф
    if method == "get_graph_state":
        return mgr.get_graph_state()
    if method == "get_graph_stats":
        return mgr.get_graph_stats()
    if method == "get_louvain":
        return mgr.get_louvain()
    if method == "get_neighbors":
        return mgr.get_neighbors(p["id"], p.get("direction", "all"))
    if method == "get_ring":
        return mgr.get_ring(p["id"], p["min_depth"], p["max_depth"],
                            p.get("direction", "omnidirectional"))
    if method == "get_islands":
        return mgr.get_islands()
    if method == "get_roots":
        return mgr.get_roots()
    if method == "get_frontier":
        return mgr.get_frontier()

    # Файл
    if method == "save":
        mgr.save()
        return {"saved": True, "path": mgr.path}
    if method == "reload":
        mgr.reload()
        return {"reloaded": True}
    if method == "get_file_info":
        return {
            "path": mgr.path,
            "dirty": mgr.dirty,
            "nodes": mgr.G.number_of_nodes(),
            "edges": mgr.G.number_of_edges(),
        }

    raise BeatriceError(f"Неизвестный метод: {method}")


def _get_event(method: str, params: dict, result: Any) -> Optional[dict]:
    """Сгенерировать событие для broadcast на основе метода и его результата."""
    p = params
    if method == "add_node":
        return {"type": "node_added", "payload": result}
    if method == "remove_node":
        return {"type": "node_removed", "payload": {"id": p["id"]}}
    if method == "update_node":
        return {"type": "node_updated", "payload": result}
    if method == "move_node":
        return {"type": "node_moved", "payload": {"old_id": p["old_id"], "new_id": p["new_id"]}}

    if method == "add_edge":
        return {"type": "edge_added", "payload": result}
    if method == "remove_edge":
        return {"type": "edge_removed", "payload": {"source": p["source"], "target": p["target"]}}
    if method == "update_edge":
        return {"type": "edge_updated", "payload": result}

    if method in ("tag_add", "tag_remove", "tag_clear"):
        return {"type": "tags_changed", "payload": {
            "node_ids": list(result.keys()),
            "action": method.replace("tag_", ""),
        }}

    if method == "save":
        return {"type": "file_saved", "payload": {"path": result["path"]}}
    if method == "reload":
        return {"type": "graph_updated", "payload": {}}

    return None


# ────── Запуск ──────

def run_server(graph_path: str, host: str = "127.0.0.1",
               port: int = 8576, dev: bool = False) -> None:
    """Запустить FastAPI-сервер."""
    import uvicorn

    manager = WebGraphManager()
    manager.load(graph_path)

    app = create_app(manager, dev=dev)

    log_level = "info"
    print(f"🌐 Beatrice Web GUI: http://{host}:{port}")
    print(f"📁 Граф: {Path(graph_path).resolve()}")
    print(f"📊 Узлов: {manager.G.number_of_nodes()}, Рёбер: {manager.G.number_of_edges()}")
    if dev:
        print(f"🔧 Режим разработки (CORS для localhost:5173)")

    uvicorn.run(app, host=host, port=port, log_level=log_level)


def run_cli():
    """Entry point для beatrice-web."""
    import sys
    if len(sys.argv) < 2:
        print("Usage: beatrice-web <graph.json> [--host HOST] [--port PORT] [--dev]",
              file=sys.stderr)
        sys.exit(1)

    graph_path = sys.argv[1]
    host = "127.0.0.1"
    port = 8576
    dev = False

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--host" and i + 1 < len(sys.argv):
            host = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == "--dev":
            dev = True
            i += 1
        else:
            i += 1

    run_server(graph_path, host=host, port=port, dev=dev)
