"""Общие диалоги: подтверждение, ввод."""

from textual.screen import ModalScreen
from textual.widgets import Input, Label
from textual.containers import Vertical


class ConfirmDialog(ModalScreen):
    """Универсальный диалог подтверждения."""

    CSS = """
    ConfirmDialog {
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

    def __init__(self, title: str, message: str) -> None:
        super().__init__()
        self._title = title
        self._message = message

    def compose(self):
        yield Vertical(
            Label(self._title, id="dialog-title"),
            Label(self._message),
            Label("y: confirm  Escape: cancel", id="dialog-hint"),
            id="dialog",
        )

    def key_y(self) -> None:
        self.dismiss(True)

    def key_escape(self) -> None:
        self.dismiss(None)


class AddNodeDialog(ModalScreen):
    """Диалог добавления нового узла."""

    CSS = """
    AddNodeDialog {
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

    def __init__(self, default_id: str = "node1", **kwargs) -> None:
        super().__init__(**kwargs)
        self._default_id = default_id

    def compose(self):
        yield Vertical(
            Label("Add Node", id="dialog-title"),
            Input(value=self._default_id, placeholder="Node ID", id="dialog-id", classes="dialog-input"),
            Input(placeholder="Label (optional)", id="dialog-label", classes="dialog-input"),
            Input(placeholder="Type (optional)", id="dialog-type", classes="dialog-input"),
            Label("Enter: add  Escape: cancel", id="dialog-hint"),
            id="dialog",
        )

    def on_mount(self) -> None:
        self.query_one("#dialog-id", Input).focus()

    def key_escape(self) -> None:
        self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id in ("dialog-label", "dialog-type"):
            self._submit()

    def _submit(self) -> None:
        nid = self.query_one("#dialog-id", Input).value.strip()
        if not nid:
            self.query_one("#dialog-hint", Label).update("[red]Node ID cannot be empty![/]")
            return
        label = self.query_one("#dialog-label", Input).value.strip()
        type_str = self.query_one("#dialog-type", Input).value.strip()
        result = {"id": nid}
        if label:
            result["label"] = label
        if type_str:
            result["type"] = type_str
        self.dismiss(result)


class InputDialog(ModalScreen):
    """Простой диалог для ввода одного значения."""

    CSS = """
    InputDialog {
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

    def __init__(self, title: str, placeholder: str = "") -> None:
        super().__init__()
        self._title = title
        self._placeholder = placeholder

    def compose(self):
        yield Vertical(
            Label(self._title, id="dialog-title"),
            Input(placeholder=self._placeholder, id="dialog-input", classes="dialog-input"),
            Label("Enter: confirm  Escape: cancel", id="dialog-hint"),
            id="dialog",
        )

    def on_mount(self) -> None:
        self.query_one("#dialog-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def key_escape(self) -> None:
        self.dismiss(None)
