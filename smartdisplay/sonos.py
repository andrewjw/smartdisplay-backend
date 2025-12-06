#!/usr/bin/python3

from datetime import datetime, UTC
from functools import lru_cache
import io
import math
import queue
import struct
import sys
import threading
import time
from typing import Any, Dict, Optional, List
from xml.dom.minidom import parseString

from PIL import Image
import requests

from sentry_sdk import capture_exception  # type:ignore
import soco  # type: ignore

# Apple Music
# {'creator': 'Arcade Fire', 'stream_content': '', 'radio_show': '',
#  'album_art_uri': '/getaa?s=1&u=xyz',
#  'album': 'Funeral', 'parent_id': '-1', 'item_id': '-1', 'restricted': True,
#  'title': 'Neighborhood #1 (Tunnels)',
#  'resources': [{'uri': 'x-sonos-http:song%3a1249418558.mp4?...',
#                'protocol_info': 'sonos.com-http:*:audio/mp4:*',
#                'import_uri': None, 'size': None, 'duration': '0:04:48',
#                'bitrate': None, 'sample_frequency': None,
#                'bits_per_sample': None, 'nr_audio_channels': None,
#                'resolution': None, 'color_depth': None, 'protection': None}],
#  'desc': None}

# BBC Sounds
# {'stream_content': "BR P|TYPE=SNG|TITLE (Are You Ready) Do the Bus Stop "
#                    "(Bustin' Loose Disco Express Remix)|ARTIST Fatback Band"
#                    "|ALBUM ",
#  'radio_show': 'Radio 6 Music,',
#  'album_art_uri': 'https://ichef.bbci.co.uk/images/ic/640x640/p0bqcdzf.jpg',
#  'parent_id': '-1', 'item_id': '-1', 'restricted': True, 'title': '',
#  'resources': [{'uri': 'x-sonosapi-hls:stations%7...',
#                'protocol_info': 'sonos.com-http:*:application/x-mpegURL:*',
#                'import_uri': None, 'size': None,
#                'duration': None, 'bitrate': None, 'sample_frequency': None,
#                'bits_per_sample': None, 'nr_audio_channels': None,
#                'resolution': None, 'color_depth': None, 'protection': None}],
#  'desc': None}

# Music Library
# {'creator': '86TVs', 'stream_content': '', 'radio_show': '',
#  'album_art_uri': '/getaa?u=x-file-cifs%3a%2f%2f192.168.1.207%2f...',
#  'album': '86TVs', 'original_track_number': 1, 'parent_id': '-1',
#  'item_id': '-1', 'restricted': True, 'title': 'Modern Life',
#  'resources': [{'uri': 'x-file-cifs://192.168.1.207/music_hq/...',
#                 'protocol_info': 'x-file-cifs:*:audio/flac:*',
#                 'import_uri': None, 'size': None,
#                 'duration': '0:03:11', 'bitrate': None,
#                 'sample_frequency': None,
#                 'bits_per_sample': None, 'nr_audio_channels': None,
#                 'resolution': None,
#                 'color_depth': None, 'protection': None}], 'desc': None}

CURRENT_TRACK_INFO: Optional["TrackInfo"] = None


class Terminator:
    def __init__(self) -> None:
        self._terminate = False

    def terminate(self) -> None:
        print("Terminating!")
        self._terminate = True

    def is_terminated(self) -> bool:
        return self._terminate


