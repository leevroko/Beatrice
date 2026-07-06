"""Правый вьюпорт — список связей текущего узла."""

from textual.widgets import Static, Label
from textual.containers import Vertical


class SectionLabel(Static):
    """Заголовок секции (исходящие/входящие)."""

    def __init__(self, text: str) -> None:
        super().__init__(text)


class LinkRow(Static):
    """Одна строка связи."""

    def __init__(self, node_id: str, relation: str = "",
                 direction: str = "out") -> None:
        self.node_id = node_id
        self.relation = relation
        self.direction = direction
        arrow = "→" if direction == "out" else "←"
        rel_part = f" [{relation}]" if relation else ""
        super().__init__(f"  {arrow} {node_id}{rel_part}")


class LinksList(Static):
    """Список входящих и исходящих связей текущего узла."""

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

    def __init__(self) -> None:
        super().__init__()
        self._current_node: str | None = None

    def compose(self):
        yield Label("Links", id="links-header")
        yield Label("Select a node to see its links", id="links-empty")

    def show_links(self, node_id: str,
                   out_links: list[tuple[str, dict]],
                   in_links: list[tuple[str, dict]]) -> None:
        """Заполнить список связей для узла."""
        self._current_node = node_id

        empty = self.query_one("#links-empty", Label)
        empty.display = False

        # Удаляем старые секции
        for child in list(self.children):
            if child.id in ("links-header", "links-empty"):
                continue
            child.remove()

        # Исходящие
        self.mount(SectionLabel("  → Outgoing", classes="section-title"))
        if out_links:
            for tgt, data in out_links:
                self.mount(LinkRow(tgt, data.get("relation", ""), "out"))
        else:
            self.mount(Label("  (none)", id="links-empty"))

        # Входящие
        self.mount(SectionLabel("  ← Incoming", classes="section-title"))
        if in_links:
            for src, data in in_links:
                self.mount(LinkRow(src, data.get("relation", ""), "in"))
        else:
            self.mount(Label("  (none)", id="links-empty"))

    def clear(self) -> None:
        """Очистить список (например, после удаления узла)."""
        self._current_node = None
        empty = self.query_one("#links-empty", Label)
        empty.display = True
        for child in list(self.children):
            if child.id in ("links-header", "links-empty"):
                continue
            child.remove()
