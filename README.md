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
| 🌳 **Корни** (out>0, in=0) | `beatrice graph roots graph.json` |
| 🚩 **Фронтир** (in>0, out=0) | `beatrice graph frontier graph.json` |
| 🏝️ **Острова** (изолированные кластеры) | `beatrice graph islands graph.json` |
| 🧬 **Сообщества** (Louvain-кластеризация) | `beatrice graph louvain graph.json` |
| 🔵 **Кольца** (узлы на диапазоне глубин) | `beatrice graph ring graph.json node --min 2 --max 4` |
| 🏷️ **Теги** (управление тегами узлов) | `beatrice graph tag add/rm/ls/clear graph.json ...` |
| ➕ **Добавить узел** с атрибутами | `beatrice graph add-node graph.json id --label ...` |
| ✏️ **Редактировать узел** (patch атрибутов) | `beatrice graph edit-node graph.json id --label ...` |
| ❌ **Удалить узел** (со всеми связями) | `beatrice graph rm-node graph.json id` |
| 🔗 **Добавить ребро** | `beatrice graph add-edge graph.json src tgt --relation ...` |
| ✂️ **Удалить ребро** | `beatrice graph rm-edge graph.json src tgt` |
| 🔀 **Пересечение графов** (G1 ∩ G2) | `beatrice graph intersect g1.json g2.json` |
| 🔀 **Объединение графов** (G1 ∪ G2) | `beatrice graph union g1.json g2.json` |
| 🔀 **Разность графов** (G1 ∖ G2) | `beatrice graph diff g1.json g2.json` |
| 🔀 **Симметрическая разность** (G1 △ G2) | `beatrice graph symdiff g1.json g2.json` |
| 📊 **Статистика графа** | `beatrice stat graph.json` |
| 🌐 **Визуализация** в standalone HTML | `beatrice graph render graph.json` |

---

## Быстрый старт

### Установка

**Рекомендуемый способ:** установка пакета через pip в режиме editable для разработки:

```bash
git clone <repo_url>
cd Beatrice
pip install -e .           # только CLI
pip install -e ".[tui]"    # CLI + TUI
pip install -e ".[web]"    # CLI + Web GUI (бета)
pip install -e ".[tui,web]"  # Всё вместе
```

После установки доступны три глобальные команды:
- `beatrice` — CLI
- `beatrice-tui` — TUI
- `beatrice-web` — Web GUI (FastAPI + React)

**Зависимости:** ядро требует только `networkx`. TUI-режим — `textual` и `rapidfuzz`. Web-режим — `fastapi`, `uvicorn`, `websockets`.

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
beatrice stat graph.json
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
beatrice graph search graph.json "Orphan"
```

### Добавить узел

```bash
beatrice graph add-node graph.json Redis \
  --label Redis --type "БД" --desc "In-memory cache"
```

### Посмотреть соседей

```bash
beatrice graph neighbors graph.json Kafka --direction all
```

### Сгенерировать HTML-визуализацию

```bash
beatrice graph render graph.json
```

Открой `graph.html` в браузере — интерактивный force-directed граф с zoom/pan/tooltip/легендой.

---

## Полная документация CLI

```
Использование:
  beatrice graph search    <graph.json> <query>   [--regex] [--json]
  beatrice graph neighbors <graph.json> <node>    [--direction out|in|all] [--json]
  beatrice graph orphans   <graph.json>
  beatrice graph roots     <graph.json>
  beatrice graph frontier  <graph.json>
  beatrice graph add-node  <graph.json> <id...>   [--label --type --desc --color --size]
  beatrice graph edit-node <graph.json> <id>     [--label --type --desc --color --size]
  beatrice graph islands  <graph.json>
  beatrice graph louvain <graph.json>     [--seed N]
  beatrice graph ring      <graph.json> <node>  --min N --max M [--direction]
  beatrice graph tag       <graph.json> <node> add|rm|ls|clear <tag...>
  beatrice graph rm-node   <graph.json> <id...>
  beatrice graph add-edge  <graph.json> <src...> <tgt...> [--relation --weight]
  beatrice graph rm-edge   <graph.json> <src...> <tgt...>
  beatrice graph intersect <graph1.json> <graph2.json>
  beatrice graph union     <graph1.json> <graph2.json>
  beatrice graph diff      <graph1.json> <graph2.json>
  beatrice graph symdiff   <graph1.json> <graph2.json>
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

### `graph roots`

```bash
beatrice graph roots graph.json
```

