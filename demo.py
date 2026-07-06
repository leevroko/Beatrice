#!/usr/bin/env python3
"""
Beatrice — минимальный демо-пример графа знаний.

Возможности:
  1. Построение графа (узлы + рёбра с атрибутами)
  2. Поиск сирот
  3. Анализ: PageRank, Louvain, centrality
  4. Визуализация: standalone HTML + Obsidian Canvas
"""

import networkx as nx
from networkx.algorithms.community import louvain_communities
from pathlib import Path
import json

OUT = Path(__file__).parent


# ═══════════════════════════════════════════════════════════
# 1. Строим граф
# ═══════════════════════════════════════════════════════════

G = nx.DiGraph()

# Узлы с атрибутами
G.add_node("Kafka",         label="Kafka",          type="брокер",
           desc="Распределённый event streaming",    color="#FF6B6B", size=25)
G.add_node("ZooKeeper",     label="ZooKeeper",      type="координатор",
           desc="Управление кластером",              color="#4ECDC4", size=18)
G.add_node("SchemaRegistry", label="Schema Registry", type="сервис",
           desc="Управление схемами данных",          color="#45B7D1", size=15)
G.add_node("KafkaConnect",  label="Kafka Connect",   type="сервис",
           desc="Интеграция с внешними системами",    color="#96CEB4", size=15)
G.add_node("KafkaStreams",  label="Kafka Streams",   type="библиотека",
           desc="Stream processing",                 color="#FFEAA7", size=15)
G.add_node("KRaft",         label="KRaft",           type="протокол",
           desc="Raft-замена ZooKeeper",              color="#DDA0DD", size=12)
G.add_node("Topic",         label="Topic",           type="структура",
           desc="Очередь сообщений",                 color="#98D8C8", size=20)
G.add_node("ConsumerGroup", label="Consumer Group",  type="консьюмер",
           desc="Группа консьюмеров",                color="#F7DC6F", size=16)

# Ребра
G.add_edge("Kafka", "ZooKeeper",        relation="использует")
G.add_edge("Kafka", "SchemaRegistry",   relation="интегрируется с")
G.add_edge("KafkaConnect", "Kafka",     relation="записывает в")
G.add_edge("KafkaStreams", "Kafka",     relation="читает из")
G.add_edge("Kafka", "Topic",           relation="содержит")
G.add_edge("Topic", "ConsumerGroup",   relation="читается")
G.add_edge("Kafka", "KRaft",           relation="переходит на")
G.add_edge("KRaft", "ZooKeeper",       relation="заменяет")

# Сирота — узел без связей (для демонстрации)
G.add_node("OrphanNode",   label="Узел-сирота",     type="unknown",
           desc="Не имеет связей",                   color="#999999", size=10)


# ═══════════════════════════════════════════════════════════
# 2. Запросы
# ═══════════════════════════════════════════════════════════

print("═" * 50)
print("📊 Анализ графа знаний Kafka")
print("═" * 50)

# 2.1 Базовая статистика
print(f"\n📈 Статистика:")
print(f"   Узлов:   {G.number_of_nodes()}")
print(f"   Рёбер:   {G.number_of_edges()}")
print(f"   Плотность: {nx.density(G):.4f}")
print(f"   Компонент связности: {nx.number_weakly_connected_components(G)}")

# 2.2 Сироты
orphans = [n for n, d in G.degree() if d == 0]
print(f"\n👻 Сироты (degree == 0):")
for o in orphans:
    print(f"   - {o}: {G.nodes[o].get('desc', '—')}")

# 2.3 PageRank
# Используем pure-Python версию (без scipy), если native не работает
try:
    ranks = nx.pagerank(G)
except ImportError:
    ranks = nx.pagerank(G, nstart={n: 1 for n in G.nodes()}, tol=1e-6)
print(f"\n🔝 PageRank (топ-5):")
for node, rank in sorted(ranks.items(), key=lambda x: -x[1])[:5]:
    print(f"   {node:<20s} {rank:.4f}")

# 2.4 Louvain community
communities = louvain_communities(G.to_undirected(), seed=42)
print(f"\n🔷 Louvain communities ({len(communities)}):")
for i, comm in enumerate(communities):
    print(f"   Community {i}: {', '.join(sorted(comm)[:5])}")

# 2.5 Degree centrality
dc = nx.degree_centrality(G)
print(f"\n🎯 Degree centrality (топ-5):")
for node, val in sorted(dc.items(), key=lambda x: -x[1])[:5]:
    print(f"   {node:<20s} {val:.4f}")

# 2.6 Shortest paths
print(f"\n🛤️  Кратчайший путь Kafka → ConsumerGroup:")
path = nx.shortest_path(G, "Kafka", "ConsumerGroup")
print(f"   {' → '.join(path)}")


# ═══════════════════════════════════════════════════════════
# 3. Экспорт
# ═══════════════════════════════════════════════════════════

