---
name: beatrice
description: "CLI и TUI для построения и редактирования графов знаний на базе NetworkX."
---

# Beatrice — Knowledge Graph CLI & TUI

Beatrice — это инструмент для построения и редактирования графов знаний через терминал. Состоит из двух интерфейсов — CLI (командная строка) и TUI (терминальный интерфейс). Оба работают с одним форматом данных — JSON node-link.

## Быстрый старт

### Установка

```bash
git clone <repo_url>
cd ~/wss/ai/Beatrice
pip install -e .           # только CLI
pip install -e ".[tui]"    # CLI + TUI
```

После установки доступны две команды:
- `beatrice` — CLI
- `beatrice-tui` — TUI

### CLI

```bash
# Создать граф из скрипта Python
python3 -c "
import networkx as nx, json
G = nx.DiGraph()
G.add_node('Python', label='Python', type='язык', desc='Язык программирования')
G.add_node('Pytest', label='Pytest', type='инструмент', desc='Фреймворк для тестов')
G.add_edge('Pytest', 'Python', relation='написан на')
Path('graph.json').write_text(json.dumps(nx.node_link_data(G), ensure_ascii=False, indent=2), encoding='utf-8')
"

# Статистика
beatrice stat graph.json

# Поиск узлов
beatrice graph search graph.json "Python"
beatrice graph search graph.json "pyt.*" --regex

# Найти сирот (узлы без связей)
beatrice graph orphans graph.json

# Показать соседей узла
beatrice graph neighbors graph.json Python --direction all

# Добавить узел
beatrice graph add-node graph.json Rust --label Rust --type язык

# Удалить узел (со всеми связями)
beatrice graph rm-node graph.json Rust

# Добавить ребро
beatrice graph add-edge graph.json Pytest Python --relation тестирует

# Удалить ребро
beatrice graph rm-edge graph.json Pytest Python

# Сгенерировать HTML-визуализацию
beatrice graph render graph.json
open graph.html
```

### TUI

```bash
beatrice-tui graph.json
```

**Навигация:**
- `h`/`l` — переключение между панелями
- `j`/`k` — вверх/вниз по спискам
- `o`/`Enter` — открыть узел/ссылку
- `s` — поиск (fuzzy) в списке узлов
- `x` — цикл фильтра сирот (any/orphans/non-orphans)
- `a` — добавить (узел/ссылку в зависимости от панели)
- `d` — удалить (узел/ссылку)
- `r` — редактировать relation связи
- `:` — палитра команд (список с фильтрацией)
- `Ctrl+s` — сохранить граф
- `?` — справка
- `Escape` — отменить редактирование/закрыть

## Формат данных

Граф хранится в JSON node-link — стандартном формате NetworkX:

```json
{
  "directed": true,
  "multigraph": false,
  "graph": {},
  "nodes": [
    {"id": "Python", "label": "Python", "type": "язык", "desc": "Язык программирования"}
  ],
  "edges": [
    {"source": "Pytest", "target": "Python", "relation": "тестирует"}
  ]
}
```

Атрибуты `label`, `type`, `desc`, `color`, `size`, `note` — опциональные, используются для отображения в TUI и HTML-визуализации. Можно добавлять свои.

Поле `note` предназначено для Obsidian-ссылки в формате `obsidian://open?vault=НАЗВАНИЕ&file=Путь/к/Заметке`. Используется:
- В Web GUI: поле в редакторе, кнопка «Открыть», фильтр/подсветка узлов без конспекта
- В CLI: атрибут `--note` у команд `add-node` и `edit-node`
- В HTML render: ссылка «📝 Конспект» в тултипе узла

### Obsidian CLI: определение хранилища

Obsidian CLI (доступен с v1.12.4+) — официальный CLI, работает как пульт для запущенного Obsidian. Требует включения в настройках Obsidian (Settings → General → Command line interface).

**Проверка установки:**
```bash
obsidian version
```

**Определение хранилища (vault):**
```bash
obsidian vault               # имя и метаданные активного хранилища
obsidian vault info=path     # путь к хранилищу
obsidian vaults              # список всех известных хранилищ с путями
obsidian vaults verbose      # список с полными путями
```

