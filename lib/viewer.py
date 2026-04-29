#!/usr/bin/env python3
"""
Tiny stdlib HTTP server for the zssh-record live viewer.

Routes:
  GET /                  -> index.html (from <out_dir>)
  GET /meta.json         -> meta.json (from <out_dir>)
  GET /stream/session    -> SSE tail -f of session.log
  GET /stream/wb         -> SSE tail -f of wb_agent.log
  GET /stream/fe         -> SSE tail -f of wb_fe_agent.log

Bound to 127.0.0.1 only. Quits on Ctrl-C / SIGTERM.
"""

import os
import sys
import time
import json
import signal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 0
OUT_DIR = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.getcwd()

LOGS = {
    "session": os.path.join(OUT_DIR, "session.log"),
    "wb": os.path.join(OUT_DIR, "wb_agent.log"),
    "fe": os.path.join(OUT_DIR, "wb_fe_agent.log"),
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return  # silence default access log

    def _send(self, status, body, ctype="text/plain; charset=utf-8", extra=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        if body is not None:
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body is not None:
            self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/" or path == "/index.html":
            try:
                with open(os.path.join(OUT_DIR, "index.html"), "rb") as fh:
                    self._send(200, fh.read(), "text/html; charset=utf-8")
            except FileNotFoundError:
                self._send(404, b"index.html not found")
            return

        if path == "/meta.json":
            try:
                with open(os.path.join(OUT_DIR, "meta.json"), "rb") as fh:
                    self._send(200, fh.read(), "application/json")
            except FileNotFoundError:
                self._send(200, b"{}", "application/json")
            return

        if path.startswith("/stream/"):
            name = path[len("/stream/"):]
            log_path = LOGS.get(name)
            if not log_path:
                self._send(404, b"unknown stream")
                return
            self._stream(log_path)
            return

        self._send(404, b"not found")

    def _stream(self, log_path):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        # Wait briefly for the file to exist
        for _ in range(50):
            if os.path.exists(log_path):
                break
            time.sleep(0.1)

        try:
            fh = open(log_path, "rb")
        except FileNotFoundError:
            try:
                self.wfile.write(b"event: end\ndata: missing\n\n")
            except Exception:
                pass
            return

        # Start from the beginning so user sees recent context
        last_keepalive = time.time()
        try:
            while True:
                chunk = fh.read(4096)
                if chunk:
                    # SSE: split on newlines, prefix each with `data: `
                    text = chunk.decode("utf-8", errors="replace")
                    for line in text.splitlines(True):
                        # keep trailing newlines off; SSE separates events with blank line
                        line = line.rstrip("\n")
                        try:
                            self.wfile.write(b"data: " + line.encode("utf-8", "replace") + b"\n\n")
                        except (BrokenPipeError, ConnectionResetError):
                            return
                    self.wfile.flush()
                    last_keepalive = time.time()
                else:
                    # idle: keepalive every 15 s, otherwise sleep briefly
                    if time.time() - last_keepalive > 15:
                        try:
                            self.wfile.write(b": keepalive\n\n")
                            self.wfile.flush()
                        except (BrokenPipeError, ConnectionResetError):
                            return
                        last_keepalive = time.time()
                    time.sleep(0.2)
        finally:
            try:
                fh.close()
            except Exception:
                pass


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    server.daemon_threads = True

    def stop(*_):
        try:
            server.shutdown()
        except Exception:
            pass

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    actual_port = server.server_address[1]
    sys.stdout.write(f"[zssh-viewer] serving {OUT_DIR} on http://127.0.0.1:{actual_port}/\n")
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
