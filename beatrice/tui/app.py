"""Beatrice TUI — главное приложение."""

from pathlib import Path
from textual.app import App
from textual.screen import Screen
from textual.widgets import Header, Footer, Label
from textual.containers import Horizontal

from beatrice.tui.graph_manager import GraphManager
from beatrice.tui.messages import (
    NodeSelected, NodeSaved, NodeAdded, NodeDeleted,
    LinkAdded, LinkDeleted, FilterChanged, StatusMessage,
)
from beatrice.tui.widgets.nodes_list import NodesList
from beatrice.tui.widgets.node_form import NodeForm
from beatrice.tui.widgets.links_list import LinksList


class LoadingScreen(Screen):
    """Экран загрузки — пока граф читается с диска."""

    def compose(self):
        yield Label("Загрузка графа...", id="loading-label")


class MainScreen(Screen):
    """Главный экран с тремя вьюпортами."""

    CSS = """
    #panels-container {
        height: 1fr;
    }

    #panel-left {
        width: 30%;
        min-width: 25;
        border-right: solid #0f3460;
        background: #16213e;
    }

    #panel-center {
        width: 40%;
        min-width: 30;
        background: #1a1a2e;
    }

    #panel-right {
        width: 30%;
        min-width: 25;
        border-left: solid #0f3460;
        background: #16213e;
    }

    #status-bar {
        dock: top;
        height: 1;
        background: #0f3460;
        color: #eee;
        padding: 0 1;
    }

    #help-bar {
        dock: bottom;
        height: 1;
        background: #0f3460;
        color: #888;
        padding: 0 1;
    }
    """

    def compose(self):
        yield Label(id="status-bar")
        with Horizontal(id="panels-container"):
            yield NodesList(id="panel-left")
            yield NodeForm(id="panel-center")
            yield LinksList(id="panel-right")
        yield Label(id="help-bar")

    def on_mount(self) -> None:
        """После монтирования — загрузить данные в виджеты."""
        gm = self.app.graph_manager  # type: ignore[attr-defined]

        # Загрузить список узлов
        nodes_list = self.query_one("#panel-left", NodesList)
        nodes_list.load_from_graph_manager(gm)

        # Выбрать первый узел по умолчанию
        all_nodes = gm.all_nodes()
        if all_nodes:
            self._select_node(all_nodes[0])

        self._update_status_bar()

    def on_node_selected(self, message: NodeSelected) -> None:
        """Выбран узел — обновить форму и связи."""
        self._select_node(message.node_id)

    def _select_node(self, node_id: str) -> None:
        """Показать узел в центре и справа."""
        gm = self.app.graph_manager  # type: ignore[attr-defined]
        if not gm.has_node(node_id):
            return

        form = self.query_one("#panel-center", NodeForm)
        form.show_node(node_id, gm.node_attrs(node_id))

        links = self.query_one("#panel-right", LinksList)
        links.show_links(
            node_id,
            gm.neighbors_out(node_id),
            gm.neighbors_in(node_id),
        )

    def _update_status_bar(self) -> None:
        """Обновить верхнюю строку статуса."""
        gm = self.app.graph_manager  # type: ignore[attr-defined]
        path = Path(gm.path).name if gm.path else "(none)"
        bar = self.query_one("#status-bar", Label)
        dirty_mark = " ✎" if gm.dirty else ""
        bar.update(
            f"📂 {path}{dirty_mark}  │  "
            f"Nodes: {gm.node_count}  │  "
            f"Edges: {gm.edge_count}  │  "
            f"Orphans: {gm.orphan_count}"
        )


class BeatriceApp(App):
    """Главное приложение TUI."""

    CSS = """
    Screen {
        background: #1a1a2e;
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
                f"{gm.node_count} nodes · {gm.edge_count} edges · "
                f"{gm.orphan_count} orphans"
            )
        except Exception as e:
            self.title = "Beatrice — Error"
            self.sub_title = str(e)
            self.push_screen(MainScreen())
            return

        self.push_screen(MainScreen())


def run_tui(graph_path: str) -> None:
    """Запустить TUI с указанным графом."""
    app = BeatriceApp(graph_path)
    app.run()
