# Task Specification — Beatrice Web GUI v1

## Summary

Разработать Web GUI для библиотеки Beatrice — FastAPI + WebSocket бэкенд с React SPA фронтендом, встроенный в пакет `beatrice` как subpackage `beatrice/web_gui/`.

## Motivation

Текущий TUI (Textual) функционален, но терминальный интерфейс неудобен для широкого круга пользователей. Web GUI даст визуальный доступ к графам знаний через браузер с теми же возможностями редактирования и интерактивной визуализацией на D3.js.

## Requirements

### 1. Архитектура

- **Расположение:** `beatrice/web_gui/` (subpackage внутри `beatrice`)
- **Бэкенд:** `beatrice/web_gui/server.py` — FastAPI-сервер
- **Фронтенд:** `beatrice/web_gui/frontend/` — React SPA (Vite + TypeScript + React Router)
- **Entry point:** `beatrice serve <graph.json>` — запускает FastAPI-сервер на порту 8576
  - Обязательный аргумент — путь к файлу графа
  - Если не указан — ошибка
- **Протокол:** WebSocket (JSON-RPC) для всех операций
- **Сохранение:** только ручное (кнопка Save / Ctrl+S). Сервер не пишет на диск автоматически.

### 2. Бэкенд (FastAPI)

#### 2.1 Запуск

```
beatrice serve graph.json
```

- Раздаёт статику из `frontend/dist/` в production
- В dev-режиме — CORS для Vite dev server (localhost:5173)
- При старте загружает граф из переданного файла в `GraphManager` (из `beatrice.tui.graph_manager`)
- WebSocket endpoint: `ws://localhost:8576/ws`

#### 2.2 WebSocket (JSON-RPC)

Формат запроса:
```json
{"method": "add_node", "params": {"id": "kafka", "label": "Kafka", "type": "Брокер"}, "id": 1}
```

Формат ответа (успех):
```json
{"result": {"node_id": "kafka"}, "id": 1}
```

Формат ответа (ошибка):
```json
{"error": {"code": -32000, "message": "Узел уже существует"}, "id": 1}
```

#### 2.3 Методы API

##### Узлы
- `add_node` — добавить узел (id, label, type, desc, color, size, tags)
- `remove_node` — удалить узел (и его связи)
- `update_node` — обновить атрибуты узла (patch)
- `get_node` — получить данные узла
- `list_nodes` — список всех узлов (id, label, type, tags)
- `search_nodes` — поиск по строке (id/label)
- `move_node` — переименовать узел (с сохранением связей)

##### Связи
- `add_edge` — добавить связь (source, target, relation, weight)
- `remove_edge` — удалить связь
- `update_edge` — обновить атрибуты связи
- `list_edges` — список всех связей (для узла или всех)
- `list_edges_for_node` — связи конкретного узла (с разделением in/out)

##### Теги
- `tag_add` — добавить теги к узлу(ам)
- `tag_remove` — удалить теги из узла(ов)
- `tag_clear` — очистить все теги узла
- `tag_list` — список тегов (всех или конкретного узла) со статистикой (counts)
- `tag_nodes` — получить узлы с указанными тегами

##### Граф (визуализация)
- `get_graph_state` — полный дамп графа для инициализации (nx.node_link_data)
- `get_graph_stats` — статистика: кол-во узлов, рёбер, сирот, плотность, PageRank топ-5, Louvain-сообщества, компоненты слабой связности
- `get_louvain` — данные Louvain-сообществ для раскраски
- `get_neighbors` — соседи узла (in/out)
- `get_ring` — кольца узла (BFS диапазон)
- `get_islands` — компоненты слабой связности
- `get_roots` — корневые узлы
- `get_frontier` — пограничные узлы

##### Файл
- `save` — сохранить граф на диск
- `reload` — перезагрузить файл с диска (сброс несохранённых изменений)
- `get_file_info` — путь к файлу, dirty-статус

#### 2.4 Инкрементальные события

