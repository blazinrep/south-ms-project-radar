#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[1]
PORT = 8766
RUN_LOCK = threading.Lock()

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(REPO), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, fmt, *args):
        print(f"[HardHatRadar] {self.address_string()} - {fmt % args}", flush=True)

    def _json(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if urlparse(self.path).path == "/api/status":
            self._json(200, {
                "ok": True,
                "service": "Hard Hat Radar Control Room",
                "port": PORT,
                "repo": str(REPO),
            })
            return
        super().do_GET()

    def do_POST(self):
        if urlparse(self.path).path != "/api/run-radar-scan":
            self._json(404, {"ok": False, "error": "Not found"})
            return

        if not RUN_LOCK.acquire(blocking=False):
            self._json(409, {"ok": False, "error": "A Radar Scan is already running."})
            return

        try:
            started = time.time()
            proc = subprocess.run(
                ["bash", "./run_intelligence_pipeline.sh"],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                timeout=900,
            )
            output = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
            self._json(200 if proc.returncode == 0 else 500, {
                "ok": proc.returncode == 0,
                "returncode": proc.returncode,
                "elapsedSeconds": round(time.time() - started, 1),
                "output": output[-30000:],
            })
        except subprocess.TimeoutExpired:
            self._json(504, {"ok": False, "error": "Radar Scan exceeded the 15-minute safety timeout."})
        except Exception as exc:
            self._json(500, {"ok": False, "error": str(exc)})
        finally:
            RUN_LOCK.release()

if __name__ == "__main__":
    os.chdir(REPO)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Hard Hat Radar Control Room serving http://127.0.0.1:{PORT}", flush=True)
    server.serve_forever()
