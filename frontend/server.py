from __future__ import annotations

import os
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BACKEND_BASE = os.environ.get("SUBDFA_BACKEND_BASE", "http://127.0.0.1:8787").rstrip("/")


class FrontendHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def end_headers(self) -> None:
        if not self.path.startswith("/api/v1/"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _proxy(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else None
        request = Request(
            f"{BACKEND_BASE}{self.path}",
            data=body,
            headers={
                "Content-Type": self.headers.get("Content-Type", "application/json"),
                "Accept": self.headers.get("Accept", "application/json"),
            },
            method=self.command,
        )
        try:
            with urlopen(request, timeout=120) as upstream:
                status = upstream.status
                payload = upstream.read()
                headers = dict(upstream.headers.items())
        except HTTPError as exc:
            status = exc.code
            payload = exc.read()
            headers = dict(exc.headers.items())
        except URLError as exc:
            status = 502
            payload = f"{{\"error\":\"Backend unavailable: {exc.reason}\"}}".encode("utf-8")
            headers = {"Content-Type": "application/json; charset=utf-8"}

        self.send_response(status)
        for name in ("Content-Type", "Cache-Control"):
            if name in headers:
                self.send_header(name, headers[name])
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        if self.path.startswith("/api/v1/"):
            self._proxy()
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.path.startswith("/api/v1/"):
            self._proxy()
            return
        self.send_error(405, "Method not allowed")

    def do_OPTIONS(self) -> None:
        if self.path.startswith("/api/v1/"):
            self._proxy()
            return
        self.send_error(405, "Method not allowed")


if __name__ == "__main__":
    host = os.environ.get("SUBDFA_FRONTEND_HOST", "127.0.0.1")
    port = int(os.environ.get("SUBDFA_FRONTEND_PORT", "8790"))
    server = ThreadingHTTPServer((host, port), FrontendHandler)
    print(f"AutoLogic frontend + API proxy listening on http://{host}:{port}; backend={BACKEND_BASE}")
    server.serve_forever()