После любого мутирующего метода сервер шлёт событие **всем подключенным клиентам**:

```json
{"jsonrpc": "2.0", "method": "event", "params": {"type": "node_added", "payload": {"node_id": "kafka", "data": {...}}}}
```

Типы событий:
- `node_added` — добавлен узел (данные нового узла)
- `node_removed` — удалён узел (id)
- `node_updated` — изменён узел (данные после изменения)
- `edge_added` — добавлена связь (source, target, data)
- `edge_removed` — удалена связь (source, target)
- `edge_updated` — изменена связь (source, target, data)
- `tags_changed` — изменены теги узла (node_id, tags)
- `graph_updated` — общее изменение (если несколько операций сразу, например reload)

### 3. Фронтенд (React SPA)

#### 3.1 Структура

```
beatrice/web_gui/frontend/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── index.html
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/
│   │   ├── websocket.ts       # WebSocket JSON-RPC клиент
│   │   └── types.ts           # TS типы для API
│   ├── store/
│   │   ├── graphStore.ts      # Zustand-подобный стор графа
│   │   └── uiStore.ts         # Стор UI-состояния (выбранный узел, панели)
│   ├── components/
│   │   ├── Layout.tsx         # Главный лэйаут (3 панели)
│   │   ├── NodesList/
│   │   │   ├── NodesList.tsx   # Панель списка узлов (слева)
│   │   │   ├── NodeItem.tsx
│   │   │   └── FilterBar.tsx   # Поиск + фильтр по типу/тегам
│   │   ├── NodeEditor/
│   │   │   ├── NodeEditor.tsx   # Форма редактирования узла (центр)
│   │   │   ├── AttributesForm.tsx
│   │   │   ├── TagsEditor.tsx   # CRUD тегов узла + статистика
│   │   │   └── EdgeList.tsx     # Список связей узла (in/out) с CRUD
│   │   └── GraphView/
│   │       ├── GraphView.tsx    # D3.js force-directed граф (правая панель)
│   │       ├── GraphControls.tsx # Кнопки/селекты управления графом
│   │       └── Tooltip.tsx      # Тултип при клике
│   └── styles/
│       └── global.css
```

#### 3.2 Три панели (UX)

**Левая панель — NodesList:**
- Список всех узлов (id, label, type, tags)
- Поиск/фильтрация по строке (fuzzy через rapidfuzz-like на клиенте или серверный поиск)
- Фильтр по типу узла
- Фильтр по тегам (селект с множественным выбором)
- Переключатель «только сироты»
- Клик по узлу → выделение на графе + форма редактирования в центре

**Центральная панель — NodeEditor:**
- Отображается при выборе узла (если не выбран — заглушка «Выберите узел»)
- Поля: ID (нередактируемый), Label (текст), Type (текст), Description (textarea), Color (color picker), Size (number)
- Кнопки: Save, Delete node (с подтверждением)
- TagsEditor: список тегов узла, кнопка «+» для добавления, крестик для удаления, статистика тегов всего графа ниже
- EdgeList: таблица связей — входящие и исходящие. Каждая строка: source → relation → target. Кнопки «+» (добавить связь, выбор узла из списка), «×» (удалить)
- Кнопка «Move/Rename» — диалог переименования узла

**Правая панель — GraphView:**
- D3.js force-directed граф на весь экран панели (или placeholder, занимающий доступное пространство)
- При невыбранном узле — весь граф
- При выборе узла — подсветка его и его соседей первого уровня (остальные полупрозрачные)

#### 3.3 GraphView (D3.js)

Полный функционал из текущего HTML render:

