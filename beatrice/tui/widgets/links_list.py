"""Правый вьюпорт — список связей текущего узла, добавление/удаление/редактирование."""

from textual.widgets import Static, Label, Input, ListView, ListItem
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.binding import Binding

from beatrice.tui.messages import NodeSelected, StatusMessage, GraphChanged


class NodeListItem(ListItem):
    """ListItem, хранящий node_id как атрибут."""

    def __init__(self, node_id: str, label_text: str | None = None, **kwargs) -> None:
        self.node_id = node_id
        display = label_text or node_id
        super().__init__(Label(display), **kwargs)


class LinkItem(ListItem):
    """Элемент списка связей — node_id + relation + направление."""

    def __init__(self, node_id: str, relation: str = "",
                 direction: str = "out") -> None:
        self.node_id = node_id
        self.direction = direction
        arrow = "→" if direction == "out" else "←"
        rel_part = f" [{relation}]" if relation else ""
        super().__init__(Label(f"  {arrow} {node_id}{rel_part}"))


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
    #dialog-title { color: #e94560; text-style: bold; margin-bottom: 1; }
    #dialog-search {
        background: #0f3460; border: solid #0f3460; color: #eee; margin-bottom: 1;
    }
    #dialog-search:focus { border: tall #e94560; }
    .dialog-input {
        background: #0f3460; border: solid #0f3460; color: #eee; margin-bottom: 1;
    }
    .dialog-input:focus { border: tall #e94560; }
    #dialog-list { height: 1fr; border: none; background: #0f3460; }
    ListItem { padding: 0 1; }
    ListItem:hover { background: #16213e; }
    ListItem.--highlight { background: #e94560; }
    #dialog-hint { color: #888; margin-top: 1; }
    """

    def __init__(self, source_node: str, all_nodes: list[str], node_labels: dict[str, str]) -> None:
        super().__init__()
        self.source_node = source_node
        self._all_nodes = all_nodes
        self._all_labels = node_labels
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
        lv = self.query_one("#dialog-list", ListView)
        lv.clear()
        if query:
            from rapidfuzz import fuzz
            scored = []
            for n in self._all_nodes:
                display = self._all_labels.get(n, n)
                score = max(
                    fuzz.partial_ratio(query.lower(), display.lower()),
                    fuzz.partial_ratio(query.lower(), n.lower()),
                )
                if score > 30:
                    scored.append((score, n))
            scored.sort(key=lambda x: -x[0])
            self._filtered = [n for _, n in scored]
        else:
            self._filtered = list(self._all_nodes)
        for n in self._filtered:
            display = self._all_labels.get(n, n)
            lv.append(NodeListItem(n, label_text=display))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "dialog-search":
            self._refresh_list(event.value)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, NodeListItem):
            self.query_one("#dialog-relation", Input).focus()

    def key_enter(self) -> None:
        self._submit()

    def key_escape(self) -> None:
        self.dismiss(None)

    def _submit(self) -> None:
        lv = self.query_one("#dialog-list", ListView)
        target = ""
        if lv.index is not None and lv.index < len(lv.children):
            selected = lv.children[lv.index]
            if isinstance(selected, NodeListItem):
                target = selected.node_id
        if not target and len(lv.children) > 0:
            first = lv.children[0]
            if isinstance(first, NodeListItem):
                target = first.node_id
        relation = self.query_one("#dialog-relation", Input).value.strip()
        if not target:
            self.query_one("#dialog-hint", Label).update("[red]No target node selected![/]")
            return
        self.dismiss({"target": target, "relation": relation})


class DeleteLinkConfirm(ModalScreen):
    """Подтверждение удаления связи."""

    CSS = """
    DeleteLinkConfirm { align: center middle; }
    #dialog { width: 40; height: auto; background: #16213e; border: thick #e94560; padding: 2; }
    #dialog-title { color: #e94560; text-style: bold; margin-bottom: 1; }
    #dialog-hint { color: #888; margin-top: 1; }
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
    EditRelationDialog { align: center middle; }
    #dialog { width: 40; height: auto; background: #16213e; border: thick #e94560; padding: 2; }
    #dialog-title { color: #e94560; text-style: bold; margin-bottom: 1; }
    .dialog-input { background: #0f3460; border: solid #0f3460; color: #eee; margin-bottom: 1; }
    .dialog-input:focus { border: tall #e94560; }
    #dialog-hint { color: #888; margin-top: 1; }
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
    """Правый вьюпорт: два ListView — Outgoing и Incoming."""

    BINDINGS = [
        Binding("o", "open_link", "Open", priority=True),
        Binding("a", "add_link", "Add link", priority=True),
        Binding("d", "delete_link", "Delete", priority=True),
        Binding("r", "edit_relation", "Edit relation", priority=True),
    ]

    CSS = """
    LinksList { height: 100%; overflow-y: auto; }
    #links-header { color: #e94560; text-style: bold; margin-bottom: 1; }
    #links-empty { color: #888; margin-top: 1; }
    .section-title { color: #4ECDC4; text-style: bold; margin-top: 1; margin-bottom: 0; padding: 0; }
    .links-list { height: 1fr; border: none; background: #16213e; min-height: 1; }
    ListView { background: #16213e; border: none; }
    LinkItem { padding: 0 1; }
    LinkItem:hover { background: #0f3460; }
    LinkItem.--highlight { background: #e94560; }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._current_node: str | None = None

    def compose(self):
        yield Label("Links", id="links-header")
        yield Label("Select a node to see its links", id="links-empty")
        yield Label("", id="out-title", classes="section-title")
        yield ListView(id="list-out", classes="links-list")
        yield Label("", id="in-title", classes="section-title")
        yield ListView(id="list-in", classes="links-list")

    def on_focus(self) -> None:
        self.post_message(StatusMessage(
            "j/k: nav  o: open linked  a: add  d: delete  r: edit", "info"))

    def show_links(self, node_id: str,
                   out_links: list[tuple[str, dict]],
                   in_links: list[tuple[str, dict]]) -> None:
        self._current_node = node_id
        self.query_one("#links-empty", Label).display = False

        out_title = self.query_one("#out-title", Label)
        out_count = f" ({len(out_links)})" if out_links else " (0)"
        out_title.update(f"  → Outgoing{out_count}")

        out_list = self.query_one("#list-out", ListView)
        out_list.clear()
        for tgt, data in out_links:
            out_list.append(LinkItem(tgt, data.get("relation", ""), "out"))
        if out_links:
            out_list.index = 0

        in_title = self.query_one("#in-title", Label)
        in_count = f" ({len(in_links)})" if in_links else " (0)"
        in_title.update(f"  ← Incoming{in_count}")

        in_list = self.query_one("#list-in", ListView)
        in_list.clear()
        for src, data in in_links:
            in_list.append(LinkItem(src, data.get("relation", ""), "in"))
        if in_links:
            in_list.index = 0

    def _active_list(self) -> ListView | None:
        f = self.app.focused
        if f and f.id == "list-out":
            return self.query_one("#list-out", ListView)
        if f and f.id == "list-in":
            return self.query_one("#list-in", ListView)
        out = self.query_one("#list-out", ListView)
        if len(out.children) > 0:
            return out
        in_lv = self.query_one("#list-in", ListView)
        return in_lv if len(in_lv.children) > 0 else None

    def _selected_link(self) -> LinkItem | None:
        lv = self._active_list()
        if lv is None or lv.index is None or lv.index >= len(lv.children):
            return None
        item = lv.children[lv.index]
        return item if isinstance(item, LinkItem) else None

    def action_open_link(self) -> None:
        link = self._selected_link()
        if link:
            self.post_message(NodeSelected(link.node_id))

    def action_add_link(self) -> None:
        source_node = self._current_node
        if not source_node:
            return
        gm = self.app.graph_manager
        all_nodes = [n for n in gm.all_nodes() if n != source_node]

        def on_dialog(result):
            if result is None:
                return
            target = result["target"]
            relation = result["relation"]
            if not gm.has_node(source_node) or not gm.has_node(target):
                self.post_message(StatusMessage("Node not found", "error"))
                return
            if gm.has_edge(source_node, target):
                self.post_message(StatusMessage("Link exists", "warning"))
                return
            attrs = {}
            if relation:
                attrs["relation"] = relation
            gm.add_edge(source_node, target, **attrs)
            self.show_links(source_node, gm.neighbors_out(source_node),
                            gm.neighbors_in(source_node))
            self.post_message(GraphChanged())
            self.post_message(StatusMessage("Link added", "success"))

        self.app.push_screen(AddLinkDialog(source_node, all_nodes, gm.node_labels()), on_dialog)

    def action_delete_link(self) -> None:
        link = self._selected_link()
        if not link or not self._current_node:
            return
        source = self._current_node if link.direction == "out" else link.node_id
        target = link.node_id if link.direction == "out" else self._current_node
        gm = self.app.graph_manager
        if not gm.has_edge(source, target):
            return

        def on_confirm(ok):
            if not ok:
                return
            gm.remove_edge(source, target)
            self.show_links(self._current_node,
                            gm.neighbors_out(self._current_node),
                            gm.neighbors_in(self._current_node))
            self.post_message(GraphChanged())
            self.post_message(StatusMessage("Link deleted", "success"))

        ed = gm.G.edges[source, target].get("relation", "")
        self.app.push_screen(DeleteLinkConfirm(source, target, ed), on_confirm)

    def action_edit_relation(self) -> None:
        link = self._selected_link()
        if not link or not self._current_node:
            return
        source = self._current_node if link.direction == "out" else link.node_id
        target = link.node_id if link.direction == "out" else self._current_node
        gm = self.app.graph_manager
        if not gm.has_edge(source, target):
            return
        old_rel = gm.G.edges[source, target].get("relation", "")

        def on_dialog(new_rel):
            if new_rel is None:
                return
            attrs = {}
            if new_rel:
                attrs["relation"] = new_rel
            gm.update_edge(source, target, **attrs)
            self.show_links(self._current_node,
                            gm.neighbors_out(self._current_node),
                            gm.neighbors_in(self._current_node))
            self.post_message(GraphChanged())
            self.post_message(StatusMessage("Relation updated", "success"))

        self.app.push_screen(EditRelationDialog(source, target, old_rel), on_dialog)

    def clear(self) -> None:
        self._current_node = None
        self.query_one("#links-empty", Label).display = True
        self.query_one("#list-out", ListView).clear()
        self.query_one("#list-in", ListView).clear()
