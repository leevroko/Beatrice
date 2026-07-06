"""Центральный вьюпорт — форма просмотра/редактирования узла."""

from textual.widgets import Static, Input, TextArea, Label
from textual.containers import Vertical
from textual.keys import Keys
from textual.binding import Binding

from beatrice.tui.messages import NodeSaved, StatusMessage


def _color_block(hex_color: str) -> str:
    """Вернуть цветной блок для превью цвета."""
    if hex_color and hex_color.startswith("#"):
        return f"  [#{hex_color[1:]} on #{hex_color[1:]}](    )[/]"
    return ""


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

    .dirty-indicator {
        color: #FFEAA7;
        text-style: bold;
        margin-left: 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._current_node: str | None = None
        self._dirty: bool = False
        self._saved_attrs: dict = {}  # атрибуты на момент открытия

    def compose(self):
        yield Label("Node", id="form-header")
        yield Label("Select a node from the list", id="form-empty")

    def on_mount(self) -> None:
        pass

    def on_focus(self) -> None:
        """Показать подсказки при фокусе."""
        self.post_message(StatusMessage("Tab: next field  Ctrl+s: save", "info"))

    def on_input_changed(self, event: Input.Changed) -> None:
        """Любое изменение поля — помечаем как dirty."""
        self._mark_dirty()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Изменение TextArea — помечаем как dirty."""
        self._mark_dirty()

    def _mark_dirty(self) -> None:
        """Пометить форму как изменённую."""
        if self._current_node and not self._dirty:
            self._dirty = True
            header = self.query_one("#form-header", Label)
            header.update(f"Node ✎")

    def show_node(self, node_id: str, attrs: dict) -> None:
        """Заполнить форму данными узла. Сохраняет предыдущий узел."""
        # Сохранить предыдущий узел, если он был изменён
        if self._dirty and self._current_node:
            self._save_current_node()

        self._current_node = node_id
        self._saved_attrs = dict(attrs)
        self._dirty = False

        empty = self.query_one("#form-empty", Label)
        empty.display = False

        self._build_form(node_id, attrs)

    def _build_form(self, node_id: str, attrs: dict) -> None:
        """Построить или обновить поля формы."""
        header = self.query_one("#form-header", Label)
        header.update(f"Node")

        for child in list(self.children):
            if child.id in ("form-header", "form-empty"):
                continue
            if child.has_class("form-row"):
                child.remove()

        # ID (read-only)
        self.mount(
            Vertical(
                Label("ID", classes="form-label"),
                Input(value=node_id, id="node-id-input",
                      classes="form-input", disabled=True),
                classes="form-row",
            )
        )

        # Label
        self.mount(
            Vertical(
                Label("Label", classes="form-label"),
                Input(value=attrs.get("label", ""), placeholder="Display name",
                      id="node-label-input", classes="form-input"),
                classes="form-row",
            )
        )

        # Type
        self.mount(
            Vertical(
                Label("Type", classes="form-label"),
                Input(value=attrs.get("type", ""),
                      placeholder="e.g. брокер, сервис, БД",
                      id="node-type-input", classes="form-input"),
                classes="form-row",
            )
        )

        # Description
        self.mount(
            Vertical(
                Label("Description", classes="form-label"),
                TextArea(text=attrs.get("desc", ""), placeholder="Node description",
                         id="node-desc-input", classes="form-input"),
                classes="form-row",
            )
        )

        # Color
        color = attrs.get("color", "")
        self.mount(
            Vertical(
                Label(f"Color  {_color_block(color)}", classes="form-label",
                      id="form-color-label"),
                Input(value=color, placeholder="#FF0000",
                      id="node-color-input", classes="form-input"),
                classes="form-row",
            )
        )

        # Size
        size = str(attrs.get("size", "")) if attrs.get("size") else ""
        self.mount(
            Vertical(
                Label("Size", classes="form-label"),
                Input(value=size, placeholder="Node radius (pixels)",
                      id="node-size-input", classes="form-input", type="number"),
                classes="form-row",
            )
        )

    def _show_empty(self) -> None:
        self._current_node = None
        self._dirty = False
        empty = self.query_one("#form-empty", Label)
        empty.display = True
        header = self.query_one("#form-header", Label)
        header.update("Node")
        for child in list(self.children):
            if child.id in ("form-header", "form-empty"):
                continue
            child.remove()

    def get_form_values(self) -> dict:
        """Собрать текущие значения из полей формы. Только изменённые."""
        res = {}
        for child in self.walk_children():
            if isinstance(child, Input):
                if child.id == "node-label-input" and child.value != self._saved_attrs.get("label", ""):
                    res["label"] = child.value
                elif child.id == "node-type-input" and child.value != self._saved_attrs.get("type", ""):
                    res["type"] = child.value
                elif child.id == "node-color-input" and child.value != self._saved_attrs.get("color", ""):
                    res["color"] = child.value
                elif child.id == "node-size-input":
                    new_size = int(child.value) if child.value.isdigit() else None
                    old_size = self._saved_attrs.get("size")
                    if new_size != old_size:
                        res["size"] = new_size
            elif isinstance(child, TextArea) and child.id == "node-desc-input":
                if child.text != self._saved_attrs.get("desc", ""):
                    res["desc"] = child.text
        return res

    def _save_current_node(self) -> None:
        """Сохранить изменения текущего узла в GraphManager."""
        if not self._current_node:
            return
        values = self.get_form_values()
        if not values:
            self._dirty = False
            return

        gm = self.app.graph_manager
        gm.update_node(self._current_node, **values)
        # gm.save() — автосохранение уже в update_node через _mark_changed
        self._dirty = False
        header = self.query_one("#form-header", Label)
        header.update("Node")
        self.post_message(NodeSaved(self._current_node))
        self.post_message(StatusMessage(f"Saved: {self._current_node}", "success"))

    def action_cancel_edit(self) -> None:
        """Escape — отменить изменения и вернуть сохранённые значения."""
        if self._current_node and self._dirty:
            self._build_form(self._current_node, self._saved_attrs)
            self._dirty = False
            header = self.query_one("#form-header", Label)
            header.update("Node")
            self.post_message(StatusMessage("Edit cancelled", "info"))

    @property
    def current_node(self) -> str | None:
        return self._current_node

    @property
    def dirty(self) -> bool:
        return self._dirty
