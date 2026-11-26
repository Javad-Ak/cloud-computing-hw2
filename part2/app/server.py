"""HTTP API for the lab queue.

Bodies are plain text, not JSON:
  GET  /health                  200  ok
  POST /join   {"name": "..."}  200  ticket number, or 400 if the name is rejected
  POST /next                    200  name, or 404 empty
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from app.queue import join, take


def make_handler(queue_file: Path) -> type[BaseHTTPRequestHandler]:
    class QueueHandler(BaseHTTPRequestHandler):
        def _send_text(self, status: int, text: str) -> None:
            body = text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path == "/health":
                self._send_text(200, "ok")
            else:
                self._send_text(404, "not found")

        def do_POST(self) -> None:
            if self.path == "/join":
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                try:
                    data = json.loads(raw.decode("utf-8"))
                    if not isinstance(data, dict) or "name" not in data:
                        raise ValueError("missing name")
                    ticket = join(queue_file, data["name"])
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
                    self._send_text(400, "invalid")
                    return
                self._send_text(200, str(ticket))
            elif self.path == "/next":
                try:
                    name = take(queue_file)
                except LookupError:
                    self._send_text(404, "empty")
                    return
                self._send_text(200, name)
            else:
                self._send_text(404, "not found")

    return QueueHandler


def serve(host: str, port: int, data_dir: str) -> None:
    """Listen until the process is stopped. Use join and take from app.queue."""
    queue_file = Path(data_dir) / "queue.txt"
    server = ThreadingHTTPServer((host, port), make_handler(queue_file))
    try:
        server.serve_forever()
    finally:
        server.server_close()


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    data_dir = os.environ.get("DATA_DIR", "/data")
    serve("0.0.0.0", port, data_dir)


if __name__ == "__main__":
    main()