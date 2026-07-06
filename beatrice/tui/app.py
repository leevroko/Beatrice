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


def _panel_id_for(panel_index: int) -> str:
    return ["panel-left", "panel-center", "panel-right"][panel_index]


class MainScreen(Screen):
    """Главный экран с тремя вьюпортами и навигацией."""

    BINDINGS = [
        ("h", "focus_left", "Left panel"),
        ("l", "focus_right", "Right panel"),
        ("q", "quit", "Quit"),
        ("?", "show_help", "Help"),
        ("ctrl+s", "save", "Save"),
        ("r", "render", "Render HTML"),
        (":", "command_palette", "Commands"),
    ]

    CSS = """
    #panels-container {
        height: 1fr;
    }

    .panel {
        border: none;
    }

    .panel-active {
        border: none;
    }

    #panel-left {
        width: 30%;
        min-width: 25;
        border-right: solid #0f3460;
        background: #16213e;
    }

    #panel-left.panel-active {
        border-right: solid #e94560;
    }

    #panel-center {
        width: 40%;
        min-width: 30;
        background: #1a1a2e;
    }

    #panel-center.panel-active {
        border-left: solid #e94560;
        border-right: solid #e94560;
    }

    #panel-right {
        width: 30%;
        min-width: 25;
        border-left: solid #0f3460;
        background: #16213e;
    }

    #panel-right.panel-active {
        border-left: solid #e94560;
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

    def __init__(self):
        super().__init__()
        self._active_panel = 0  # 0=left, 1=center, 2=right

    def compose(self):
        yield Label(id="status-bar")
        with Horizontal(id="panels-container"):
            yield NodesList(id="panel-left", classes="panel")
            yield NodeForm(id="panel-center", classes="panel")
            yield LinksList(id="panel-right", classes="panel")
        yield Label(id="help-bar")

    def on_mount(self) -> None:
        gm = self.app.graph_manager
        if hasattr(gm, 'load'):
            pass

        nodes_list = self.query_one("#panel-left", NodesList)
        nodes_list.load_from_graph_manager(gm)

        all_nodes = gm.all_nodes()
        if all_nodes:
            self._select_node(all_nodes[0])

        self._update_status_bar()
        self._update_help_bar()
        self._focus_panel(0)

    def _focus_panel(self, index: int) -> None:
        """Переключить фокус на указанный вьюпорт."""
        self._active_panel = index
        for i in range(3):
            panel = self.query_one(f"#{_panel_id_for(i)}")
            panel.remove_class("panel-active")
        active = self.query_one(f"#{_panel_id_for(index)}")
        active.add_class("panel-active")
        active.focus()
        self._update_help_bar()

    def action_focus_left(self) -> None:
        targets = {0: 2, 1: 0, 2: 1}
        self._focus_panel(targets[self._active_panel])

    def action_focus_right(self) -> None:
        targets = {0: 1, 1: 2, 2: 0}
        self._focus_panel(targets[self._active_panel])

    def action_quit(self) -> None:
        gm = self.app.graph_manager
        if gm.dirty:
            self.post_message(StatusMessage("Unsaved changes! Save with Ctrl+s or :w", "warning"))
        else:
            self.app.exit()

    def action_save(self) -> None:
        """Сохранить: сначала форму, потом граф на диск."""
        # Сохранить форму текущего узла
        form = self.query_one("#panel-center", NodeForm)
        if form.dirty:
            form._save_current_node()

        gm = self.app.graph_manager
        try:
            gm.save()
            self._update_status_bar()
            self.post_message(StatusMessage(f"Saved: {Path(gm.path).name}", "success"))
        except Exception as e:
            self.post_message(StatusMessage(f"Save error: {e}", "error"))

    def action_show_help(self) -> None:
        self.post_message(StatusMessage(
            "hjkl: nav  o: open  s: search  x: orphans  ?: help  :: commands  Ctrl+s: save  q: quit",
            "info"
        ))

    def action_render(self) -> None:
        gm = self.app.graph_manager
        if gm.path:
            output = Path(gm.path).with_suffix(".html")
            self.post_message(StatusMessage(f"Render: not yet implemented", "warning"))

    def action_command_palette(self) -> None:
        self.post_message(StatusMessage("Command palette: next iteration", "warning"))

    def _update_status_bar(self) -> None:
        gm = self.app.graph_manager
        path = Path(gm.path).name if gm.path else "(none)"
        bar = self.query_one("#status-bar", Label)
        dirty_mark = " ✎" if gm.dirty else ""
        bar.update(
            f"📂 {path}{dirty_mark}  │  "
            f"Nodes: {gm.node_count}  │  "
            f"Edges: {gm.edge_count}  │  "
            f"Orphans: {gm.orphan_count}"
        )

    def _update_help_bar(self) -> None:
        """Обновить контекстную нижнюю строку."""
        names = {0: "NODES", 1: "FORM", 2: "LINKS"}
        helps = {
            0: "j/k: nav  o: open  s: search  x: orphans  a: add  d: delete",
            1: "Tab: next field  Ctrl+s: save",
            2: "o: open linked  a: add link  d: delete",
        }
        bar = self.query_one("#help-bar", Label)
        panel_name = names.get(self._active_panel, "?")
        help_text = helps.get(self._active_panel, "")
        bar.update(f"[bold]{panel_name}[/bold]  │  {help_text}  │  :: commands")

    # ────── Message handlers ──────

    def on_node_selected(self, message: NodeSelected) -> None:
        self._select_node(message.node_id)
        self._focus_panel(1)  # фокус на форму

    def on_status_message(self, message: StatusMessage) -> None:
        bar = self.query_one("#help-bar", Label)
        severity_colors = {
            "info": "#888",
            "success": "#4ECDC4",
            "error": "#e94560",
            "warning": "#FFEAA7",
        }
        color = severity_colors.get(message.severity, "#888")
        bar.update(f"[{color}]{message.text}[/]")
        self.set_timer(5.0, self._update_help_bar)

    def _select_node(self, node_id: str) -> None:
        gm = self.app.graph_manager
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


class BeatriceApp(App):
    """Главное приложение TUI."""

    CSS = """
    Screen {
        background: #1a1a2e;
    }
    """

    def __init__(self, graph_path: str):
        super().__init__()
        self.graph_path = graph_path
        self.graph_manager = GraphManager()

    def on_mount(self) -> None:
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


def run_tui(graph_path: str) -> None:
    app = BeatriceApp(graph_path)
    app.run()