Пример вывода `obsidian vaults`:
```
Knowledge    /Users/me/obsidian/knowledge
Work         /Users/me/obsidian/work
```

**Применение в Beatrice:**
- `obsidian vaults` позволяет агенту определить, какой vault соответствует `obsidian://open?vault=...` URI у узла графа
- Путь к vault нужен для: чтения содержимого заметки (`obsidian read`), верификации существования файла, синхронизации атрибутов между графом и заметкой
- Obsidian CLI не является зависимостью Beatrice — функционал `note` работает и без него, CLI только расширяет возможности

## Поиск сирот

Узлы без единой связи (степень 0):
```bash
beatrice graph orphans graph.json
```

В TUI: клавиша `x` переключает фильтр сирот (any → orphans → non-orphans).

## HTML-визуализация

```bash
beatrice graph render graph.json
```

Генерирует `graph.html` — standalone интерактивный D3.js force-directed граф с zoom/pan/tooltip/легендой/кнопками.

## Команды CLI (полный список)

| Команда | Назначение |
|---------|-----------|
| `beatrice stat <graph>` | Статистика (узлы, рёбра, плотность, сироты, PageRank, Louvain, острова, конспекты) |
| `beatrice graph search <graph> <query>` | Поиск узлов по строке или regex (--note with/without) |
| `beatrice graph neighbors <graph> <node>` | Соседи узла (--direction out\|in\|all, --note with/without) |
| `beatrice graph orphans <graph>` | Список сирот (--note with/without) |
| `beatrice graph roots <graph>` | Корневые узлы (out>0, in=0) (--note with/without) |
| `beatrice graph frontier <graph>` | Пограничные узлы (in>0, out=0) (--note with/without) |
| `beatrice graph islands <graph>` | Изолированные кластеры (--note with/without) |
| `beatrice graph louvain <graph>` | Louvain-сообщества |
| `beatrice graph ring <graph> <node> --min N --max M` | Узлы на диапазоне глубин (--note with/without) |
| `beatrice graph note add <graph> <id...> <uri>` | Задать Obsidian-ссылку узлу |
| `beatrice graph note rm <graph> <id...>` | Очистить Obsidian-ссылку узла |
| `beatrice graph note ls <graph> [id]` | Статистика конспектов или --with/--without |
| `beatrice graph tag add <graph> <id...> <tag...>` | Добавить теги к узлу |
| `beatrice graph tag rm <graph> <id...> <tag...>` | Удалить теги из узла |
| `beatrice graph tag ls <graph> [id]` | Показать теги (всех или узла) |
| `beatrice graph tag clear <graph> <id...>` | Очистить теги узла |
| `beatrice graph add-node <graph> <id...>` | Добавить узел с --label,--type,--desc,--color,--size,--note |
| `beatrice graph edit-node <graph> <id>` | Изменить атрибуты узла (patch-only, --note в т.ч.) |
| `beatrice graph rm-node <graph> <id...>` | Удалить узел |
| `beatrice graph add-edge <graph> <src...> <tgt...>` | Добавить ребро с --relation,--weight |
| `beatrice graph rm-edge <graph> <src...> <tgt...>` | Удалить ребро |
| `beatrice graph intersect <g1> <g2>` | Пересечение графов (G1 ∩ G2) |
| `beatrice graph union <g1> <g2>` | Объединение графов (G1 ∪ G2) |
| `beatrice graph diff <g1> <g2>` | Разность графов (G1 ∖ G2) |
| `beatrice graph symdiff <g1> <g2>` | Симметрическая разность (G1 △ G2) |
| `beatrice graph render <graph>` | Сгенерировать HTML-визуализацию (--theme dark\|light) |

## Источник

Код: `~/wss/ai/Beatrice/`
Документация: `~/wss/ai/Beatrice/README.md`
Планы: `~/wss/ai/Beatrice/PLAN.md`
Модель данных: `~/wss/ai/Beatrice/docs/data-model.md`
