"""Beatrice TUI — главное приложение."""

from pathlib import Path
from textual.app import App
from textual.screen import Screen
from textual.widgets import Header, Footer, Label
from textual.containers import Horizontal

from beatrice.tui.graph_manager import GraphManager
from beatrice.tui.messages import (
    NodeSelected, NodeSaved, NodeAdded, NodeDeleted,
    LinkAdded, LinkDeleted, FilterChanged, StatusMessage, GraphChanged,
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
        ("ctrl+z", "undo", "Undo"),
        ("ctrl+y", "redo", "Redo"),
        ("e", "open_graph", "Open"),
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
        """Выйти с проверкой на несохранённые изменения."""
        gm = self.app.graph_manager
        if gm.dirty:
            from beatrice.tui.widgets.dialogs import ConfirmDialog
            def on_confirm(result):
                if result:
                    self.app.exit()
            self.app.push_screen(
                ConfirmDialog("Unsaved changes",
                             "There are unsaved changes. Quit anyway? (y/Escape)"),
                on_confirm
            )
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

    def action_undo(self) -> None:
        self._cmd_undo()

    def action_redo(self) -> None:
        self._cmd_redo()

    def action_show_help(self) -> None:
        """Открыть экран справки."""
        from beatrice.tui.widgets.help_screen import HelpScreen
        self.app.push_screen(HelpScreen())

    def action_render(self) -> None:
        gm = self.app.graph_manager
        if gm.path:
            output = Path(gm.path).with_suffix(".html")
            self.post_message(StatusMessage(f"Render: not yet implemented", "warning"))

    def action_command_palette(self) -> None:
        """Открыть палитру команд."""
        from beatrice.tui.widgets.command_palette import CommandPalette

        def on_command(result):
            if result is None:
                return
            self._handle_command(result)

        self.app.push_screen(CommandPalette(), on_command)

    def action_open_graph(self) -> None:
        """Запросить путь к графу и открыть его."""
        from beatrice.tui.widgets.dialogs import InputDialog

        def on_input(path):
            if path is None or not path.strip():
                return
            path = path.strip()
            if not Path(path).exists():
                self.post_message(StatusMessage(f"File not found: {path}", "error"))
                return
            try:
                self.app.graph_manager.load(path)
                self.app.title = f"Beatrice — {Path(path).name}"
                self._refresh_all()
                self._update_status_bar()
                self.post_message(StatusMessage(f"Opened: {path}", "success"))
            except Exception as e:
                self.post_message(StatusMessage(f"Load error: {e}", "error"))

        self.app.push_screen(
            InputDialog("Open graph", "Path to graph.json"), on_input)

    def _handle_command(self, handler_key: str) -> None:
        """Выполнить команду из палитры."""
        handlers = {
            "quit": lambda: self.action_quit(),
            "save": lambda: self.action_save(),
            "save_quit": lambda: (self.action_save(), self.app.exit())[0],
            "undo": self._cmd_undo,
            "redo": self._cmd_redo,
            "open_graph": lambda: self.action_open_graph(),
            "add_node": lambda: self._cmd_add_node(),
            "rm_node": lambda: self._cmd_rm_node(),
            "render": self._cmd_render,
            "theme_dark": self._cmd_theme_dark,
            "theme_light": self._cmd_theme_light,
            "filter_orphans_any": self._cmd_filter_orphans("any"),
            "filter_orphans_yes": self._cmd_filter_orphans("orphans"),
            "filter_orphans_no": self._cmd_filter_orphans("non-orphans"),
        }
        handler = handlers.get(handler_key)
        if handler:
            handler()

    def _cmd_undo(self) -> None:
        gm = self.app.graph_manager
        if gm.undo():
            self._refresh_all()
            self.post_message(StatusMessage("Undo", "success"))
        else:
            self.post_message(StatusMessage("Nothing to undo", "info"))

    def _cmd_redo(self) -> None:
        gm = self.app.graph_manager
        if gm.redo():
            self._refresh_all()
            self.post_message(StatusMessage("Redo", "success"))
        else:
            self.post_message(StatusMessage("Nothing to redo", "info"))

    def _cmd_add_node(self) -> None:
        """:add-node — быстрый ввод id через InputDialog."""
        from beatrice.tui.widgets.dialogs import InputDialog
        def on_input(nid):
            if nid is None or not nid.strip():
                return
            nid = nid.strip()
            gm = self.app.graph_manager
            if gm.has_node(nid):
                self.post_message(StatusMessage(f"Node '{nid}' already exists", "warning"))
                return
            gm.add_node(nid)
            self._refresh_all()
            self._select_node(nid)
            self.post_message(StatusMessage(f"Node added: {nid}", "success"))
        self.app.push_screen(InputDialog("Add node", "Node ID"), on_input)

    def _cmd_rm_node(self) -> None:
        """:rm-node — быстрый ввод id для удаления."""
        from beatrice.tui.widgets.dialogs import InputDialog
        def on_input(nid):
            if nid is None or not nid.strip():
                return
            nid = nid.strip()
            gm = self.app.graph_manager
            if not gm.has_node(nid):
                self.post_message(StatusMessage(f"Node '{nid}' not found", "error"))
                return
            degree = gm.degree(nid)
            from beatrice.tui.widgets.dialogs import ConfirmDialog
            def on_confirm(ok):
                if not ok:
                    return
                gm.remove_node(nid)
                self._refresh_all()
                self.post_message(StatusMessage(f"Deleted: {nid}", "success"))
            self.app.push_screen(
                ConfirmDialog("Delete node",
                    f"Delete '{nid}'?\n{degree} connection(s) will be removed."),
                on_confirm,
            )
        self.app.push_screen(InputDialog("Delete node", "Node ID"), on_input)

    def _cmd_render(self) -> None:
        gm = self.app.graph_manager
        if gm.path:
            output = Path(gm.path).with_suffix(".html")
            self.post_message(StatusMessage(f"Render: not yet implemented", "warning"))

    def _cmd_theme_dark(self) -> None:
        self.theme = "dark"
        self.post_message(StatusMessage("Theme: dark", "success"))

    def _cmd_theme_light(self) -> None:
        self.theme = "textual-light"
        self.post_message(StatusMessage("Theme: light", "success"))

    def _cmd_filter_orphans(self, mode: str):
        def _apply():
            nodes_list = self.query_one("#panel-left", NodesList)
            nodes_list._show_orphans = mode
            nodes_list._refresh_list()
        return _apply

    def _refresh_all(self) -> None:
        """Полностью обновить все три вьюпорта после undo/redo."""
        gm = self.app.graph_manager
        nodes_list = self.query_one("#panel-left", NodesList)
        nodes_list.load_from_graph_manager(gm)
        self._update_status_bar()
        # Обновить форму и связи для текущего узла
        form = self.query_one("#panel-center", NodeForm)
        if form.current_node and gm.has_node(form.current_node):
            form.show_node(form.current_node, gm.node_attrs(form.current_node))
            links = self.query_one("#panel-right", LinksList)
            links.show_links(
                form.current_node,
                gm.neighbors_out(form.current_node),
                gm.neighbors_in(form.current_node),
            )

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

    def on_graph_changed(self, message: GraphChanged) -> None:
        """Graph changed — update nodes list and status bar."""
        nodes_list = self.query_one("#panel-left", NodesList)
        nodes_list.load_from_graph_manager(self.app.graph_manager)
        self._update_status_bar()

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

    def __init__(self, graph_path: str, graph_manager: GraphManager):
        super().__init__()
        self.graph_path = graph_path
        self.graph_manager = graph_manager

    def on_mount(self) -> None:
        """Перейти на главный экран (граф уже загружен)."""
        gm = self.graph_manager
        self.title = f"Beatrice — {Path(self.graph_path).name}"
        self.sub_title = (
            f"{gm.node_count} nodes · {gm.edge_count} edges · "
            f"{gm.orphan_count} orphans"
        )
        self.push_screen(MainScreen())


def run_tui(graph_path: str) -> None:
    """Запустить TUI с указанным графом.

    При ошибке загрузки печатает сообщение в stderr и завершается с кодом 1.
    """
    import sys

    if not Path(graph_path).exists():
        print(f"Ошибка: файл не найден: {graph_path}", file=sys.stderr)
        sys.exit(1)

    try:
        gm = GraphManager()
        gm.load(graph_path)
    except Exception as e:
        print(f"Ошибка загрузки графа: {e}", file=sys.stderr)
        sys.exit(1)

    app = BeatriceApp(graph_path, gm)
    app.run()


def run_tui_cli() -> None:
    """Entry point для beatrice-tui."""
    import sys
    if len(sys.argv) < 2:
        print("Использование: beatrice-tui <graph.json>", file=sys.stderr)
        sys.exit(1)
    run_tui(sys.argv[1])
