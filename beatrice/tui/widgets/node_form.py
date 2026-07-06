"""Центральный вьюпорт — форма просмотра/редактирования узла."""

from textual.widgets import Static, Input, TextArea, Label
from textual.containers import Vertical, Horizontal


class NodeForm(Static):
    """Форма просмотра и редактирования атрибутов узла."""

    CSS = """
    NodeForm {
        height: 100%;
        overflow-y: auto;
    }

    #form-header {
        color: #e94560;
        text-style: bold;
        margin-bottom: 1;
    }

    .form-row {
        margin-bottom: 1;
    }

    .form-label {
        color: #aaa;
        text-style: bold;
        margin-bottom: 0;
        padding-left: 0;
    }

    .form-input {
        background: #16213e;
        border: solid #0f3460;
        color: #eee;
        padding: 0 1;
    }

    .form-input:focus {
        border: tall #e94560;
    }

    #node-id-input {
        background: #111;
        color: #888;
    }

    #node-desc-input {
        height: 5;
    }

    #form-empty {
        color: #888;
        text-align: center;
        margin-top: 6;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._current_node: str | None = None

    def compose(self):
        yield Label("Node", id="form-header")
        yield Label("Select a node from the list", id="form-empty")

    def on_mount(self) -> None:
        self._show_empty()

    def show_node(self, node_id: str, attrs: dict) -> None:
        """Заполнить форму данными узла."""
        self._current_node = node_id

        # Удаляем пустой лейбл
        empty = self.query_one("#form-empty", Label)
        empty.display = False

        # Строим форму
        self._build_form(node_id, attrs)

    def _build_form(self, node_id: str, attrs: dict) -> None:
        """Построить или обновить поля формы."""
        # Удаляем старые поля (кроме header и empty)
        for child in list(self.children):
            if child.id in ("form-header", "form-empty"):
                continue
            if child.has_class("form-row"):
                child.remove()

        # ID (read-only)
        self.mount(
            Vertical(
                Label("ID", classes="form-label"),
                Input(
                    value=node_id,
                    id="node-id-input",
                    classes="form-input",
                    disabled=True,
                ),
                classes="form-row",
            )
        )

        # Label
        self.mount(
            Vertical(
                Label("Label", classes="form-label"),
                Input(
                    value=attrs.get("label", ""),
                    placeholder="Display name",
                    id="node-label-input",
                    classes="form-input",
                ),
                classes="form-row",
            )
        )

        # Type
        self.mount(
            Vertical(
                Label("Type", classes="form-label"),
                Input(
                    value=attrs.get("type", ""),
                    placeholder="e.g. брокер, сервис, БД",
                    id="node-type-input",
                    classes="form-input",
                ),
                classes="form-row",
            )
        )

        # Description
        self.mount(
            Vertical(
                Label("Description", classes="form-label"),
                TextArea(
                    text=attrs.get("desc", ""),
                    placeholder="Node description",
                    id="node-desc-input",
                    classes="form-input",
                ),
                classes="form-row",
            )
        )

        # Color
        color = attrs.get("color", "")
        self.mount(
            Vertical(
                Label(f"Color  [{"█" if color else "—"}]{'[/]' if color else ''}",
                      classes="form-label",
                      id="form-color-label"),
                Input(
                    value=color,
                    placeholder="#FF0000",
                    id="node-color-input",
                    classes="form-input",
                ),
                classes="form-row",
            )
        )

        # Size
        size = str(attrs.get("size", ""))
        self.mount(
            Vertical(
                Label("Size", classes="form-label"),
                Input(
                    value=size,
                    placeholder="Node radius (pixels)",
                    id="node-size-input",
                    classes="form-input",
                    type="number",
                ),
                classes="form-row",
            )
        )

    def _show_empty(self) -> None:
        """Показать пустое состояние."""
        self._current_node = None
        empty = self.query_one("#form-empty", Label)
        empty.display = True
        for child in list(self.children):
            if child.id in ("form-header", "form-empty"):
                continue
            child.remove()

    def get_form_values(self) -> dict:
        """Собрать текущие значения из полей формы."""
        res = {}
        for child in self.walk_children(with_self=False):
            if isinstance(child, Input) and child.id == "node-label-input":
                res["label"] = child.value
            elif isinstance(child, Input) and child.id == "node-type-input":
                res["type"] = child.value
            elif isinstance(child, TextArea) and child.id == "node-desc-input":
                res["desc"] = child.text
            elif isinstance(child, Input) and child.id == "node-color-input":
                res["color"] = child.value
            elif isinstance(child, Input) and child.id == "node-size-input":
                res["size"] = int(child.value) if child.value.isdigit() else None
        return {k: v for k, v in res.items() if v is not None and v != ""}

    @property
    def current_node(self) -> str | None:
        return self._current_node