colors = {"брокер": "#FF6B6B", "координатор": "#4ECDC4", "сервис": "#45B7D1",
          "библиотека": "#FFEAA7", "протокол": "#DDA0DD", "структура": "#98D8C8",
          "консьюмер": "#F7DC6F", "unknown": "#999999"}

# 3.1 Экспорт в Obsidian Canvas (.canvas)
canvas = {
    "nodes": [],
    "edges": []
}

# Layout вручную (круг)
import math
n_nodes = G.number_of_nodes()
positions = {}
for i, node in enumerate(G.nodes()):
    angle = 2 * math.pi * i / n_nodes
    positions[node] = (400 + 300 * math.cos(angle),
                       300 + 300 * math.sin(angle))

for node, (x, y) in positions.items():
    canvas["nodes"].append({
        "id": node,
        "x": x, "y": y,
        "width": 200, "height": 60,
        "type": "text",
        "text": G.nodes[node].get("label", node),
        "color": G.nodes[node].get("color", "#999999"),
    })

for src, tgt, data in G.edges(data=True):
    canvas["edges"].append({
        "id": f"{src}→{tgt}",
        "fromNode": src, "fromSide": "right",
        "toNode": tgt, "toSide": "left",
        "label": data.get("relation", ""),
    })

canvas_path = OUT / "demo_kafka_graph.canvas"
canvas_path.write_text(json.dumps(canvas, ensure_ascii=False, indent=2))
print(f"\n💾 Obsidian Canvas:  {canvas_path}")

# 3.2 Экспорт в GraphML
graphml_path = OUT / "demo_kafka_graph.graphml"
nx.write_graphml(G, graphml_path)
print(f"💾 GraphML:          {graphml_path}")

# 3.3 Экспорт в GEXF
gexf_path = OUT / "demo_kafka_graph.gexf"
nx.write_gexf(G, gexf_path)
print(f"💾 GEXF:             {gexf_path}")

# 3.4 Экспорт в JSON node-link
json_path = OUT / "demo_kafka_graph.json"
data = nx.node_link_data(G)
with open(json_path, "w") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f"💾 JSON (node-link): {json_path}")

# 3.5 Экспорт в standalone HTML через D3.js force-directed graph
# Простой, надёжный, не требует внешних зависимостей (кроме CDN)
html_path = OUT / "demo_kafka_graph.html"

# Подготовим данные для D3
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
        "source": s,
        "target": t,
        "relation": d.get("relation", ""),
    })

json_nodes = json.dumps(nodes_data, ensure_ascii=False)
json_edges = json.dumps(edges_data, ensure_ascii=False)

# Сообщество для раскраски (опционально) — уже есть в communities
node_to_community = {}
for i, comm in enumerate(communities):
    for n in comm:
        node_to_community[n] = i