def sonos_watcher(handler: "SonosHandler", terminator: Terminator) -> None:
    devices = {}
    subscription = None
    try:
        while "Kitchen" not in devices:
            devices = {device.player_name: device
                       for device in soco.discover(timeout=60)}
        print("sonos got kitchen")

        subscription = soco.services.AVTransport(devices["Kitchen"]) \
            .subscribe(auto_renew=True)

        while not terminator.is_terminated():
            try:
                event = subscription.events.get(timeout=5)

                if event.variables.get("transport_state", None) != "PLAYING":
                    handler.track_info = None
                    continue
                if "current_track_meta_data" in event.variables \
                        and event.variables["current_track_meta_data"] != "":
                    print("sonos", event.variables["current_track_meta_data"].to_dict())
                    track_info = process_event_track_metadata(
                        event.variables["current_track_meta_data"].to_dict(),
                        devices["Kitchen"])
                    handler.track_info = track_info
                    print("sonos", track_info)
            except queue.Empty:
                pass
    except Exception as e:
        sys.stderr.write("Error in sonos_watcher:\n")
        sys.stderr.write(repr(e) + "\n")
        sys.stderr.flush()
        capture_exception(e)
    finally:
        print("Sonos watcher is shutting down!")
        handler.track_info = None
        if subscription is not None:
            try:
                subscription.unsubscribe()
            except Exception as e:
                pass


def stream_content_split(stream_content: str, key: str) -> str:
    if key in stream_content:
        return stream_content.split(key)[1].split("|")[0]
    return ""


def process_event_track_metadata(metadata: Dict[str, Any],
                                 device: Any) -> Optional["TrackInfo"]:
    if "creator" in metadata and len(metadata["creator"]) > 0:
        return TrackInfo({
            "artist": metadata["creator"],
            "album": metadata.get("album", ""),
            "title": metadata.get("title", ""),
            "album_art": metadata.get("album_art_uri", "")
        }, device.ip_address)
    elif "stream_content" in metadata and len(metadata["stream_content"]) > 0:
        return TrackInfo({
            "artist": stream_content_split(
                metadata["stream_content"],
                "|ARTIST "),
            "album": stream_content_split(
                metadata["stream_content"],
                "|ALBUM "),
            "title": stream_content_split(
                metadata["stream_content"],
                "|TITLE "),
            "album_art": metadata.get("album_art_uri", "")
        }, device.ip_address)
    elif "title" in metadata and len(metadata["title"]) > 0:
        return TrackInfo({
            "artist": "",
            "album": "",
            "title": metadata["title"],
            "album_art": metadata.get("album_art_uri", "")
        }, device.ip_address)
    else:
        sys.stderr.write("Unknown metadata format:\n")
        sys.stderr.write(repr(metadata) + "\n")
        return None


class TrackInfo:
    def __init__(self, track_info: Any, sonos_uri: str) -> None:
        self.created = datetime.now(UTC)
        self.artist = track_info["artist"]
        self.album = track_info["album"]
        self.title = track_info["title"]
        self.album_art = track_info["album_art"]
        if not self.album_art.startswith("http"):
            self.album_art = f"http://{sonos_uri}:1400{self.album_art}"

        if self.album_art is not None and len(self.album_art) > 0:
            try:
                self.album_art_header: Optional[bytes] = \
                    get_album_art(self.album_art, True)
                self.album_art_image: Optional[bytes] = \
                    get_album_art(self.album_art, False)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code != 403:
                    raise
                sys.stderr.write(f"Got error {e.response.status_code} accessing {self.album_art}.")
                self.album_art_header = None
                self.album_art_image = None
            except requests.exceptions.ConnectionError as e:
                sys.stderr.write("Error loading Album Art\n")
                sys.stderr.write(repr(e))
                self.album_art_header = None
                self.album_art_image = None
        else:
            print("no album art url :-(")
            self.album_art_header = None
            self.album_art_image = None

    def __eq__(self, other: object) -> bool:
        if other is None:
            return True
        if not isinstance(other, TrackInfo):
            return False
        return self.artist == other.artist and self.album == other.album and \
            self.title == other.title and self.album_art == self.album_art

    def __neq__(self, other: "TrackInfo") -> bool:
        return not (self == other)

    def __str__(self):
        return f"<TrackInfo '{self.artist}' '{self.album}' '{self.title}'" + \
               f" {self.album_art_image is not None}>"


