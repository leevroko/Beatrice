# ADR: Архитектура системы построения и визуализации графов знаний

**Проект:** Beatrice — обёртка над NetworkX для графов знаний
**Дата:** 2026-07-06
**Статус:** Принято

---

## Содержание

1. [Бизнес-контекст и цели](#1-бизнес-контекст-и-цели)
2. [Ключевые требования](#2-ключевые-требования)
3. [Движок графов — NetworkX](#3-движок-графов--networkx)
4. [Визуализация — sigma.js через ipysigma](#4-визуализация--sigmajs-через-ipysigma)
5. [Интеграция с Obsidian](#5-интеграция-с-obsidian)
6. [Вспомогательные инструменты](#6-вспомогательные-инструменты)
7. [Архитектура Beatrice](#7-архитектура-beatrice)
8. [Roadmap](#8-roadmap)
9. [Приложение — таблица сравнения библиотек](#9-приложение--таблица-сравнения-библиотек)
10. [Приложение — обзор всех рассмотренных библиотек](#10-приложение--обзор-всех-рассмотренных-библиотек)

---

## 1. Бизнес-контекст и цели

### 1.1 Задача

Построение графа знаний по произвольной теме, где:
- **узлы** — подтемы / концепты / сущности
- **рёбра** — связи между ними (иерархические, ассоциативные, причинно-следственные)

### 1.2 Ключевые возможности решения

| Возможность | Описание |
|-------------|----------|
| Построение графа | Программное добавление узлов и рёбер с атрибутами |
| Поиск сирот | Обнаружение узлов без связей |
| Декларативное объявление | YAML/JSON-схема или Python-код для описания графа |
| Визуализация | Интерактивный force-directed граф, standalone web |
| Заметки к узлам | Произвольные атрибуты, Markdown, source-ссылки |
| Анализ | PageRank, centrality, community detection, shortest paths |
| Экспорт | HTML, Obsidian Canvas, GraphML, GEXF |
| Масштабируемость | 1000–10000+ узлов |

### 1.3 Принятые решения

| Решение | Выбор |
|---------|-------|
| Движок | **NetworkX** — собственная обёртка поверх него |
| Визуализация (сейчас) | **D3.js v7** (SVG force-directed, standalone HTML) |
| Визуализация (план) | **sigma.js** (WebGL, для графов > 1000 узлов, отложено) |
| Standalone web | HTML-файл с D3.js/sigma.js, открывается в браузере |
| Obsidian | через Web Browser plugin + .canvas |
| Анализ | NetworkX (500+ встроенных алгоритмов) |
| Среда разработки | Python ≥ 3.11 |

---

## 2. Ключевые требования

### 2.1 Функциональные требования

1. **FR-1. Построение графа.** Пользователь должен иметь возможность программно создавать узлы и рёбра с произвольными атрибутами.
2. **FR-2. Поиск сирот.** Библиотека должна уметь находить узлы без входящих/исходящих связей (`degree == 0`).
3. **FR-3. Декларативное описание.** Поддержка JSON/YAML для импорта графов и описания схемы.
4. **FR-4. Визуализация.** Интерактивный force-directed граф, открываемый в браузере — zoom, pan, drag, клик по узлам.
5. **FR-5. Заметки к узлам.** Каждый узел может содержать произвольные свойства (описание, color, size, ссылки).
6. **FR-6. Анализ.** PageRank, centrality (degree, betweenness, eigenvector), community detection (Louvain), shortest paths.
7. **FR-7. Экспорт.** HTML (standalone), Obsidian Canvas (`.canvas`), GraphML, GEXF, JSON node-link.
8. **FR-8. Масштабирование.** Уверенная работа до 10 000 узлов.

### 2.2 Нефункциональные требования

1. **NFR-1. Производительность.** Визуализация через WebGL (не canvas/DOM) для 10K узлов.
2. **NFR-2. Zero сервер.** Всё работает локально, без облачных сервисов.
3. **NFR-3. Минимум зависимостей.** Ядро — только NetworkX + стандартная библиотека.
4. **NFR-4. Расширяемость.** Обёртка не скрывает NetworkX, а дополняет — пользователь может обратиться к `G` напрямую.

---

## 3. Движок графов — NetworkX

### 3.1 Почему NetworkX

| Критерий | NetworkX | igraph | graph-tool |
|----------|----------|--------|------------|
| Простота установки | ✅ `pip install` | ✅ `pip install` | ❌ conda/apt + C++ компиляция |
| Количество алгоритмов | 500+ | ~200 | ~150 |
| Документация | ✅ отличная | ✅ хорошая | ⚠️ средняя |
| Производительность | ⚠️ базовая | ✅ ×100 быстрее | ✅ ×1000 быстрее |
| node attributes | ✅ любые dict | ⚠️ через properties | ⚠️ через PropertyMap |
| Сообщество | 18K+ ★ | 2K+ ★ | 1.5K+ ★ |

**Вывод:** NetworkX — правильный выбор для обёртки. igraph и graph-tool быстрее, но менее гибки для атрибутов и сложнее в установке.

### 3.2 Сравнение производительности (PageRank на 1M узлов)

| Библиотека | Время | Память | Сложность установки |
|------------|-------|--------|-------------------|
| NetworkX | ~180 с | 4.2 GB | `pip install` |
| igraph | ~6 с | 1.1 GB | `pip install` |
| graph-tool | ~2 с | 0.8 GB | `conda install -c conda-forge` |

Источник: [kindatechnical.com](https://kindatechnical.com/graph-theory-applications/networkx-vs-igraph-vs-graph-tool-comparison.html)

Для графов до 100K узлов NetworkX достаточен.

### 3.3 Типовые операции

```python
from networkx import DiGraph, pagerank
from networkx.algorithms.community import louvain_communities
from networkx.algorithms.centrality import degree_centrality

G = DiGraph()

# Добавление с атрибутами
G.add_node("Kafka", type="брокер", description="распределённый event streaming")
G.add_edge("Kafka", "ZooKeeper", relation="использует")

# Поиск сирот
orphans = [n for n, d in G.degree() if d == 0]

# Анализ
ranks = pagerank(G)
centrality = degree_centrality(G)
communities = louvain_communities(G.to_undirected())

# Экспорт
from networkx import write_graphml, write_gexf
write_graphml(G, "graph.graphml")
write_gexf(G, "graph.gexf")
```

---

## 4. Визуализация — D3.js (текущее решение), sigma.js/WebGL (запланировано)

### 4.1 Текущее решение: D3.js v7 (force-directed SVG)

Сейчас визуализация реализована через чистый **D3.js v7** — встроенный HTML-шаблон генерирует force-directed граф с полным набором интерактивных возможностей.

**Почему D3.js, а не WebGL-решения:**
- D3.js не требует установки дополнительных Python-пакетов (кроме самого NetworkX)
- Генерируется самодостаточный HTML (9 KB) с одним CDN-запросом `d3.v7.min.js`
- SVG-рендеринг даёт максимальную гибкость кастомизации (CSS-стили, DOM-события)
- Для графов до 500–1000 узлов производительности D3.js достаточно
- Код шаблона полностью подконтролен — нет чёрного ящика

**Возможности текущего D3.js-шаблона:**
- 🔄 Force-directed layout (physical simulation)
- 🔍 Zoom + Pan (d3.zoom)
- 🖱️ Drag узлов (двойной клик — отпустить)
- 💬 Tooltip по клику: название, описание, тип, флаг сироты
- 👻 Кнопка «Сироты» — скрыть/показать узлы без связей
- ↔ Кнопка «Направления» — стрелки на рёбрах
- ⟲ Кнопка «Сбросить» — сброс zoom/pan
- 🎨 Легенда с раскраской по типу узлов
- 📐 Edge labels — текст на рёбрах
- 🚨 Сироты подсвечены красным бордером

### 4.2 Планируемый переход: sigma.js (WebGL)

**Когда переходить:** когда граф знаний превысит ~1000 узлов или станет заметно тормозить в браузере.

**Цель:** заменить SVG-рендеринг D3.js на WebGL-рендеринг sigma.js для графов 1K–100K узлов.

**Как будет реализовано:**
- Написать второй HTML-шаблон, использующий sigma.js напрямую (без ipysigma)
- `export_html()` будет принимать параметр `engine="d3" | "sigma"`
- При `engine="sigma"` генерировать sigma.js-шаблон вместо D3.js
- NetworkX-логика, анализ, экспорт — без изменений

**Разница D3.js vs sigma.js (WebGL):**

| Характеристика | D3.js (сейчас) | sigma.js (план) |
|----------------|---------------|-----------------|
| Движок | SVG / DOM | **WebGL** (GPU) |
| 100 узлов | ✅ отлично | ✅ отлично |
| 1 000 узлов | ⚠️ заметно тормозит | ✅ плавно, 60 FPS |
| 10 000 узлов | ❌ браузер зависает | ✅ плавно |
| Кастомизация | ✅ CSS/HTML — полный контроль | ⚠️ сложнее, через code reducers |
| Размер HTML | ~9 KB | ~12 KB |
| Зависимости | D3.js (CDN) | sigma.js + graphology (CDN) |

**Почему sigma.js, а не ipysigma:**
- Прямой sigma.js не требует Python-зависимостей (ipysigma тащит Jupyter widgets)
- Полный контроль над шаблоном
- ipysigma генерирует Jupyter-виджет, а не standalone HTML (проверено на практике — не работало)

### 4.3 Сравнение визуализационных библиотек (справочно)

| Библиотека | Движок | Standalone | 10K узл. | Python API | Статус |
|------------|--------|-----------|---------|------------|--------|
| **D3.js (сейчас)** ⭐ | SVG | ✅ | ❌ | ✅ (шаблон) | **текущее решение** |
| **sigma.js (план)** | WebGL | ✅ | ✅ | ✅ (шаблон) | **запланировано** |
| ipysigma | sigma.js WebGL | ⚠️ widget | ✅ | ✅ | ❌ rejected |
| gravis | D3/vis.js/Three.js | ✅ | ⚠️ | ✅ | ❌ не нужно |
| d3graph | D3.js | ✅ | ❌ | ✅ | ❌ не нужно |
| kgviz | Three.js 3D | ✅ | ✅ | ✅ | ❌ не нужно |

---

## 5. Интеграция с Obsidian

### 5.1 Варианты

| Вариант | Плюсы | Минусы |
|---------|-------|--------|
| **HTML через Custom Frames / Web Browser** | Полный контроль, WebGL, интерактив | Требует плагин, грузит внешний URL или локальный файл |
| **Obsidian Canvas (.canvas)** | Нативный, скилл `create-canvas` | Только 2D, нет WebGL, layout надо считать самому |
| **Obsidian Graph View** | Встроенный | Только backlinks заметок, не кастомизируется |

### 5.2 Принятое решение: HTML + Web Browser (основной), .canvas (дополнительно)

**Основной канал:** `export_html("knowledge_graph.html")` — файл открывается в Obsidian через [Custom Frames](https://github.com/Ellpeck/ObsidianCustomFrames) или [Web Browser](https://github.com/Trikzon/obsidian-web-browser) плагин.

```yaml
# Custom Frames конфиг
- id: knowledge-graph
  url: file:///Users/user/vault/knowledge_graph.html
  display: iframe
  width: 100
  height: 100
```

**Дополнительный канал:** `export_obsidian_canvas("graph.canvas")` — для встраивания в заметки через `![[graph.canvas]]`.

### 5.3 Obsidian Canvas формат

```json
{
  "nodes": [
    {
      "id": "n1",
      "x": 100, "y": 200,
      "width": 250, "height": 80,
      "type": "file",
      "file": "Kafka.md"
    },
    {
      "id": "n2",
      "x": 400, "y": 200,
      "width": 250, "height": 80,
      "type": "file",
      "file": "ZooKeeper.md"
    }
  ],
  "edges": [
    {
      "id": "e1",
      "fromNode": "n1", "fromSide": "right",
      "toNode": "n2", "toSide": "left",
      "label": "использует"
    }
  ]
}
```

**Спецификация:** [JSON Canvas 1.0](https://jsoncanvas.org/)

---

## 6. Вспомогательные инструменты

### 6.1 YAML-схема для декларативного описания

```yaml
# graph_schema.yaml
name: "Технологический стек"
nodes:
  - id: "kafka"
    label: "Kafka"
    type: "брокер"
    description: "Распределённый event streaming"
    color: "#FF6B6B"
    size: 20
  - id: "zookeeper"
    label: "ZooKeeper"
    type: "координатор"
    description: "Управление кластером"
    color: "#4ECDC4"
    size: 15

edges:
  - source: "kafka"
    target: "zookeeper"
    relation: "использует"
    weight: 0.9
```

### 6.2 Работа с сиротами

```python
# Явный метод
orphans = kg.find_orphans()

# Через path (связность)
connected_subgraphs = list(nx.connected_components(kg.G.to_undirected()))

# Только узлы без заметок (если заметки помечены атрибутом)
orphans_without_notes = [
    n for n, d in kg.G.nodes(data=True)
    if d.get('file') is None
]
```

### 6.3 Анализ

```python
# PageRank — важность узлов
ranks = nx.pagerank(kg.G)
for node, rank in sorted(ranks.items(), key=lambda x: -x[1])[:10]:
    print(f"{node}: {rank:.3f}")

# Louvain — кластеризация
communities = nx.community.louvain_communities(kg.G.to_undirected())
for i, comm in enumerate(communities):
    print(f"Community {i}: {comm}")

# Centrality
bc = nx.betweenness_centrality(kg.G)
dc = nx.degree_centrality(kg.G)
ec = nx.eigenvector_centrality(kg.G, max_iter=1000)
```

---

## 7. Архитектура Beatrice

### 7.1 Структура пакета

```
beatrice/
├── __init__.py               # Экспорт основного класса
├── core.py                   # KnowledgeGraph — основная обёртка
├── schema.py                 # YAML/JSON-загрузка схем
├── analysis.py               # PageRank, centrality, communities
├── export/
│   ├── __init__.py
│   ├── html.py               # Экспорт в HTML (sigma.js)
│   ├── obsidian_canvas.py    # Экспорт в .canvas
│   └── graphml.py            # Экспорт в GraphML/GEXF
├── viz/
│   ├── __init__.py
│   └── sigma.py              # ipysigma / sigma.js настройки
└── cli.py                    # Опциональный CLI
```

### 7.2 Основной класс

```python
import networkx as nx
from pathlib import Path
from typing import Any, Optional

class KnowledgeGraph:
    """Обёртка над NetworkX для графов знаний."""

    def __init__(self, directed: bool = True):
        self.G = nx.DiGraph() if directed else nx.Graph()

    # ---- Построение ----

    def add_node(self, id: str, label: str = "",
                 type: str = "", description: str = "",
                 color: str = "", size: float = 10,
                 **kwargs) -> None:
        self.G.add_node(id,
            label=label or id,
            type=type,
            description=description,
            color=color or None,
            size=size,
            **kwargs)

    def add_edge(self, source: str, target: str,
                 relation: str = "", weight: float = 1.0,
                 **kwargs) -> None:
        self.G.add_edge(source, target,
            relation=relation,
            weight=weight,
            **kwargs)

    def load_yaml(self, path: str) -> None:
        """Загрузить схему из YAML-файла."""
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        for node in data.get("nodes", []):
            self.add_node(**node)
        for edge in data.get("edges", []):
            self.add_edge(**edge)

    def load_json(self, path: str) -> None:
        """Загрузить граф из JSON."""
        import json
        with open(path) as f:
            data = json.load(f)
        for node in data.get("nodes", []):
            self.add_node(**node)
        for edge in data.get("edges", []):
            self.add_edge(**edge)

    # ---- Анализ ----

    def find_orphans(self) -> list:
        """Узлы без связей (степень 0)."""
        return [n for n, d in self.G.degree() if d == 0]

    def pagerank(self, **kwargs) -> dict:
        return nx.pagerank(self.G, **kwargs)

    def communities(self, **kwargs) -> list:
        return list(nx.community.louvain_communities(
            self.G.to_undirected(), **kwargs))

    def centrality(self, method: str = "degree") -> dict:
        methods = {
            "degree": nx.degree_centrality,
            "betweenness": nx.betweenness_centrality,
            "eigenvector": lambda g:
                nx.eigenvector_centrality(g, max_iter=1000),
            "closeness": nx.closeness_centrality,
        }
        return methods[method](self.G)

    # ---- Экспорт ----

    def export_html(self, path: str = "knowledge_graph.html",
                    **kwargs) -> str:
        """Экспорт в standalone HTML через sigma.js."""
        from beatrice.export.html import export_to_html
        return export_to_html(self.G, path, **kwargs)

    def export_obsidian_canvas(self, path: str = "graph.canvas",
                                note_dir: Optional[str] = None) -> str:
        """Экспорт в Obsidian Canvas (.canvas)."""
        from beatrice.export.obsidian_canvas import export_canvas
        return export_canvas(self.G, path, note_dir)

    # ---- Свойства ----

    @property
    def node_count(self) -> int:
        return self.G.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self.G.number_of_edges()

    @property
    def density(self) -> float:
        return nx.density(self.G)
```

### 7.3 Пример использования

```python
from beatrice import KnowledgeGraph

kg = KnowledgeGraph()

# Декларативное построение
kg.add_node("Kafka",      label="Kafka",      type="брокер",
            description="распределённый event streaming")
kg.add_node("ZooKeeper",  label="ZooKeeper",  type="координатор",
            description="управление кластером")
kg.add_node("SchemaRegistry", label="Schema Registry", type="сервис",
            description="управление схемами данных")
kg.add_node("KafkaConnect",   label="Kafka Connect",   type="сервис",
            description="интеграция с внешними системами")
kg.add_node("KafkaStreams",   label="Kafka Streams",   type="библиотека",
            description="stream processing")

kg.add_edge("Kafka", "ZooKeeper",     relation="использует")
kg.add_edge("Kafka", "SchemaRegistry", relation="использует")
kg.add_edge("KafkaConnect", "Kafka",  relation="записывает в")
kg.add_edge("KafkaStreams", "Kafka",  relation="читает из")

# Или загрузка из YAML
# kg.load_yaml("tech_stack.yaml")

# Анализ
orphans = kg.find_orphans()
ranks = kg.pagerank()
communities = kg.communities()

# Экспорт
kg.export_html("kafka_graph.html", theme="dark")
kg.export_obsidian_canvas("kafka_graph.canvas")
```

---

## 8. Roadmap — актуальный статус

**Фокус разработки:** построение графа, базовый анализ, декларативные схемы, HTML-визуализация.

**Отложено на неопределённый срок:**
- Betweenness / eigenvector centrality
- Closeness centrality
- Экспорт в Obsidian vault (`.md` файлы)
- MCP-сервер
- CLI (`beatrice build`, `beatrice serve`)
- 3D-визуализация (kgviz)

---

### Фаза 1 — MVP (core) ✅
- [x] `KnowledgeGraph` класс: add_node, add_edge, find_orphans ✅
- [x] YAML/JSON загрузка схем ✅
- [x] Экспорт GraphML/GEXF/JSON ✅
- [x] Базовый анализ: degree centrality, PageRank, Louvain, shortest paths ✅

### Фаза 2 — Визуализация ✅
- [x] `export_html()` через D3.js force-directed граф ✅
- [x] Кастомизация: цвет, размер, описание, тип, tooltip ✅
- [x] Легенда, кнопки управления (сироты, направления, сброс) ✅
- [x] `.show()` — HTML открывается в браузере из файла ✅

### Фаза 3 — Расширенный анализ *(отложено)*
- [ ] Betweenness / eigenvector centrality
- [ ] Closeness centrality

### Фаза 4 — Obsidian *(отложено)*
- [ ] `export_obsidian_vault()` — генерация `.md` файлов для Obsidian
- [ ] YAML frontmatter с id, type, связями

### Фаза 5 — Дополнительно *(отложено)*
- [ ] Кастомный WebGL-шаблон (sigma.js вместо D3.js) — для графов > 1000 узлов
- [ ] 3D-визуализация (kgviz)
- [ ] CLI
- [ ] MCP-сервер

---

## 9. Приложение — таблица сравнения библиотек

### 9.1 Движки графов

| Библиотека | Установка | Произв-сть | Алгоритмы | Атрибуты | Когда брать |
|------------|-----------|-----------|-----------|----------|------------|
| **NetworkX** ⭐ | `pip install` | ×1 | 500+ | dict | **Основа обёртки** |
| igraph | `pip install` | ×100 | ~200 | properties | Если нужно быстрее |
| graph-tool | conda/apt | ×1000 | ~150 | PropertyMap | Если графы > 1M узлов |
| rustworkx | `pip install` | ×100–500 | ~50 | dict | Если Rust нравится больше |

### 9.2 Специализированные KG-библиотеки

| Библиотека | Звёзды | Назначение |
|------------|--------|------------|
| **semantica** | 1221 ★ | Полноценная платформа: ContextGraph, W3C PROV-O, Rete, MCP |
| **myKG** | ~5K/нед | Документы → граф знаний (JSONL + Neo4j + Obsidian vault) |
| **kglab** | 680 ★ | Абстракция над NetworkX + RDFlib + PyVis |
| **seocho** | новая | Ontology-driven: schema → LLM → SHACL → Cypher |
| **graphforge** | ~80/нед | Лёгкая Entity/Relationship → NetworkX → enrichment |

### 9.3 Визуализация

| Библиотека | Движок | Standalone | 10K узл. | Python API | Когда |
|------------|--------|-----------|---------|------------|-------|
| **ipysigma** ⭐ | sigma.js WebGL | ✅ | ✅ | ✅ | **Основной выбор** |
| gravis | D3/vis.js/Three.js | ✅ | ⚠️ | ✅ | Простота, 3 режима |
| d3graph | D3.js | ✅ | ❌ | ✅ | Маленькие графы |
| kgviz | Three.js 3D | ✅ | ✅ | ✅ | 3D эстетика |
| anywidget-graph | sigma.js | ✅ | ✅ | ✅ | Jupyter/Marimo |
| yFiles Streamlit | proprietary | ❌ | ✅ | ✅ | Streamlit |
| streamlit-cytoscape | Cytoscape.js canvas | ❌ | ~1K | ✅ | Streamlit |
| nx-vis-visualizer | vis.js | ✅ | ❌ | ✅ | vis.js фанаты |

---

## 10. Приложение — обзор всех рассмотренных библиотек

### NetworkX
- **GitHub:** https://github.com/networkx/networkx
- **Docs:** https://networkx.org
- **Звёзды:** 18K+
- **Лицензия:** BSD-3
- **Суть:** Фундаментальная библиотека для работы с графами на Python.
- **Для чего:** Создание, манипуляция, анализ графов. 500+ алгоритмов.

### igraph
- **GitHub:** https://github.com/igraph/igraph
- **Docs:** https://igraph.org/python
- **Звёзды:** 2K+
- **Лицензия:** GPL-2
- **Суть:** C-ядро с Python/R/C биндингами. ×10–100 быстрее NetworkX.
- **Для чего:** Production-нагрузки, 100K–10M узлов.

### graph-tool
- **GitHub:** https://git.skewed.de/count0/graph-tool
- **Docs:** https://graph-tool.skewed.de
- **Лицензия:** GPL-3
- **Суть:** C++ с OpenMP. ×100–1000 быстрее NetworkX.
- **Для чего:** Research, 10M+ узлов, stochastic block models.

### rustworkx
- **GitHub:** https://github.com/Qiskit/rustworkx
- **Звёзды:** ~800
- **Лицензия:** Apache-2.0
- **Суть:** Rust через PyO3.
- **Для чего:** Когда скорости igraph мало.

### semantica
- **GitHub:** https://github.com/semantica-agi/semantica
- **Звёзды:** 1221 ★
- **Лицензия:** MIT
- **Суть:** Полноценная платформа графов знаний: ContextGraph, OWL/SHACL, W3C PROV-O, Rete/Datalog/SPARQL reasoning, конфликт-детекция, MCP сервер, React Explorer.
- **Для чего:** Enterprise-решения, compliance, audit trails.

### myKG
- **GitHub:** https://github.com/SenolIsci/mykg
- **Загрузки/нед:** ~5000
- **Лицензия:** MIT
- **Суть:** CLI: документы → граф знаний (JSONL + Neo4j + Obsidian vault + RDF/OWL + D3.js HTML).
- **Для чего:** Быстро получить граф из папки с документами.

### kglab
- **GitHub:** https://github.com/DerwenAI/kglab
- **Звёзды:** 680 ★
- **Лицензия:** MIT
- **Суть:** Абстракция над NetworkX + RDFlib + PyVis + RAPIDS.
- **Для чего:** Если нужно работать с RDF-данными как с графом.

### seocho
- **GitHub:** https://github.com/tteon/seocho
- **Лицензия:** MIT
- **Суть:** Ontology-driven: определил schema → LLM извлёк → SHACL проверил → Cypher в Neo4j.
- **Для чего:** Если онтология — главный приоритет.

### ipysigma
- **GitHub:** https://github.com/medialab/ipysigma
- **Docs:** https://github.com/Yomguithereal/ipysigma
- **Лицензия:** MIT
- **Суть:** Jupyter-виджет на sigma.js (WebGL). 20+ визуальных переменных, ForceAtlas2, Louvain, SigmaGrid.
- **Для чего:** **Визуализация 10K+ узлов** с Python API.

### gravis
- **GitHub:** https://github.com/robert-haas/gravis
- **Docs:** https://robert-haas.github.io/gravis-docs
- **Лицензия:** Apache-2.0
- **Суть:** Три бэкенда (D3.js, vis.js, three.js/3d-force-graph) в одном Python API.
- **Для чего:** Универсальная визуализация с 3 опциями рендеринга.

### d3graph
- **GitHub:** https://github.com/erdogant/d3graph
- **Звёзды:** 203 ★
- **Загрузки/мес:** ~7400
- **Лицензия:** BSD-3
- **Суть:** D3.js force-directed из Python. Просто: adjacency matrix → интерактивный HTML.
- **Для чего:** Малые графы (< 1000 узлов).

### kgviz
- **GitHub:** https://github.com/dataprofessor/kgviz
- **Загрузки/мес:** ~450
- **Лицензия:** MIT
- **Суть:** 3D WebGL (React/Three.js) для Jupyter, Streamlit, Gradio, Dash, HTML.
- **Для чего:** 3D-визуализация, embedding maps (PCA/t-SNE/UMAP/SOM).

### anywidget-graph
- **GitHub:** https://github.com/GrafeoDB/anywidget-graph
- **Звёзды:** 2 ★
- **Лицензия:** Apache-2.0
- **Суть:** Sigma.js widget на anywidget. Universal: Jupyter, Marimo, VS Code, Colab.
- **Для чего:** Ноутбуки, Grafeo/Neo4j/NetworkX интеграция.

### yFiles Graphs for Streamlit
- **GitHub:** https://github.com/yWorks/yfiles-graphs-for-streamlit
- **Звёзды:** 21 ★
- **Лицензия:** проприетарная (бесплатно для Streamlit)
- **Суть:** yFiles layouts (organic, hierarchic, tree, orthogonal, circular, radial) для Streamlit.
- **Для чего:** Streamlit-дашборды с продвинутыми layout'ами.

### streamlit-cytoscape
- **GitHub:** форк st-link-analysis
- **Загрузки/мес:** ~820
- **Лицензия:** MIT
- **Суть:** Cytoscape.js в Streamlit.
- **Для чего:** Streamlit-приложения.

### dash-cytoscape
- **GitHub:** https://github.com/plotly/dash-cytoscape
- **Лицензия:** MIT
- **Суть:** Cytoscape.js в Dash от Plotly.
- **Для чего:** Dash-приложения с графами.

### graphable
- **GitHub:** https://github.com/TheTrueSCU/graphable
- **Лицензия:** MIT
- **Суть:** Type-safe DAG: топсорт, critical path, Mermaid/Graphviz/D2/PlantUML/TikZ.
- **Для чего:** DAG-зависимости, workflow orchestration.

### knowledgecomplex
- **GitHub:** https://github.com/DynamicalSystemsGroup/knowledgecomplex
- **Звёзды:** 6 ★
- **Лицензия:** Apache-2.0
- **Суть:** Типизированные симплициальные комплексы: OWL + SHACL + Betti numbers + Hodge Laplacian.
- **Для чего:** Математическая топология графов.

### PyCodeKG
- **GitHub:** https://github.com/Flux-Frontiers/pycode_kg
- **Звёзды:** 1 ★
- **Лицензия:** Elastic-2.0
- **Суть:** AST Python-кода → граф знаний в SQLite + LanceDB.
- **Для чего:** Анализ архитектуры Python-кода.

### sift-kg
- **PyPI:** https://pypi.org/project/sift-kg
- **Лицензия:** unknown
- **Суть:** Пайплайн: extract → build → resolve → narrate → view.
- **Для чего:** Документы → граф с interactive HTML и confidence scoring.

---

*Решение принято: 2026-07-06*
*Автор: Beatrice (AI-агент)*
*Версия: 1.0*
