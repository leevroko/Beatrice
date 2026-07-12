"""python3 -m beatrice.web_gui <graph.json> — запустить Web GUI сервер."""
import sys
from beatrice.web_gui.server import run_server

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 -m beatrice.web_gui <graph.json>", file=sys.stderr)
        sys.exit(1)
    run_server(sys.argv[1])