Показывает корневые узлы — которые сами ссылаются на других (out_degree > 0), но на них никто не ссылается (in_degree == 0).

### `graph frontier`

```bash
beatrice graph frontier graph.json
beatrice graph front graph.json      # алиас
```

Показывает пограничные узлы — на которых ссылаются (in_degree > 0), но сами никуда не ссылаются (out_degree == 0). Сироты не включаются.

### `graph islands`

```bash
beatrice graph islands graph.json
beatrice graph isl graph.json          # алиас
beatrice graph components graph.json   # алиас
```

Показывает изолированные кластеры (компоненты слабой связности). Узлы, между которыми есть путь в любом направлении — на одном острове.

Острова отсортированы по размеру (от большого к малому), узлы внутри — по алфавиту.

```
$ beatrice graph islands graph.json

Остров #1 (4 узла):
  kafka    «Kafka»           брокер
  connect  «Kafka Connect»   сервис
  sr       «Schema Reg»      сервис
  zk       «ZooKeeper»       координатор

Остров #2 (1 узел) 👻 сирота:
  orphan   «Сирота»          unknown

Всего островов: 2
```

### `graph louvain`

```bash
beatrice graph louvain graph.json
beatrice graph lv graph.json               # алиас
beatrice graph louvain graph.json --seed 0  # кастомный seed
```

Кластеризация Louvain: разбивает граф на сообщества по плотности внутренних связей.
Вывод — как у `islands`: сообщества отсортированы по размеру, узлы внутри — по алфавиту.

```
$ beatrice graph louvain graph.json

Сообщество #1 (3 узла):
  kafka    «Kafka»           брокер
  connect  «Kafka Connect»   сервис
  sr       «Schema Reg»      сервис

Сообщество #2 (2 узла):
  zk       «ZooKeeper»       координатор
  orphan   «Сирота»          unknown

Всего сообществ: 2
```

### `graph ring`

```bash
beatrice graph ring graph.json Kafka --min 2 --max 4
beatrice graph rng graph.json Kafka --min 0 --max 1 --direction descending
```

BFS от указанного узла, XOR слоёв: узлы на диапазоне глубин (min+1..max).

Параметры:
- `--min` (обязательный) — минимальная глубина (≥0)
- `--max` (обязательный) — максимальная глубина (≥min)
- `--direction` — `descending` (только нисходящие), `ascending` (только восходящие), `omnidirectional` (по умолчанию, оба направления)

```
$ beatrice graph ring graph.json a --min 2 --max 4

Кольца 3–4 от узла «a» (all):

Глубина 3:
  d       «D»

Глубина 4:
  e       «E»

Найдено: 2 узла
```

### `graph tag`

Управление тегами узлов. Теги — произвольные строки, хранятся в поле `tags` каждого узла.

```bash
beatrice graph tag add   graph.json Kafka streaming kafka-экосистема
beatrice graph tag rm    graph.json Kafka temp
beatrice graph tag ls    graph.json              # все теги графа
beatrice graph tag ls    graph.json Kafka         # теги конкретного узла
beatrice graph tag clear graph.json Kafka
```

Параметры:
- `add <graph> <id...> <tag...>` — добавить теги к узлу (узлам)
- `rm <graph> <id...> <tag...>` — удалить теги из узла (узлов)
- `ls <graph> [id]` — без id показывает все теги графа с частотой, с id — теги узла
- `clear <graph> <id...>` — очистить все теги узла (узлов)

Фильтрация по тегам доступна на командах `search`, `neighbors`, `islands`, `ring`:

```bash
beatrice graph search graph.json "" --tag streaming --tag-mode any
beatrice graph islands graph.json --tag kafka --tag-mode all
beatrice graph ring graph.json Kafka --min 0 --max 2 --tag streaming
```

- `--tag` можно указывать несколько раз
- `--tag-mode` принимает `any` (по умолчанию) или `all`

### `graph edit-node`

```bash
beatrice graph edit-node graph.json Kafka --label "Apache Kafka" --desc "Event streaming platform"
beatrice graph edit-node graph.json Kafka --type "брокер" --color "#FF0000"
beatrice graph en graph.json Kafka --label "Kafka"    # алиас en
```

Patch-only: меняются только те атрибуты, что переданы флагами. Остальные остаются нетронутыми.

Параметры: `--label`, `--type`, `--desc`, `--color` (hex), `--size` (число).

