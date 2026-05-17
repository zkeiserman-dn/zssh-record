#!/usr/bin/env python3
"""
Tiny stdlib HTTP server for the zssh-record live viewer.

Routes:
  GET /                  -> index.html (from <out_dir>)
  GET /meta.json         -> meta.json (from <out_dir>)
  GET /stream/session    -> SSE tail -f of session.log
  GET /stream/wb         -> SSE tail -f of wb_agent.log
  GET /stream/fe         -> SSE tail -f of wb_fe_agent.log

Bind address comes from argv[3] (default 0.0.0.0). Quits on Ctrl-C / SIGTERM.
"""

import os
import sys
import time
import json
import signal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 0
OUT_DIR = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.getcwd()
BIND = sys.argv[3] if len(sys.argv) > 3 else "0.0.0.0"

# Static entries
LOGS = {"session": os.path.join(OUT_DIR, "session.log")}
import glob as _glob


def _refresh_logs():
    """Re-scan OUT_DIR for wb_*_ncp*.log files (called on each request)."""
    for path in sorted(_glob.glob(os.path.join(OUT_DIR, "wb_*_ncp*.log"))):
        name = os.path.basename(path).replace(".log", "")
        if name not in LOGS:
            LOGS[name] = path
    # Fallback to legacy single-NCP names
    if not any(k.startswith("wb_agent_ncp") for k in LOGS):
        for legacy in ("wb_agent.log", "wb_fe_agent.log"):
            p = os.path.join(OUT_DIR, legacy)
            n = legacy.replace(".log", "_ncp0")
            if os.path.exists(p) and n not in LOGS:
                LOGS[n] = p


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
        _refresh_logs()
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

        if path == "/streams.json":
            import json as _json
            streams = sorted(k for k in LOGS if k.startswith("wb_"))
            self._send(200, _json.dumps(streams).encode(), "application/json")
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

        # Seek to the END of the file: each browser tab only sees lines that
        # arrive AFTER it connects.  No backfill of historical content.
        try:
            fh.seek(0, 2)
        except Exception:
            pass

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
    server = ThreadingHTTPServer((BIND, PORT), Handler)
    server.daemon_threads = True

    def stop(*_):
        try:
            server.shutdown()
        except Exception:
            pass

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    actual_port = server.server_address[1]
    sys.stdout.write(f"[zssh-viewer] serving {OUT_DIR} on http://{BIND}:{actual_port}/\n")
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
