"""Help screen — таблица всех хоткеев."""

from textual.screen import ModalScreen
from textual.widgets import Static, Label


class HelpScreen(ModalScreen):
    """Справка по хоткеям."""

    CSS = """
    HelpScreen {
        align: center middle;
    }

    #dialog {
        width: 60;
        height: 30;
        background: #16213e;
        border: thick #e94560;
        padding: 1 2;
        overflow-y: auto;
    }

    #help-title {
        color: #e94560;
        text-style: bold;
        text-align: center;
        margin-bottom: 1;
    }

    .section-title {
        color: #4ECDC4;
        text-style: bold;
        margin-top: 1;
    }

    .help-row {
        color: #eee;
        margin-left: 1;
    }

    .help-key {
        color: #FFEAA7;
    }

    #help-footer {
        color: #888;
        text-align: center;
        margin-top: 1;
    }
    """

    def compose(self):
        yield Static(
            "[bold #e94560]Help — Keyboard Shortcuts[/]\n\n"

            "[bold #4ECDC4]Global[/]\n"
            "  [:command_palette]Commands[/]\n"
            "  [bold #FFEAA7]q[/]    Quit\n"
            "  [bold #FFEAA7]Ctrl+s[/] Save\n"
            "  [bold #FFEAA7]?[/]    This help\n"
            "  [bold #FFEAA7]r[/]    Render HTML\n"
            "  [bold #FFEAA7]h/l[/]  Switch panels left/right\n\n"

            "[bold #4ECDC4]Nodes List (left panel)[/]\n"
            "  [bold #FFEAA7]j/k[/]  Navigate up/down\n"
            "  [bold #FFEAA7]g/G[/]  First/last\n"
            "  [bold #FFEAA7]o[/]    Open selected node\n"
            "  [bold #FFEAA7]s[/]    Focus search\n"
            "  [bold #FFEAA7]Escape[/] Clear search\n"
            "  [bold #FFEAA7]x[/]    Cycle orphan filter\n"
            "  [bold #FFEAA7]a[/]    Add node\n"
            "  [bold #FFEAA7]d[/]    Delete node\n\n"

            "[bold #4ECDC4]Node Form (center panel)[/]\n"
            "  [bold #FFEAA7]Tab[/]        Next field\n"
            "  [bold #FFEAA7]Shift+Tab[/]  Prev field\n"
            "  [bold #FFEAA7]Escape[/]     Cancel edits\n\n"

            "[bold #4ECDC4]Links (right panel)[/]\n"
            "  [bold #FFEAA7]o[/]  Open linked node\n"
            "  [bold #FFEAA7]a[/]  Add link\n"
            "  [bold #FFEAA7]d[/]  Delete link\n"
            "  [bold #FFEAA7]r[/]  Edit relation\n\n"

            "[bold #4ECDC4]Command Palette[/]\n"
            "  [bold #FFEAA7]:q[/]         Quit\n"
            "  [bold #FFEAA7]:w[/]         Save\n"
            "  [bold #FFEAA7]:wq[/]        Save and quit\n"
            "  [bold #FFEAA7]:undo[/]      Undo\n"
            "  [bold #FFEAA7]:redo[/]      Redo\n"
            "  [bold #FFEAA7]:render[/]    Render HTML\n"
            "  [bold #FFEAA7]:theme[/]     Switch theme\n\n"

            "[dim]Escape to close[/]",
            id="help-content",
        )

    def key_escape(self) -> None:
        self.app.pop_screen()
