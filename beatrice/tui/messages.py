"""Message definitions for TUI inter-widget communication."""

from textual.message import Message


class NodeSelected(Message):
    """Пользователь выбрал узел в списке."""

    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        super().__init__()


class NodeSaved(Message):
    """Узел был изменён и сохранён."""

    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        super().__init__()


class NodeAdded(Message):
    """Новый узел добавлен."""

    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        super().__init__()


class NodeDeleted(Message):
    """Узел удалён."""

    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        super().__init__()


class LinkAdded(Message):
    """Новая связь добавлена."""

    def __init__(self, source: str, target: str, relation: str) -> None:
        self.source = source
        self.target = target
        self.relation = relation
        super().__init__()


class LinkDeleted(Message):
    """Связь удалена."""

    def __init__(self, source: str, target: str) -> None:
        self.source = source
        self.target = target
        super().__init__()


class FilterChanged(Message):
    """Изменился фильтр списка узлов."""

    def __init__(self, query: str = "", show_orphans: str = "any") -> None:
        self.query = query
        self.show_orphans = show_orphans  # "any" | "orphans" | "non-orphans"
        super().__init__()


class GraphSaved(Message):
    """Граф сохранён на диск."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__()


class StatusMessage(Message):
    """Сообщение для нижней строки (статус/ошибка)."""

    def __init__(self, text: str, severity: str = "info") -> None:
        self.text = text
        self.severity = severity  # "info" | "success" | "error" | "warning"
        super().__init__()
