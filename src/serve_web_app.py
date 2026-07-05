"""
Serve the landslide warning dashboard with a live refresh endpoint.

Run:
    python -m src.serve_web_app
"""

import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import ROOT_DIR


HOST = "127.0.0.1"
PORT = 8000
WEB_DIR = os.path.join(ROOT_DIR, "web_app")


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_POST(self):
        if self.path != "/api/refresh":
            self.send_error(404, "Unknown endpoint")
            return

        try:
            from src.dynamic_risk import generate_dynamic_landslide_risk_map
            from src.export_web_app import export_web_app_assets

            generate_dynamic_landslide_risk_map()
            export_web_app_assets()
            self._send_json({"ok": True})
        except Exception as exc:
            traceback.print_exc()
            self._send_json(
                {
                    "ok": False,
                    "error": str(exc),
                    "python": sys.executable,
                    "hint": (
                        "Start the dashboard with the project environment: "
                        "D:\\sindupalchok_landslide\\venv\\Scripts\\python.exe "
                        "-m src.serve_web_app"
                    ),
                },
                status=500,
            )

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve_web_app(host=HOST, port=PORT):
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"Serving dashboard at http://{host}:{port}/")
    print("Use Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    serve_web_app()
