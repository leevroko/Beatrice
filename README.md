# Beatrice — CLI для графов знаний

> Построение, анализ и визуализация графов знаний через NetworkX.

**Beatrice** — это обёртка над NetworkX с мощным CLI для транзактных операций над графами знаний. Хранит графы в формате JSON node-link, все команды работают по схеме: `прочитать → NetworkX → изменить → записать`. Никаких серверов, никаких внешних сервисов — только Python и браузер.

---

## Возможности

| Возможность | Команда |
|---|---|
| 🔍 **Поиск узлов** по строке или regex | `beatrice graph search graph.json "query"` |
| 🧭 **Соседи узла** (входящие/исходящие) | `beatrice graph neighbors graph.json node` |
| 👻 **Узлы-сироты** (без связей) | `beatrice graph orphans graph.json` |
| ➕ **Добавить узел** с атрибутами | `beatrice graph add-node graph.json id --label ...` |
| ❌ **Удалить узел** (со всеми связями) | `beatrice graph rm-node graph.json id` |
| 🔗 **Добавить ребро** | `beatrice graph add-edge graph.json src tgt --relation ...` |
| ✂️ **Удалить ребро** | `beatrice graph rm-edge graph.json src tgt` |
| 📊 **Статистика графа** | `beatrice stat graph.json` |
| 🌐 **Визуализация** в standalone HTML | `beatrice graph render graph.json` |

---

## Быстрый старт

### Установка

```bash
pip install networkx
```

Beatrice — это один файл, не требует дополнительной установки пакета.

### Создать первый граф

```python
# save as create_graph.py
import networkx as nx, json
from pathlib import Path

G = nx.DiGraph()
G.add_node("Kafka",         label="Kafka",        type="брокер")
G.add_node("ZooKeeper",     label="ZooKeeper",    type="координатор")
G.add_edge("Kafka", "ZooKeeper", relation="использует")
G.add_node("OrphanNode",    label="Сирота",       type="unknown")

Path("graph.json").write_text(
    json.dumps(nx.node_link_data(G), ensure_ascii=False, indent=2),
    encoding="utf-8")
```

```bash
python3 create_graph.py
```

### Запросить статистику

```bash
python3 beatrice/cli.py stat graph.json
```

```
Узлов:  3
Рёбер:  1
Плотность:  0.1667
Сирот:  1
         OrphanNode
```

### Найти сирот

```bash
python3 beatrice/cli.py graph search graph.json "Orphan"
```

### Добавить узел

```bash
python3 beatrice/cli.py graph add-node graph.json Redis \
  --label Redis --type "БД" --desc "In-memory cache"
```

### Посмотреть соседей

```bash
python3 beatrice/cli.py graph neighbors graph.json Kafka --direction all
```

### Сгенерировать HTML-визуализацию

```bash
python3 beatrice/cli.py graph render graph.json
```

Открой `graph.html` в браузере — интерактивный force-directed граф с zoom/pan/tooltip/легендой.

---

## Полная документация CLI

```
Использование:
  beatrice graph search    <graph.json> <query>   [--regex]
  beatrice graph neighbors <graph.json> <node>    [--direction out|in|all]
  beatrice graph orphans   <graph.json>
  beatrice graph add-node  <graph.json> <id...>   [--label --type --desc --color --size]
  beatrice graph rm-node   <graph.json> <id...>
  beatrice graph add-edge  <graph.json> <src...> <tgt...> [--relation --weight]
  beatrice graph rm-edge   <graph.json> <src...> <tgt...>
  beatrice graph render    <graph.json> [output]  [--theme dark|light]
  beatrice stat            <graph.json>
```

### `graph search`

```bash
beatrice graph search graph.json "kafka"
beatrice graph search graph.json "kaf|Kaf" --regex
beatrice graph search graph.json ""
```

Ищет по `id` и `label` узлов. С `--regex` интерпретирует запрос как регулярное выражение.

### `graph neighbors`

```bash
beatrice graph neighbors graph.json Kafka
beatrice graph neighbors graph.json Kafka --direction out
beatrice graph neighbors graph.json Kafka --direction in
```

- `out` — на кого указывает данный узел
- `in` — кто указывает на данный узел
- `all` (по умолчанию) — оба направления

### `graph orphans`

```bash
beatrice graph orphans graph.json
beatrice graph orph graph.json     # алиас
```

Показывает узлы без единой связи (степень 0). Если сирот нет — сообщает об этом.

### `graph add-node`

```bash
beatrice graph add-node graph.json Kafka --label Kafka --type брокер --desc "Event streaming"
beatrice graph add-node graph.json A B C    # добавить три узла без атрибутов
```

Параметры: `--label`, `--type`, `--desc`, `--color` (hex), `--size` (число).