class SonosHandler:
    def __init__(self) -> None:
        self._last_track_info: Optional[TrackInfo] = None
        self.track_info: Optional[TrackInfo] = None
        self.last_screen = "sonos"
        self._last_display_time: Optional[datetime] = None

        self._terminator = Terminator()
        print("starting sonos watcher")
        self._thread = threading.Thread(target=sonos_watcher,
                                        args=(self, self._terminator))
        self._thread.daemon = True
        self._thread.start()

    def __del__(self):
        print("SonosHandler shutting down...")
        self._terminator.terminate()
        if self._thread.is_alive():
            self._thread.join(timeout=5)

    def has_track_changed(self) -> bool:
        if self.track_info is None:
            self.last_display_time = None
            self._last_track_info = None
            return False
        if self._last_track_info is None \
                or self.track_info != self._last_track_info:
            self._last_track_info = self.track_info
            self.last_display_time = datetime.now(UTC)
            return True
        gap = datetime.now(UTC) - self.track_info.created
        if abs(gap.total_seconds()) > 60 * 5:
            self.track_info.created = datetime.now(UTC)
            self.last_display_time = datetime.now(UTC)
            return True
        return False

    def get_current_album_art(self, header: bool = False) -> Optional[bytes]:
        if self.track_info is None:
            return None
        return self.track_info.album_art_header if header \
            else self.track_info.album_art_image

    def set_last_screen(self, screen: str) -> None:
        self.last_screen = screen

    def get_last_screen(self) -> str:
        return self.last_screen

    def show_quick(self) -> bool:
        if self._last_display_time is None:
            return False
        if (datetime.now(UTC) - self._last_display_time).total_seconds() \
           > 2 * 60:
            self._last_display_time = datetime.now(UTC)
            return True
        return False


@lru_cache(maxsize=20)
def get_album_art(art_uri: str, header: bool) -> Optional[bytes]:
    sys.stderr.write(f"Getting album art {art_uri}\n")
    resp = requests.get(art_uri, stream=True, timeout=10)
    resp.raise_for_status()
    buffer = io.BytesIO()
    try:
        for chunk in resp.iter_content(chunk_size=128):
            buffer.write(chunk)
    except requests.exceptions.ChunkedEncodingError:
        return None
    buffer.seek(0)

    image_data: List[int] = []
    if header:
        image_data.extend(ord(c) for c in "I75v1")
        image_data.append(64)
        image_data.append(64)
        image_data.append(3)
        expected_size = 8 + 64 * 64 * 3
    else:
        expected_size = 64 * 64 * 3
    with Image.open(buffer) as im:
        try:
            im.thumbnail((64, 64), Image.Resampling.NEAREST)
        except OSError:
            return None
        xsize, ysize = im.size

        xbefore, xafter, ybefore, yafter = 0, 0, 0, 0
        if xsize < 64:
            xbefore = math.floor((64 - xsize) / 2.0)
            xafter = math.ceil((64 - xsize) / 2.0)
        if ysize < 64:
            ybefore = math.floor((64 - ysize) / 2.0)
            yafter = math.ceil((64 - ysize) / 2.0)

        if ybefore > 0:
            image_data.extend([0, 0, 0] * 64 * ybefore)
        for y in range(ysize):
            if xbefore > 0:
                image_data.extend([0, 0, 0] * xbefore)
            for x in range(xsize):
                pixel = im.getpixel((x, y))
                if isinstance(pixel, int):
                    r, g, b = pixel, pixel, pixel
                elif len(pixel) == 3:
                    r, g, b = pixel
                else:
                    raise ValueError(f"Got {len(pixel)} colour values.")

                image_data.extend([r, g, b])
            if xafter > 0:
                image_data.extend([0, 0, 0] * xafter)
        if yafter > 0:
            image_data.extend([0, 0, 0] * 64 * yafter)
    sys.stdout.write(f"Album art size: {len(image_data)}\n")
    return struct.pack("B" * (expected_size), *image_data)


def xml_get_text(nodelist):
    rc = []
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc.append(node.data)
    return ''.join(rc)


if __name__ == "__main__":
    import time
    handler = SonosHandler()

    while True:
        if handler.has_track_changed():
            print("Track changed:", handler.track_info)
        elif handler.show_quick():
            print("Show quick:", handler.track_info)
        else:
            print("No change:", handler.track_info)

        sys.stdout.flush()
        time.sleep(5)
