from datetime import date, datetime, tzinfo
import http.server
import json
from io import BytesIO
from typing import Any, List
from urllib.parse import urlparse, parse_qs
import sys
import traceback
from zoneinfo import ZoneInfo

from sentry_sdk import capture_exception, capture_message  # type:ignore

from .current_weather import get_current_weather, \
                             get_current_weather_last_update
from .sonos import SonosHandler
from .trains import get_trains_message, get_trains_from_london, \
                    get_trains_to_london
from .house_temperature import get_house_temperature
from .solar import get_current_solar, is_solar_valid
from .water_gas import get_water_gas

SONOS = SonosHandler()


def handle_error(func):
    def r(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            traceback.print_exception(e)
            capture_exception(e)

            self.send_response(500)
            self.send_header("Content-type", "text/plain")
            self.end_headers()

            self.wfile.write(f"Exception Occurred.\n".encode("utf8"))
    return r


class SmartDisplayHandler(http.server.BaseHTTPRequestHandler):
    @handle_error
    def do_GET(self) -> None:
        data: Any
        if self.path.startswith("/next_screen"):
            data = self.next_screen()
        elif self.path.startswith("/sonos/art"):
            self.sonos_art()
            return
        elif self.path.startswith("/sonos"):
            data = self.sonos_data()
        elif self.path.startswith("/trains_to_london"):
            data = self.trains_to_london()
        elif self.path.startswith("/trains_from_london"):
            data = self.trains_from_london()
        elif self.path.startswith("/house_temperature"):
            data = get_house_temperature()
        elif self.path.startswith("/current_weather"):
            data = get_current_weather()
        elif self.path.startswith("/solar"):
            data = get_current_solar()
        elif self.path.startswith("/water_gas"):
            data = get_water_gas()
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

    @handle_error
    def do_POST(self) -> None:
        file_length = int(self.headers['Content-Length'])
        data = BytesIO()
        data.write(self.rfile.read(file_length))

        if self.path.startswith("/log"):
            self.log(data.getvalue().decode("utf8"))
        elif self.path.startswith("/error"):
            self.error(data.getvalue().decode("utf8"))
        else:
            self.return404()
            return

        self.send_response(204)
        self.end_headers()

    def next_screen(self) -> str:
        query_components = parse_qs(urlparse(self.path).query)
        current = query_components["current"][0]

        if current in ("sonos", "sonos_quick"):
            current = SONOS.get_last_screen()

        if SONOS.has_track_changed():
            SONOS.set_last_screen(current)
            return "sonos"
        if SONOS.show_quick():
            SONOS.set_last_screen(current)
            return "sonos_quick"

        screens = self.get_screens()
        idx = [idx for (screen, idx) in zip(screens, range(len(screens)))
               if screen == current]
        if len(idx) == 0:
            return screens[0]
        return screens[(idx[0] + 1) % len(screens)]

    def get_screens(self) -> List[str]:
        now = datetime.now(tz=ZoneInfo("Europe/London"))

        if now.hour < 6 or (now.hour == 6 and now.minute < 20) or \
           (now.hour == 22 and now.minute >= 30) or now.hour > 22:
            return ["blackout"]

        r = ["clock", "house_temperature"]
        if is_solar_valid():
            r.append("solar")
        r.append("water_gas")
        if get_current_weather_last_update() < 10 * 60:
            r.append("current_weather")

        hour = now.hour
        if date.today().weekday() in (0, 1):
            if hour in (6, 7, 8):
                r.append("trains_to_london")
            elif hour in (16, 17, 18, 19, 20, 21, 22):
                r.append("trains_home")
        elif date.today().weekday() in (5, 6) and hour >= 8 and hour < 18:
            r.append("trains_to_london")
        r.append("balls")
        return r

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

    def trains_to_london(self) -> Any:
        return {
            "msg": get_trains_message(),
            "trains": get_trains_to_london()
        }

    def trains_from_london(self) -> Any:
        return {
            "msg": get_trains_message(),
            "trains": get_trains_from_london()
        }

    def log(self, data: str) -> Any:
        sys.stdout.write(data)
        sys.stdout.flush()
        return {}

    def error(self, data: str) -> Any:
        capture_message(data)
        sys.stderr.write(data)
        sys.stderr.flush()
        return {}
