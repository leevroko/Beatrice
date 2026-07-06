"""Beatrice TUI — главное приложение."""

from pathlib import Path
from textual.app import App
from textual.screen import Screen
from textual.widgets import Header, Footer, Label, Static
from textual.containers import Horizontal

from beatrice.tui.graph_manager import GraphManager


class LoadingScreen(Screen):
    """Экран загрузки — пока граф читается с диска."""

    def compose(self):
        yield Label("Загрузка графа...", id="loading-label")


class MainScreen(Screen):
    """Главный экран с тремя вьюпортами (пока пустыми)."""

    def compose(self):
        yield Header(show_clock=False)
        with Horizontal():
            yield Static(id="panel-left", classes="panel")
            yield Static(id="panel-center", classes="panel")
            yield Static(id="panel-right", classes="panel")
        yield Footer()

    def on_mount(self) -> None:
        """После монтирования — показать информацию о загруженном графе."""
        gm = self.app.graph_manager  # type: ignore[attr-defined]
        panel_left = self.query_one("#panel-left", Static)
        panel_left.update(
            f"[bold]Nodes[/bold]\n\n"
            + "\n".join(gm.all_nodes())
        )
        panel_center = self.query_one("#panel-center", Static)
        panel_center.update(
            f"[bold]Node Details[/bold]\n"
            f"[dim]Select a node from the list[/dim]"
        )
        panel_right = self.query_one("#panel-right", Static)
        panel_right.update(
            f"[bold]Links[/bold]\n"
            f"[dim]Select a node to see its links[/dim]"
        )


class BeatriceApp(App):
    """Главное приложение TUI."""

    CSS = """
    Screen {
        background: #1a1a2e;
    }

    .panel {
        border: solid #0f3460;
        padding: 1;
        height: 100%;
    }

    #panel-left {
        width: 30%;
        background: #16213e;
    }

    #panel-center {
        width: 40%;
        background: #1a1a2e;
    }

    #panel-right {
        width: 30%;
        background: #16213e;
    }

    Header {
        background: #0f3460;
        color: #eee;
    }

    Footer {
        background: #0f3460;
        color: #aaa;
    }
    """

    def __init__(self, graph_path: str):
        super().__init__()
        self.graph_path = graph_path
        self.graph_manager = GraphManager()

    def on_mount(self) -> None:
        """Загрузить граф и перейти на главный экран."""
        try:
            self.graph_manager.load(self.graph_path)
            gm = self.graph_manager
            self.title = f"Beatrice — {Path(self.graph_path).name}"
            self.sub_title = (
                f"{gm.node_count} узлов · {gm.edge_count} рёбер · "
                f"{gm.orphan_count} сирот"
            )
        except Exception as e:
            self.title = "Beatrice — Ошибка"
            self.sub_title = f"Не удалось загрузить граф: {e}"
            self.push_screen(MainScreen())
            return

        self.push_screen(MainScreen())


def run_tui(graph_path: str) -> None:
    """Запустить TUI с указанным графом."""
    app = BeatriceApp(graph_path)
    app.run()
