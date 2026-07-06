"""Палитра команд — список с фильтрацией, открывается по `:`."""

from textual.widgets import Static, Input, ListView, ListItem, Label
from textual.containers import Vertical
from textual.screen import ModalScreen
from rapidfuzz import fuzz


class CommandItem(ListItem):
    """Одна команда в списке."""

    def __init__(self, name: str, description: str, handler: str, **kwargs) -> None:
        self.command_name = name
        self.handler_key = handler
        super().__init__(
            Label(f"{name:<25s} {description}", classes="command-row")
        )


COMMANDS = [
    ("q", "Quit", "quit"),
    ("w", "Save graph", "save"),
    ("wq", "Save and quit", "save_quit"),
    ("e <path>", "Open another graph", "open_graph"),
    ("undo", "Undo last change", "undo"),
    ("redo", "Redo undone change", "redo"),
    ("add-node <id>", "Quick add a node", "add_node"),
    ("rm-node <id>", "Delete a node by ID", "rm_node"),
    ("render", "Generate HTML visualization", "render"),
    ("theme dark", "Switch to dark theme", "theme_dark"),
    ("theme light", "Switch to light theme", "theme_light"),
    ("help", "Show help", "help"),
    ("filter <query>", "Filter nodes by string", "filter"),
    ("filter-orphans any", "Show all nodes", "filter_orphans_any"),
    ("filter-orphans yes", "Show orphans only", "filter_orphans_yes"),
    ("filter-orphans no", "Show non-orphans only", "filter_orphans_no"),
]


class CommandPalette(ModalScreen):
    """Палитра команд с фильтрацией."""

    CSS = """
    CommandPalette {
        align: center middle;
    }

    #dialog {
        width: 60;
        height: 24;
        background: #16213e;
        border: thick #e94560;
        padding: 1;
    }

    #palette-title {
        color: #e94560;
        text-style: bold;
        margin-bottom: 1;
    }

    #palette-input {
        background: #0f3460;
        border: solid #0f3460;
        color: #eee;
        margin-bottom: 1;
    }

    #palette-input:focus {
        border: tall #e94560;
    }

    #palette-list {
        height: 1fr;
        border: none;
        background: #16213e;
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

    .command-row {
        color: #eee;
    }

    #palette-hint {
        color: #888;
        margin-top: 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._history: list[str] = []
        self._history_index = -1

    def compose(self):
        yield Vertical(
            Label("Commands", id="palette-title"),
            Input(placeholder="Type to filter...", id="palette-input"),
            ListView(id="palette-list"),
            Label("Enter: execute  Escape: close", id="palette-hint"),
            id="dialog",
        )

    def on_mount(self) -> None:
        self._refresh_list("")
        self.query_one("#palette-input", Input).focus()

    def _refresh_list(self, query: str) -> None:
        """Отфильтровать список команд."""
        lv = self.query_one("#palette-list", ListView)
        lv.clear()

        if query.startswith(":") and len(query) > 1:
            query = query[1:]

        scored = []
        for name, desc, handler in COMMANDS:
            full = f"{name} {desc}"
            score = max(
                fuzz.partial_ratio(query.lower(), name.lower()),
                fuzz.partial_ratio(query.lower(), desc.lower()),
            )
            if score > 30:
                scored.append((score, name, desc, handler))
        scored.sort(key=lambda x: -x[0])

        for _, name, desc, handler in scored:
            lv.append(CommandItem(name, desc, handler))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "palette-input":
            self._refresh_list(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter — выполнить первую команду из списка."""
        if event.input.id == "palette-input":
            lv = self.query_one("#palette-list", ListView)
            if len(lv.children) > 0:
                first = lv.children[0]
                if isinstance(first, CommandItem):
                    self._execute(first)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, CommandItem):
            self._execute(item)

    def _execute(self, item: CommandItem) -> None:
        """Выполнить команду и закрыть палитру."""
        self.dismiss(item.handler_key)

    def key_escape(self) -> None:
        self.dismiss(None)
