"""HTTP API for the lab queue with optional Redis backend and Prometheus metrics."""

from __future__ import annotations

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

from app.queue import join as file_join
from app.queue import take as file_take

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    METRICS_ENABLED = True
    HTTP_REQUESTS_TOTAL = Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["method", "route", "status"],
    )
    HTTP_REQUEST_DURATION = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency in seconds",
        ["method", "route"],
        buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
    )
    DB_OP_DURATION = Histogram(
        "db_operation_duration_seconds",
        "Database operation latency in seconds",
        ["operation"],
        buckets=(0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
    )
    DB_ERRORS_TOTAL = Counter(
        "db_errors_total",
        "Total database errors",
        ["operation"],
    )
    QUEUE_LENGTH = Gauge(
        "queue_length",
        "Current number of people in the shared queue",
    )
except ImportError:
    METRICS_ENABLED = False

KNOWN_ROUTES = {"/health", "/join", "/next", "/metrics"}


def _build_backend(
    data_dir: str,
) -> tuple[Callable[[str], int], Callable[[], str], Callable[[], int] | None]:
    backend = os.environ.get("QUEUE_BACKEND", "file").lower()
    if backend == "redis":
        from app.redis_queue import RedisQueue

        redis_url = os.environ.get("REDIS_URL", "redis://db:6379/0")
        rq = RedisQueue(redis_url)
        return rq.join, rq.take, rq.length

    queue_file = Path(data_dir) / "queue.txt"
    return (
        (lambda name: file_join(queue_file, name)),
        (lambda: file_take(queue_file)),
        None,
    )


def make_handler(
    join_fn: Callable[[str], int],
    take_fn: Callable[[], str],
    length_fn: Callable[[], int] | None = None,
) -> type[BaseHTTPRequestHandler]:
    class QueueHandler(BaseHTTPRequestHandler):
        def _record(self, method: str, route: str, status: int, start: float) -> None:
            if not METRICS_ENABLED:
                return
            norm_route = route if route in KNOWN_ROUTES else "/other"
            elapsed = time.perf_counter() - start
            HTTP_REQUESTS_TOTAL.labels(
                method=method, route=norm_route, status=str(status)
            ).inc()
            HTTP_REQUEST_DURATION.labels(method=method, route=norm_route).observe(elapsed)

        def _send_text(
            self, status: int, text: str, start: float, method: str
        ) -> None:
            body = text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            self._record(method, self.path, status, start)

        def do_GET(self) -> None:
            start = time.perf_counter()
            if self.path == "/health":
                self._send_text(200, "ok", start, "GET")
            elif self.path == "/metrics" and METRICS_ENABLED:
                if length_fn is not None:
                    try:
                        QUEUE_LENGTH.set(length_fn())
                    except Exception:
                        DB_ERRORS_TOTAL.labels(operation="length").inc()
                payload = generate_latest()
                self.send_response(200)
                self.send_header("Content-Type", CONTENT_TYPE_LATEST)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                self._record("GET", "/metrics", 200, start)
            else:
                self._send_text(404, "not found", start, "GET")

        def do_POST(self) -> None:
            start = time.perf_counter()
            if self.path == "/join":
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                try:
                    data = json.loads(raw.decode("utf-8"))
                    if not isinstance(data, dict) or "name" not in data:
                        raise ValueError("missing name")
                    db_start = time.perf_counter()
                    try:
                        ticket = join_fn(data["name"])
                    finally:
                        if METRICS_ENABLED:
                            DB_OP_DURATION.labels(operation="join").observe(
                                time.perf_counter() - db_start
                            )
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
                    self._send_text(400, "invalid", start, "POST")
                    return
                except Exception:
                    if METRICS_ENABLED:
                        DB_ERRORS_TOTAL.labels(operation="join").inc()
                    self._send_text(503, "db unavailable", start, "POST")
                    return
                self._send_text(200, str(ticket), start, "POST")
            elif self.path == "/next":
                db_start = time.perf_counter()
                try:
                    name = take_fn()
                except LookupError:
                    self._send_text(404, "empty", start, "POST")
                    return
                except Exception:
                    if METRICS_ENABLED:
                        DB_ERRORS_TOTAL.labels(operation="take").inc()
                    self._send_text(503, "db unavailable", start, "POST")
                    return
                finally:
                    if METRICS_ENABLED:
                        DB_OP_DURATION.labels(operation="take").observe(
                            time.perf_counter() - db_start
                        )
                self._send_text(200, name, start, "POST")
            else:
                self._send_text(404, "not found", start, "POST")

    return QueueHandler


def serve(host: str, port: int, data_dir: str) -> None:
    """Listen until the process is stopped."""
    join_fn, take_fn, length_fn = _build_backend(data_dir)
    server = ThreadingHTTPServer((host, port), make_handler(join_fn, take_fn, length_fn))
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