_html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Beatrice — Knowledge Graph</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:#1a1a2e; font-family:'Segoe UI', sans-serif; overflow:hidden; color:#eee; }}
  #graph {{ width:100vw; height:100vh; }}
  .controls {{ position:absolute; top:16px; left:16px; z-index:10; display:flex; gap:8px; }}
  .controls button {{
    background:#16213e; color:#eee; border:1px solid #0f3460;
    padding:8px 14px; border-radius:6px; cursor:pointer; font-size:13px;
    transition:background .2s;
  }}
  .controls button:hover {{ background:#0f3460; }}
  .tooltip {{
    position:absolute; padding:12px 16px; background:#16213e; border:1px solid #0f3460;
    border-radius:8px; font-size:13px; pointer-events:none; max-width:300px;
    display:none; z-index:20; line-height:1.5;
  }}
  .tooltip .title {{ font-weight:bold; font-size:15px; color:#e94560; margin-bottom:4px; }}
  .tooltip .sub {{ color:#aaa; font-size:12px; }}
  .legend {{
    position:absolute; bottom:24px; left:24px; z-index:10;
    background:#16213ecc; padding:12px 16px; border-radius:8px;
    font-size:12px; border:1px solid #0f3460;
  }}
  .legend-item {{ display:flex; align-items:center; gap:8px; margin:4px 0; }}
  .legend-dot {{ width:12px; height:12px; border-radius:50%; flex-shrink:0; }}
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

<script>
const nodesData = {json_nodes};
const edgesData = {json_edges};
const orphans = {json.dumps(list(orphans))};
const typeColors = {json.dumps(colors, ensure_ascii=False)};

// === D3.js Force Layout ===
const width = window.innerWidth;
const height = window.innerHeight;

const svg = d3.select("#graph").append("svg")
    .attr("width", width).attr("height", height)
    .call(d3.zoom().scaleExtent([0.1, 10]).on("zoom", (e) => {{
        container.attr("transform", e.transform);
    }}));

const container = svg.append("g");

const tooltip = d3.select("#tooltip");

// Node data
const nodeMap = new Map(nodesData.map(n => [n.id, n]));

// Force simulation
const simulation = d3.forceSimulation(nodesData)
    .force("link", d3.forceLink(edgesData).id(d => d.id).distance(150))
    .force("charge", d3.forceManyBody().strength(-400))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collision", d3.forceCollide().radius(d => d.size + 15));

// Edges
const link = container.append("g").selectAll("line")
    .data(edgesData).join("line")
    .attr("stroke", "#555")
    .attr("stroke-width", 1.5)
    .attr("stroke-opacity", 0.6)
    .attr("marker-end", "url(#arrow)");

// Edge labels
const edgeLabel = container.append("g").selectAll("text")
    .data(edgesData).join("text")
    .text(d => d.relation)
    .attr("font-size", 9)
    .attr("fill", "#888")
    .attr("text-anchor", "middle");

// Nodes (groups)
const node = container.append("g").selectAll("g")
    .data(nodesData).join("g")
    .call(d3.drag()
        .on("start", (e, d) => {{
            if (!e.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x; d.fy = d.y;
        }})
        .on("drag", (e, d) => {{ d.fx = e.x; d.fy = e.y; }})
        .on("end", (e, d) => {{
            if (!e.active) simulation.alphaTarget(0);
            d.fx = null; d.fy = null;
        }}))
    .on("click", (e, d) => showTooltip(e, d))
    .on("dblclick", (e, d) => {{ d.fx = null; d.fy = null; simulation.alpha(0.3).restart(); }});

// Node circles
node.append("circle")
    .attr("r", d => d.size || 10)
    .attr("fill", d => d.color || "#666")
    .attr("stroke", d => d.isOrphan ? "#ff6b6b" : "#fff")
    .attr("stroke-width", d => d.isOrphan ? 3 : 1.5)
    .style("cursor", "pointer");

// Node labels
node.append("text")
    .text(d => d.label)
    .attr("dx", 0)
    .attr("dy", d => -(d.size || 10) - 6)
    .attr("text-anchor", "middle")
    .attr("font-size", 12)
    .attr("fill", "#fff")
    .style("pointer-events", "none");

// Arrows marker
defs = svg.append("defs");
defs.append("marker")
    .attr("id", "arrow")
    .attr("viewBox", "0 -5 10 10")
    .attr("refX", 25)
    .attr("refY", 0)
    .attr("markerWidth", 8)
    .attr("markerHeight", 8)
    .attr("orient", "auto")
    .append("path")
    .attr("d", "M0,-5L10,0L0,5")
    .attr("fill", "#555");

// Simulation tick
simulation.on("tick", () => {{
    link.attr("x1", d => d.source.x).attr("y1", d => d.source.y)
        .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
    edgeLabel.attr("x", d => (d.source.x + d.target.x) / 2)
        .attr("y", d => (d.source.y + d.target.y) / 2 - 6);
    node.attr("transform", d => `translate(${{d.x}},${{d.y}})`);
}});

// === Tooltip ===
function showTooltip(e, d) {{
    tooltip
        .style("display", "block")
        .style("left", (e.pageX + 16) + "px")
        .style("top", (e.pageY - 10) + "px")
        .html(`
            <div class="title">${{d.label}}</div>
            ${{d.desc ? `<div class="sub">${{d.desc}}</div>` : ''}}
            <div class="sub" style="margin-top:4px">Тип: ${{d.type || '—'}}</div>
            ${{d.isOrphan ? '<div class="sub" style="color:#ff6b6b;margin-top:4px">👻 Узел-сирота (нет связей)</div>' : ''}}
        `);
}}

// === Легенда ===
let legendItems = Object.entries({json.dumps(colors, ensure_ascii=False)}).filter(([k]) => k !== "unknown");
d3.select("#legend").html(
    legendItems.map(([type, color]) =>
        `<div class="legend-item"><span class="legend-dot" style="background:${{color}}"></span>${{type}}</div>`
    ).join("")
);

// === Controls ===
function resetZoom() {{
    svg.transition().duration(750).call(
        d3.zoom().transform, d3.zoomIdentity
    );
}}

let showOrphans = true;
function toggleOrphans() {{
    showOrphans = !showOrphans;
    node.style("opacity", d => showOrphans ? 1 : (d.isOrphan ? 0 : 1));
}}

let showDir = true;
function toggleDirection() {{
    showDir = !showDir;
    link.attr("marker-end", showDir ? "url(#arrow)" : null);
}}

// Hide tooltip on click elsewhere
d3.select("body").on("click", (e) => {{
    if (!e.target.closest("g")) tooltip.style("display", "none");
}});

// Resize handler
window.addEventListener("resize", () => {{
    const w = window.innerWidth, h = window.innerHeight;
    svg.attr("width", w).attr("height", h);
    simulation.force("center", d3.forceCenter(w / 2, h / 2));
}});
</script>
</body>
</html>"""

html_path.write_text(_html)
print(f"💾 HTML (D3.js):     {html_path}")

print(f"\n✅ Готово. Все файлы в: {OUT}")