Если узел уже существует — предупреждение, дубликат не создаётся.

### `graph rm-node`

```bash
beatrice graph rm-node graph.json OrphanNode
beatrice graph rm-node graph.json node1 node2 node3    # несколько за раз
```

Удаляет узел **и все его связи** (входящие и исходящие).

### `graph add-edge`

```bash
beatrice graph add-edge graph.json Kafka ZooKeeper --relation использует
beatrice graph add-edge graph.json A B C D --relation test  # A→B и C→D
```

Если ребро уже существует — предупреждение, дубликат не создаётся.
Если источник или цель не найдены — ошибка, ребро не добавляется.

### `graph rm-edge`

```bash
beatrice graph rm-edge graph.json Kafka ZooKeeper
beatrice graph rm-edge graph.json A B C D    # удалить A→B и C→D
```

### `graph render`

```bash
beatrice graph render graph.json                   # → graph.html (dark)
beatrice graph render graph.json --theme light      # → graph.html (light)
beatrice graph render graph.json output.html        # кастомное имя
```

Генерирует standalone HTML-файл с D3.js force-directed графом:

- 🔄 Force-directed layout
- 🔍 Zoom + Pan
- 🖱️ Drag узлов (двойной клик — отпустить)
- 💬 Tooltip по клику (id, описание, тип, флаг сироты)
- 👻 Кнопка «Сироты» — скрыть/показать
- ↔ Кнопка «Направления» — стрелки
- 🎨 Легенда по типам узлов
- 📐 Edge labels

### `stat`

```bash
beatrice stat graph.json
```

Выводит: количество узлов, рёбер, плотность, сирот, Louvain-сообщества, PageRank топ-5.

---

## Формат данных

Графы хранятся в JSON node-link — формате, который понимает NetworkX из коробки:

```json
{
  "directed": true,
  "multigraph": false,
  "nodes": [
    {"id": "kafka", "label": "Kafka", "type": "брокер", "desc": "event streaming"},
    {"id": "zookeeper", "label": "ZooKeeper", "type": "координатор", "desc": "cluster mgmt"}
  ],
  "edges": [
    {"source": "kafka", "target": "zookeeper", "relation": "использует", "weight": 1.0}
  ]
}
```

Атрибуты узлов и рёбер — произвольные ключ-значения.

---

## Транзактность

Все модифицирующие операции (`add-node`, `rm-node`, `add-edge`, `rm-edge`) работают атомарно:

1. Читается JSON-файл → NetworkX граф
2. Выполняется операция в памяти
3. Если операция успешна — граф записывается обратно в JSON

Если файл не найден, невалиден, или операция провалилась — диск **не трогается**, исходный файл остаётся нетронутым.

---

## Примеры из демо

В директории лежит готовый граф `graph.json` с демонстрационными данными:

```bash
# Запустить полное демо
python3 demo.py

# Или поработать с CLI
python3 beatrice/cli.py stat graph.json

python3 beatrice/cli.py graph search graph.json "kafka"

python3 beatrice/cli.py graph neighbors graph.json Kafka --direction all

python3 beatrice/cli.py graph render graph.json --theme dark
```

Также сгенерированы форматы для других инструментов:
- `demo_kafka_graph.graphml` — для Gephi, yEd
- `demo_kafka_graph.gexf` — для Gephi native
- `demo_kafka_graph.canvas` — для Obsidian Canvas
- `demo_kafka_graph.json` — JSON node-link

---

## Тесты

```bash
python3 -m pytest tests/ -v
```

39 тестов: load/save, search, neighbors, orphans, add/remove node, add/remove edge, render, error handling.

---

## Планы развития

Подробный список планов: [`PLAN.md`](PLAN.md)

Ключевые направления:
- Интеграция с igraph / graph-tool
- Команды `load`, `export`, `merge`, `validate`, `diff`, `info`
- WebGL-визуализация через sigma.js
- Флаг `--json` для машинного вывода
- Пакет на PyPI (`pip install beatrice`)

---

## Принятые решения

Подробный документ: [`ADR-graph-knowledge-architecture.md`](ADR-graph-knowledge-architecture.md)

| Решение | Выбор |
|---------|-------|
| Движок | **NetworkX** — собственная обёртка поверх него |
| Визуализация (сейчас) | **D3.js v7** (SVG force-directed, standalone HTML) |
| Визуализация (план) | **sigma.js** (WebGL, для графов > 1000 узлов, отложено) |
| Формат хранения | JSON node-link |
| Obsidian | через Web Browser plugin + .canvas |
| Отложено | MCP-сервер, CLI `build`/`serve`, экспорт в Obsidian vault |

---

## Лицензия

MIT
