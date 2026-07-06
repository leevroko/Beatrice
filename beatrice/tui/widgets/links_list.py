"""Правый вьюпорт — список связей текущего узла, добавление/удаление/редактирование."""

from textual.widgets import Static, Label, Input, ListView, ListItem
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.binding import Binding

from beatrice.tui.messages import NodeSelected, StatusMessage


class SectionLabel(Static):
    """Заголовок секции."""

    def __init__(self, text: str, **kwargs) -> None:
        super().__init__(text, **kwargs)


class LinkRow(Static):
    """Одна строка связи — кликабельна."""

    def __init__(self, node_id: str, relation: str = "",
                 direction: str = "out", **kwargs) -> None:
        self.node_id = node_id
        self.relation = relation
        self.direction = direction
        arrow = "→" if direction == "out" else "←"
        rel_part = f" [{relation}]" if relation else ""
        super().__init__(f"  {arrow} {node_id}{rel_part}", **kwargs)


class AddLinkDialog(ModalScreen):
    """Диалог добавления новой связи — выбор узла из списка."""

    CSS = """
    AddLinkDialog {
        align: center middle;
    }

    #dialog {
        width: 40;
        height: 24;
        background: #16213e;
        border: thick #e94560;
        padding: 2;
    }

    #dialog-title {
        color: #e94560;
        text-style: bold;
        margin-bottom: 1;
    }

    #dialog-search {
        background: #0f3460;
        border: solid #0f3460;
        color: #eee;
        margin-bottom: 1;
    }

    #dialog-search:focus {
        border: tall #e94560;
    }

    .dialog-input {
        background: #0f3460;
        border: solid #0f3460;
        color: #eee;
        margin-bottom: 1;
    }

    .dialog-input:focus {
        border: tall #e94560;
    }

    #dialog-list {
        height: 1fr;
        border: none;
        background: #0f3460;
    }

    ListItem {
        padding: 0 1;
    }

    ListItem:hover {
        background: #16213e;
    }

    ListItem.--highlight {
        background: #e94560;
    }

    #dialog-hint {
        color: #888;
        margin-top: 1;
    }
    """

    def __init__(self, source_node: str, all_nodes: list[str]) -> None:
        super().__init__()
        self.source_node = source_node
        self._all_nodes = all_nodes
        self._filtered = all_nodes[:]

    def compose(self):
        yield Vertical(
            Label(f"Add link from [bold]{self.source_node}[/bold]", id="dialog-title"),
            Input(placeholder="🔍 Search node...", id="dialog-search"),
            ListView(id="dialog-list"),
            Input(placeholder="Relation (optional)", id="dialog-relation", classes="dialog-input"),
            Label("Enter: add  Escape: cancel", id="dialog-hint"),
            id="dialog",
        )

    def on_mount(self) -> None:
        self._refresh_list("")
        self.query_one("#dialog-search", Input).focus()

    def _refresh_list(self, query: str) -> None:
        """Отфильтровать список узлов."""
        lv = self.query_one("#dialog-list", ListView)
        lv.clear()
        if query:
            from rapidfuzz import fuzz
            scored = []
            for n in self._all_nodes:
                score = fuzz.partial_ratio(query.lower(), n.lower())
                if score > 30:
                    scored.append((score, n))
            scored.sort(key=lambda x: -x[0])
            self._filtered = [n for _, n in scored]
        else:
            self._filtered = list(self._all_nodes)
        for n in self._filtered:
            lv.append(ListItem(Label(n)))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "dialog-search":
            self._refresh_list(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "dialog-relation":
            self._submit()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Выбран узел из списка."""
        item = event.item
        if isinstance(item, ListItem):
            label = item.children[0]
            if isinstance(label, Label):
                self.query_one("#dialog-search", Input).value = label.renderable
                self.query_one("#dialog-relation", Input).focus()

    def key_escape(self) -> None:
        self.dismiss(None)

    def _submit(self) -> None:
        target = self.query_one("#dialog-search", Input).value.strip()
        relation = self.query_one("#dialog-relation", Input).value.strip()
        if not target:
            self.query_one("#dialog-hint", Label).update("[red]Select or type a target node![/]")
            return
        self.dismiss({"target": target, "relation": relation})


class DeleteLinkConfirm(ModalScreen):
    """Подтверждение удаления связи."""

    CSS = """
    DeleteLinkConfirm {
        align: center middle;
    }

    #dialog {
        width: 40;
        height: auto;
        background: #16213e;
        border: thick #e94560;
        padding: 2;
    }

    #dialog-title {
        color: #e94560;
        text-style: bold;
        margin-bottom: 1;
    }

    #dialog-hint {
        color: #888;
        margin-top: 1;
    }
    """

    def __init__(self, source: str, target: str, relation: str = "") -> None:
        super().__init__()
        self.source = source
        self.target = target
        self.relation = relation

    def compose(self):
        rel = f" [{self.relation}]" if self.relation else ""
        yield Vertical(
            Label("Delete link?", id="dialog-title"),
            Label(f"{self.source} → {self.target}{rel}"),
            Label("y: confirm  Escape: cancel", id="dialog-hint"),
            id="dialog",
        )

    def key_y(self) -> None:
        self.dismiss(True)

    def key_escape(self) -> None:
        self.dismiss(None)


class EditRelationDialog(ModalScreen):
    """Диалог редактирования relation."""

    CSS = """
    EditRelationDialog {
        align: center middle;
    }

    #dialog {
        width: 40;
        height: auto;
        background: #16213e;
        border: thick #e94560;
        padding: 2;
    }

    #dialog-title {
        color: #e94560;
        text-style: bold;
        margin-bottom: 1;
    }

    .dialog-input {
        background: #0f3460;
        border: solid #0f3460;
        color: #eee;
        margin-bottom: 1;
    }

    .dialog-input:focus {
        border: tall #e94560;
    }

    #dialog-hint {
        color: #888;
        margin-top: 1;
    }
    """

    def __init__(self, source: str, target: str, old_relation: str = "") -> None:
        super().__init__()
        self.source = source
        self.target = target
        self.old_relation = old_relation

    def compose(self):
        yield Vertical(
            Label(f"Edit relation: {self.source} → {self.target}", id="dialog-title"),
            Input(value=self.old_relation, placeholder="Relation",
                  id="dialog-relation", classes="dialog-input"),
            Label("Enter: save  Escape: cancel", id="dialog-hint"),
            id="dialog",
        )

    def on_mount(self) -> None:
        self.query_one("#dialog-relation", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "dialog-relation":
            self.dismiss(event.value)

    def key_escape(self) -> None:
        self.dismiss(None)


class LinksList(Static, can_focus=True):
    """Список входящих и исходящих связей текущего узла."""

    BINDINGS = [
        Binding("o", "open_link", "Open", priority=True),
        Binding("a", "add_link", "Add link", priority=True),
        Binding("d", "delete_link", "Delete", priority=True),
        Binding("r", "edit_relation", "Edit relation", priority=True),
    ]

    CSS = """
    LinksList {
        height: 100%;
        overflow-y: auto;
    }

    #links-header {
        color: #e94560;
        text-style: bold;
        margin-bottom: 1;
    }

    #links-empty {
        color: #888;
        margin-top: 1;
    }

    .section-title {
        color: #4ECDC4;
        text-style: bold;
        margin-top: 1;
        margin-bottom: 0;
    }

    LinkRow {
        padding: 0 0 0 1;
    }

    LinkRow:hover {
        background: #0f3460;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._current_node: str | None = None
        self._out_links: list[tuple[str, dict]] = []
        self._in_links: list[tuple[str, dict]] = []

    def compose(self):
        yield Label("Links", id="links-header")
        yield Label("Select a node to see its links", id="links-empty")

    def on_focus(self) -> None:
        self.post_message(StatusMessage("o: open linked  a: add link  d: delete  r: edit relation", "info"))

    def show_links(self, node_id: str,
                   out_links: list[tuple[str, dict]],
                   in_links: list[tuple[str, dict]]) -> None:
        """Заполнить список связей для узла."""
        self._current_node = node_id
        self._out_links = out_links
        self._in_links = in_links

        # Полная очистка — удаляем всё, кроме links-header и links-empty (из compose)
        for child in list(self.children):
            if child.id in ("links-header", "links-empty"):
                continue
            child.remove()

        empty = self.query_one("#links-empty", Label)
        empty.display = False

        out_label = "  → Outgoing"
        out_count = f" ({len(out_links)})" if out_links else " (0)"
        self.mount(SectionLabel(f"{out_label}{out_count}", classes="section-title"))
        if out_links:
            for tgt, data in out_links:
                self.mount(LinkRow(tgt, data.get("relation", ""), "out"))
        else:
            # Без id — Textual сам управляет уникальностью
            self.mount(Label("  (none)"))

        in_label = "  ← Incoming"
        in_count = f" ({len(in_links)})" if in_links else " (0)"
        self.mount(SectionLabel(f"{in_label}{in_count}", classes="section-title"))
        if in_links:
            for src, data in in_links:
                self.mount(LinkRow(src, data.get("relation", ""), "in"))
        else:
            self.mount(Label("  (none)"))

    def _selected_link(self) -> LinkRow | None:
        """Найти выбранный (сфокусированный) LinkRow."""
        focused = self.app.focused
        if isinstance(focused, LinkRow):
            return focused
        # fallback: первый LinkRow
        for child in self.children:
            if isinstance(child, LinkRow):
                return child
        return None

    def action_open_link(self) -> None:
        """Открыть связанный узел."""
        if not self._current_node:
            return
        # Ищем LinkRow, на котором фокус
        link = self._selected_link()
        gm = self.app.graph_manager
        if link and gm.has_node(link.node_id):
            self.post_message(NodeSelected(link.node_id))

    def action_add_link(self) -> None:
        """Добавить новую связь."""
        if not self._current_node:
            return

        gm = self.app.graph_manager
        all_nodes = [n for n in gm.all_nodes() if n != self._current_node]

        def on_dialog(result):
            if result is None:
                return
            target = result["target"]
            relation = result["relation"]
            if target not in gm.G:
                self.post_message(StatusMessage(f"Node '{target}' not found", "error"))
                return
            if gm.has_edge(self._current_node, target):
                self.post_message(StatusMessage(f"Link already exists", "warning"))
                return

            attrs = {}
            if relation:
                attrs["relation"] = relation
            gm.add_edge(self._current_node, target, **attrs)

            # Обновить вид
            self.show_links(
                self._current_node,
                gm.neighbors_out(self._current_node),
                gm.neighbors_in(self._current_node),
            )
            self.post_message(StatusMessage(
                f"Link added: {self._current_node} → {target}", "success"))

        self.app.push_screen(AddLinkDialog(self._current_node, all_nodes), on_dialog)

    def action_delete_link(self) -> None:
        """Удалить выбранную связь."""
        if not self._current_node:
            return
        link = self._selected_link()
        if not link:
            return

        source = self._current_node if link.direction == "out" else link.node_id
        target = link.node_id if link.direction == "out" else self._current_node

        gm = self.app.graph_manager
        if not gm.has_edge(source, target):
            self.post_message(StatusMessage(f"Link not found", "error"))
            return

        def on_confirm(result):
            if not result:
                return
            gm.remove_edge(source, target)
            self.show_links(
                self._current_node,
                gm.neighbors_out(self._current_node),
                gm.neighbors_in(self._current_node),
            )
            self.post_message(StatusMessage(
                f"Link deleted: {source} → {target}", "success"))

        edge_data = gm.G.edges.get((source, target), {})
        self.app.push_screen(
            DeleteLinkConfirm(source, target, edge_data.get("relation", "")),
            on_confirm,
        )

    def action_edit_relation(self) -> None:
        """Редактировать relation выбранной связи."""
        if not self._current_node:
            return
        link = self._selected_link()
        if not link:
            return

        source = self._current_node if link.direction == "out" else link.node_id
        target = link.node_id if link.direction == "out" else self._current_node

        gm = self.app.graph_manager
        if not gm.has_edge(source, target):
            return

        old_rel = gm.G.edges[source, target].get("relation", "")

        def on_dialog(new_relation):
            if new_relation is None:
                return
            attrs = {}
            if new_relation:
                attrs["relation"] = new_relation
            gm.update_edge(source, target, **attrs)

            self.show_links(
                self._current_node,
                gm.neighbors_out(self._current_node),
                gm.neighbors_in(self._current_node),
            )
            self.post_message(StatusMessage(
                f"Relation updated: {source} → {target}", "success"))

        self.app.push_screen(
            EditRelationDialog(source, target, old_rel), on_dialog)

    def clear(self) -> None:
        """Очистить список."""
        self._current_node = None
        self._out_links = []
        self._in_links = []
        empty = self.query_one("#links-empty", Label)
        empty.display = True
        for child in list(self.children):
            if child.id in ("links-header", "links-empty"):
                continue
            child.remove()
