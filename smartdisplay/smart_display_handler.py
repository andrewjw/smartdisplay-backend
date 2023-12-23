import http.server
import json
from io import BytesIO
import socket
import socketserver
from typing import Any, Union
from urllib.parse import urlparse, parse_qs
import sys

from .sonos import SonosHandler

SONOS = SonosHandler()


class SmartDisplayHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.startswith("/next_screen"):
            data = self.next_screen()
        elif self.path.startswith("/sonos/art"):
            self.sonos_art()
            return
        elif self.path.startswith("/sonos"):
            data = self.sonos_data()
        else:
            self.return404()
            return

        if data is None:
            self.return404()
            return

        json_data = json.dumps(data).encode("utf8")

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header("Content-length", str(len(json_data)))
        self.end_headers()

        self.wfile.write(json_data)

    def return404(self) -> Any:
        self.send_response(404)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

        self.wfile.write(f"Page {self.path} not found".encode("utf8"))

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

        if SONOS.has_track_changed():
            return "sonos"

        if current == "clock":
            return "balls"
        if current == "balls":
            return "clock"
        return "clock"

    def sonos_data(self) -> Any:
        track = SONOS.track_info
        if track is None:
            return None
        return {
            "artist": track.artist,
            "album": track.album,
            "track": track.title,
            "album_art": SONOS.get_current_album_art() is not None
        }

    def sonos_art(self) -> Any:
        art = SONOS.get_current_album_art()
        if art is None:
            self.send_response(404)
            self.send_header("Content-type", "text/plain")
            self.send_header("Content-length", "4")
            self.end_headers()
            self.wfile.write("404\n".encode("utf8"))
            return
        self.send_response(200)
        self.send_header("Content-type", "application/octet-stream")
        self.send_header("Content-length", str(64*64*3))
        self.end_headers()

        self.wfile.write(art)

    def error(self, data: str) -> Any:
        sys.stderr.write(data)
        sys.stderr.flush()
        return {}
