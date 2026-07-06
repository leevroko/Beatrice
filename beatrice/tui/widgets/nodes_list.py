"""Левый вьюпорт — список всех узлов с фильтрацией."""

from textual.widgets import Static, ListView, ListItem, Label, Input
from textual.containers import Vertical
from textual.keys import Keys
from rapidfuzz import fuzz

from beatrice.tui.messages import NodeSelected, StatusMessage


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

    BINDINGS = [
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("g", "cursor_first", "First"),
        ("G", "cursor_last", "Last"),
        ("o", "open_node", "Open"),
        ("s", "search", "Search"),
        ("x", "cycle_orphan_filter", "Orphan filter"),
        ("a", "add_node", "Add node"),
        ("d", "delete_node", "Delete"),
        ("escape", "escape_search", "Clear search"),
    ]

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
        margin-bottom: 1;
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

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._all_items: list[dict] = []
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

    def on_focus(self) -> None:
        """При фокусе — показать контекстные подсказки."""
        self.post_message(StatusMessage(
            "j/k: nav  o: open  s: search  x: orphans  a: add  d: delete", "info"
        ))

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
        counter_str = f"{shown} / {total}"
        if self._show_orphans == "orphans":
            counter_str += " 👻 orphans"
        elif self._show_orphans == "non-orphans":
            counter_str += " 🔗 non-orphans"
        counter.update(counter_str)

    def _filter_items(self) -> list[dict]:
        """Применить fuzzy-поиск и фильтр сирот."""
        items = self._all_items

        if self._show_orphans == "orphans":
            items = [i for i in items if i["is_orphan"]]
        elif self._show_orphans == "non-orphans":
            items = [i for i in items if not i["is_orphan"]]

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
        item = event.item
        if isinstance(item, NodeItem):
            self.post_message(NodeSelected(item.node_id))
            self.post_message(StatusMessage(
                f"Opened: {item.node_id}", "success"
            ))

    def action_cursor_down(self) -> None:
        lv = self.query_one("#nodes-list", ListView)
        if lv.index is None:
            lv.index = 0
        elif lv.index < len(lv.children) - 1:
            lv.index += 1
        lv.action_cursor_down()

    def action_cursor_up(self) -> None:
        lv = self.query_one("#nodes-list", ListView)
        if lv.index is None:
            lv.index = 0
        elif lv.index > 0:
            lv.index -= 1
        lv.action_cursor_up()

    def action_cursor_first(self) -> None:
        lv = self.query_one("#nodes-list", ListView)
        if len(lv.children) > 0:
            lv.index = 0

    def action_cursor_last(self) -> None:
        lv = self.query_one("#nodes-list", ListView)
        if len(lv.children) > 0:
            lv.index = len(lv.children) - 1

    def action_search(self) -> None:
        self.query_one("#nodes-search", Input).focus()

    def action_escape_search(self) -> None:
        search = self.query_one("#nodes-search", Input)
        if search.value:
            search.value = ""
            self._query = ""
            self._refresh_list()
        self.focus()

    def action_cycle_orphan_filter(self) -> None:
        cycle = {"any": "orphans", "orphans": "non-orphans", "non-orphans": "any"}
        self._show_orphans = cycle[self._show_orphans]
        self._refresh_list()

    def action_open_node(self) -> None:
        lv = self.query_one("#nodes-list", ListView)
        if lv.index is not None and lv.index < len(lv.children):
            item = lv.children[lv.index]
            if isinstance(item, NodeItem):
                self.post_message(NodeSelected(item.node_id))

    def action_add_node(self) -> None:
        """Добавить новый узел через диалог."""
        from beatrice.tui.widgets.dialogs import AddNodeDialog

        default_id = self.app.graph_manager.next_node_id()

        def on_dialog(result):
            if result is None:
                return
            nid = result["id"]
            attrs = {k: v for k, v in result.items() if k != "id" and v}
            gm = self.app.graph_manager
            if gm.has_node(nid):
                self.post_message(StatusMessage(f"Node '{nid}' already exists", "warning"))
                return
            gm.add_node(nid, **attrs)
            self.load_from_graph_manager(gm)
            self.post_message(NodeSelected(nid))
            self.post_message(StatusMessage(f"Node added: {nid}", "success"))

        self.app.push_screen(AddNodeDialog(default_id=default_id), on_dialog)

    def action_delete_node(self) -> None:
        """Удалить узел с подтверждением."""
        lv = self.query_one("#nodes-list", ListView)
        if lv.index is None or lv.index >= len(lv.children):
            return
        item = lv.children[lv.index]
        if not isinstance(item, NodeItem):
            return
        nid = item.node_id
        gm = self.app.graph_manager

        from beatrice.tui.widgets.dialogs import ConfirmDialog
        degree = gm.degree(nid)
        msg = f"Delete node '{nid}'?"
        if degree > 0:
            msg += f"\nAll {degree} connection(s) will also be removed."

        def on_confirm(result):
            if not result:
                return
            gm.remove_node(nid)
            self.load_from_graph_manager(gm)
            # Выбрать другой узел, если возможно
            all_nodes = gm.all_nodes()
            if all_nodes:
                self.post_message(NodeSelected(all_nodes[0]))
            self.post_message(StatusMessage(f"Deleted: {nid}", "success"))

        self.app.push_screen(ConfirmDialog("Delete node", msg), on_confirm)
