"""Левый вьюпорт — список всех узлов с фильтрацией."""

from textual.widgets import Static, ListView, ListItem, Label, Input
from textual.containers import Vertical, Horizontal
from textual.reactive import reactive
from rapidfuzz import fuzz

from beatrice.tui.messages import NodeSelected, FilterChanged, StatusMessage


class NodeItem(ListItem):
    """Один элемент в списке узлов."""

    def __init__(self, node_id: str, label: str, type_str: str,
                 is_orphan: bool = False) -> None:
        self.node_id = node_id
        self.is_orphan = is_orphan
        orphan_tag = " 👻" if is_orphan else ""
        type_tag = f" [{type_str}]" if type_str else ""
        label_text = label or node_id
        super().__init__(
            Label(f"{label_text}{type_tag}{orphan_tag}")
        )


class NodesList(Static):
    """Список узлов с fuzzy-поиском и фильтром сирот."""

    CSS = """
    NodesList {
        height: 100%;
        overflow-y: auto;
    }

    #nodes-search {
        dock: top;
        margin: 0 0 1 0;
        background: #0f3460;
        border: none;
        color: #eee;
    }

    #nodes-search:focus {
        border: tall #e94560;
    }

    #nodes-header {
        color: #e94560;
        text-style: bold;
        margin-bottom: 1;
    }

    #nodes-counter {
        color: #888;
        text-style: italic;
    }

    #nodes-list {
        height: 1fr;
        border: none;
    }

    ListView {
        background: #16213e;
    }

    ListView:focus {
        border: none;
    }

    ListItem {
        padding: 0 1;
    }

    ListItem:hover {
        background: #0f3460;
    }

    ListItem.--highlight {
        background: #e94560;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._all_items: list[dict] = []  # {"id": ..., "label": ..., "type": ..., "is_orphan": ...}
        self._query = ""
        self._show_orphans = "any"

    def compose(self):
        yield Label("Nodes", id="nodes-header")
        yield Input(placeholder="🔍 Search nodes...", id="nodes-search")
        yield Label("", id="nodes-counter")
        yield ListView(id="nodes-list")

    def on_mount(self) -> None:
        self._refresh_list()

    def load_from_graph_manager(self, gm) -> None:
        """Загрузить данные из GraphManager."""
        self._all_items = []
        gm_orphans = set(gm.orphans)
        for nid in gm.all_nodes():
            attrs = gm.node_attrs(nid)
            self._all_items.append({
                "id": nid,
                "label": attrs.get("label", nid),
                "type": attrs.get("type", ""),
                "is_orphan": nid in gm_orphans,
            })
        self._refresh_list()

    def _refresh_list(self) -> None:
        """Отфильтровать и обновить список."""
        list_view = self.query_one("#nodes-list", ListView)
        counter = self.query_one("#nodes-counter", Label)

        filtered = self._filter_items()

        list_view.clear()
        for item in filtered:
            list_view.append(
                NodeItem(
                    item["id"],
                    item["label"],
                    item["type"],
                    item["is_orphan"],
                )
            )

        total = len(self._all_items)
        shown = len(filtered)
        counter_str = f"{shown} / {total} nodes"
        if self._show_orphans == "orphans":
            counter_str += " [👻 orphans]"
        elif self._show_orphans == "non-orphans":
            counter_str += " [🔗 non-orphans]"
        counter.update(counter_str)

    def _filter_items(self) -> list[dict]:
        """Применить fuzzy-поиск и фильтр сирот."""
        items = self._all_items

        # Orphan filter
        if self._show_orphans == "orphans":
            items = [i for i in items if i["is_orphan"]]
        elif self._show_orphans == "non-orphans":
            items = [i for i in items if not i["is_orphan"]]

        # Fuzzy search
        if self._query:
            scored = []
            for item in items:
                score = max(
                    fuzz.partial_ratio(self._query.lower(), item["id"].lower()),
                    fuzz.partial_ratio(self._query.lower(), item["label"].lower()),
                    fuzz.partial_ratio(self._query.lower(), item["type"].lower()),
                )
                if score > 40:
                    scored.append((score, item))
            scored.sort(key=lambda x: -x[0])
            items = [item for _, item in scored]

        return items

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "nodes-search":
            self._query = event.value
            self._refresh_list()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Выбран узел — сообщаем."""
        item = event.item
        if isinstance(item, NodeItem):
            self.post_message(NodeSelected(item.node_id))

    # ────── Хоткеи ──────

    def action_search(self) -> None:
        """Фокус на строку поиска."""
        self.query_one("#nodes-search", Input).focus()

    def action_cycle_orphan_filter(self) -> None:
        """Цикл фильтра сирот: any → orphans → non-orphans → any."""
        cycle = {"any": "orphans", "orphans": "non-orphans", "non-orphans": "any"}
        self._show_orphans = cycle[self._show_orphans]
        self._refresh_list()
        self.post_message(StatusMessage(
            f"Filter: {self._show_orphans}", "info"
        ))

    def action_open_node(self) -> None:
        """Открыть выбранный узел."""
        list_view = self.query_one("#nodes-list", ListView)
        if list_view.index is not None and list_view.index < len(list_view):
            item = list_view.children[list_view.index]
            if isinstance(item, NodeItem):
                self.post_message(NodeSelected(item.node_id))