- Force-directed layout (d3.forceSimulation)
- Zoom/pan (d3.zoom)
- Drag узлов
- Клик по узлу → выделение + открытие формы в центре
- Двойной клик → отпустить узел (зафиксировать позицию/снять фиксацию)
- Стрелки направлений (marker-end) с возможностью скрыть/показать
- Фильтр сирот (скрыть/показать)
- Louvain-раскраска: переключатель, select-сообщество, легенда
- Подсветка по тегу: select тега + color picker — узлы с этим тегом подсвечиваются выбранным цветом
- Типовая раскраска узлов (по полю type) + легенда
- Тултип при клике/ховере: id, label, description, type, tags
- Информация в углу: кол-во узлов, рёбер, сирот

**Дополнительно (новое):**
- При клике на узел на графе — синхронизация с NodesList (скролл до узла) и NodeEditor (открытие формы)

#### 3.4 Прочие UI элементы

- **Тулбар (верх):**
  - Название файла
  - Кнопка Save (Ctrl+S) — отправляет `save` метод на сервер
  - Кнопка Reload — перезагрузить с диска (с подтверждением, если есть несохранённые)
  - Статус подключения WebSocket (зелёный/красный индикатор)
  - Dark theme (наследовать от текущего render — чёрная тема #1a1a2e)

- **Глобальный поиск:** Ctrl+F или поле в тулбаре — поиск по всем узлам, результаты в дропдауне

- **Подтверждения:** удаление узла/связи — confirm dialog

#### 3.5 Стейт-менеджмент

- `graphStore` — состояние графа на клиенте: узлы Map<id, NodeData>, связи, теги, статистика
- После init (get_graph_state) — полная загрузка
- При инкрементальных событиях — патч стора без полной перезагрузки

### 4. Разработка

- **Dev:** Vite dev server (HMR): `cd frontend && npm run dev`
  - FastAPI-сервер с CORS для localhost:5173
  - Для удобства: Makefile target `dev-web` запускает оба
- **Prod:** `cd frontend && npm run build` → FastAPI раздаёт `frontend/dist/`
- **Production dependency:** uvicorn
- **Dev dependency:** node, npm, Vite

### 5. Зависимости Python (добавить в pyproject.toml)

```toml
[project.optional-dependencies]
web = [
    "fastapi",
    "uvicorn[standard]",
    "websockets",
]
```

## Success Criteria

- [ ] `beatrice serve graph.json` запускает сервер на :8576, открывается браузер
- [ ] Левая панель показывает список узлов с поиском и фильтрацией
- [ ] Выбор узла в списке → открывается форма редактирования в центре + подсветка на графе
- [ ] Можно добавить/редактировать/удалить узел через форму
- [ ] Можно добавить/удалить связь между узлами с типом связи
- [ ] Можно добавить/удалить теги узла + просмотр статистики тегов графа
- [ ] D3.js граф отображается с force-directed layout, zoom, drag, стрелками
- [ ] Переключение Louvain-раскраски работает
- [ ] Фильтр сирот работает
- [ ] Подсветка по тегу работает
- [ ] Клик по узлу на графе → синхронизация со списком и формой
- [ ] Сохранение через Ctrl+S / кнопку Save
- [ ] Переоткрытие другого файла через Reload
- [ ] WebSocket reconnect при обрыве
- [ ] Русскоязычный интерфейс
- [ ] `npm run build` → FastAPI раздаёт статику, всё работает в production режиме

## Scope

**In scope:**
- FastAPI сервер с WebSocket JSON-RPC
- GraphManager как основа состояния на сервере (из beatrice.tui.graph_manager)
- React SPA с тремя панелями
- D3.js визуализация с полным функционалом
- CRUD узлов, связей, тегов
- Ручное сохранение
- Деплой: Vite build + FastAPI static

**Out of scope:**
- Undo/redo в Web GUI (есть в TUI, но не переносим)
- Автосохранение
- Множественные файлы/вкладки
- Sigma.js или Cytoscape альтернативы
- Аутентификация/авторизация
- Docker-контейнеризация
- Поддержка мобильных устройств (responsive — бонус, но не цель)
- Export/import других форматов (кроме JSON node-link)
- Batch-операции через Web UI

## Open Questions

Нет — все неопределённости разрешены.