Если узел не найден — ошибка и файл не трогается. Если не передано ни одного флага — «Ничего не изменено».

```
$ beatrice graph edit-node graph.json Kafka --label "Apache Kafka" --desc "Event streaming"
Изменён узел Kafka:
  label    Kafka → Apache Kafka
  desc     (пусто) → Event streaming
```

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

### `graph intersect` / `union` / `diff` / `symdiff`

Операции над множествами графов. Принимают два графа, выводят JSON node-link результата в stdout.

```bash
beatrice graph intersect g1.json g2.json   # G1 ∩ G2 — узлы в обоих
beatrice graph union     g1.json g2.json   # G1 ∪ G2 — все узлы из обоих
beatrice graph diff      g1.json g2.json   # G1 ∖ G2 — узлы из G1, которых нет в G2
beatrice graph symdiff   g1.json g2.json   # G1 △ G2 — узлы только в одном из графов
```

Результат можно пайпить в другие команды:

```bash
beatrice graph diff g1.json g2.json | beatrice graph ring - Kafka --min 0 --max 2
beatrice graph intersect g1.json g2.json | beatrice graph stat -
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

### `--json` / `--output-format`

Команды `search`, `neighbors`, `orphans`, `roots`, `frontier`, `islands`, `louvain`, `ring` поддерживают
вывод в формате JSON вместо текста — подграф в формате node-link со всеми атрибутами:

```bash
beatrice graph search graph.json "kafka" --json
beatrice graph roots graph.json --output-format json | jq '.nodes[].id'
```

Флаг `--json` — сокращение для `--output-format json`.

### `-` (stdin pipe)

Любая команда может читать граф из stdin вместо файла, передав `-` как путь:

```bash
beatrice graph search g.json kafka --json | beatrice graph ring - Kafka --min 0 --max 1
beatrice graph diff g1.json g2.json | beatrice graph tag add - MyNode mytag
```

Для мутирующих команд результат записывается в stdout (JSON node-link) вместо файла на диске.

### `tui`

```bash
beatrice tui graph.json
```

Запускает Terminal UI для интерактивной работы с графом:

- **Три панели:** список узлов (слева), форма редактирования (центр), список связей (справа)
- **Vim-моты:** `hjkl` для навигации, `o` открыть, `s` поиск, `x` фильтр сирот
- **Палитра команд** по `:` — фильтруемый список 16 команд
- **Fuzzy-поиск** через rapidfuzz по id, label, type узлов
- **Undo/Redo** через Ctrl+Z/Ctrl+Y (25 последних действий)
- **Редактирование** узлов: label, type, description, color, size
- **Управление связями:** добавить/удалить/редактировать через диалоги
- **Help** по `?`, **темы** через `:theme dark|light`
- Поддержка мыши

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

107 тестов: CLI (86) + TUI (21): load/save, CRUD, history, undo/redo, messages, islands, tags, ring, louvain, set operations, json output, stdin pipe.

---

## Web GUI (бета)

> Интерактивный редактор графов в браузере на React + D3.js + FastAPI WebSocket.

### Установка

```bash
pip install -e ".[web]"
cd beatrice/web_gui/frontend && npm install && npm run build
```

### Запуск

```bash
beatrice serve graph.json
```

Открой `http://127.0.0.1:8576` — три панели: список узлов, редактор, D3.js граф.

### Возможности Web GUI

- 🔍 **Поиск и фильтрация** узлов по строке, типу, тегам
- 📝 **CRUD узлов** — добавление, редактирование (label, type, desc, color, size), удаление
- 🔗 **CRUD связей** — добавление/удаление с типом связи, выбор узла из списка
- 🏷️ **CRUD тегов** — добавление/удаление тегов узла, статистика тегов графа
- 🌐 **Force-directed граф** (D3.js) с зумом, drag, тултипами
- 🧬 **Louvain-сообщества** — раскраска, фильтр по сообществу, легенда
- 👻 **Фильтр сирот** — скрыть/показать узлы без связей
- 🎨 **Подсветка по тегу** — выбор тега + палитра цветов
- 💾 **Ручное сохранение** (Ctrl+S / кнопка Save)
- 🔄 **Reload** — перезагрузка с диска

### Режим разработки

```bash
# Терминал 1: FastAPI сервер
beatrice serve graph.json --dev

# Терминал 2: Vite HMR
cd beatrice/web_gui/frontend && npm run dev
```

Vite dev server на `http://localhost:5173` с HMR, проксирует `/ws` на FastAPI.

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
