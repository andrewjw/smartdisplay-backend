import http.server
import json
from io import BytesIO
from typing import Any
from urllib.parse import urlparse, parse_qs
import sys

from .sonos import has_track_changed, get_current_album_art


class SmartDisplayHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.startswith("/next_screen"):
            data = self.next_screen()
        elif self.path.startswith("/sonos"):
            data = self.sonos()
        else:
            self.send_response(404)
            self.send_header("Content-type", "text/plain")
            self.end_headers()

            self.wfile.write(f"Page {self.path} not found".encode("utf8"))
            return

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()

        self.wfile.write(json.dumps(data).encode("utf8"))

    def do_POST(self) -> None:
        file_length = int(self.headers['Content-Length'])
        data = BytesIO()
        data.write(self.rfile.read(file_length))

        self.error(data.getvalue().decode("utf8"))

        self.send_response(204)
        self.end_headers()

    def next_screen(self) -> Any:
        query_components = parse_qs(urlparse(self.path).query)
        current = query_components["current"][0]

        if has_track_changed():
            return "sonos"

        if current == "clock":
            return "balls"
        if current == "balls":
            return "clock"
        return "clock"

    def sonos(self) -> Any:
        return {
            "album_art": get_current_album_art()
        }

    def error(self, data: str) -> Any:
        sys.stderr.write(data)
        sys.stderr.flush()
        return {}
