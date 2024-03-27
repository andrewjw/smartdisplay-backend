#!/usr/bin/python3

from datetime import datetime
from functools import lru_cache
import io
import math
import struct
import sys
from typing import Any, Dict, Optional, List
from xml.dom.minidom import parseString

from PIL import Image
import requests
import soco  # type: ignore


class TrackInfo:
    def __init__(self, track_info: Any, sonos: "SonosHandler") -> None:
        self.created = datetime.utcnow()
        self.artist = track_info["artist"]
        self.album = track_info["album"]
        self.title = track_info["title"]
        self.album_art = track_info["album_art"]
        print(repr(self.album_art))
        if self.album_art is None or len(self.album_art) == 0:
            self.album_art = sonos.fix_album_art_url(track_info)
        if self.album_art is not None and len(self.album_art) > 0:
            try:
                self.album_art_image: Optional[bytes] = \
                    get_album_art(self.album_art)
            except requests.exceptions.ConnectionError as e:
                sys.stderr.write("Error loading Album Art\n")
                sys.stderr.write(str(e))
                self.album_art_image = None
        else:
            print("no album art url :-(")
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
        return f"<TrackInfo {self.artist} {self.title}" + \
               f" {self.album_art_image is not None}>"


class SonosHandler:
    def __init__(self) -> None:
        self.devices: Dict[str, Any] = {}
        self.track_info: Optional[TrackInfo] = None
        self.last_screen = "sonos"
        self.last_display_time: Optional[datetime] = None

    def _get_current_track_info(self) -> Optional[TrackInfo]:
        target = self.get_sonos_device()
        if target is None:
            return None
        transport_info = target.group.coordinator.get_current_transport_info()
        if transport_info['current_transport_state'] != "PLAYING":
            return None

        try:
            return TrackInfo(target.group.coordinator.get_current_track_info(),
                             self)
        except requests.exceptions.ReadTimeout:
            return None

    def get_sonos_device(self) -> Optional[Any]:
        if "Kitchen" not in self.devices:
            self.devices = {device.player_name: device
                            for device in soco.discover(timeout=60)}

        try:
            return self.devices["Kitchen"]
        except KeyError:
            sys.stderr.write("No device Kitchen\n")
            return None

    def has_track_changed(self) -> bool:
        new_info = self._get_current_track_info()
        if new_info is None:
            self.track_info = None
            self.last_display_time = None
            return False
        if self.track_info is None or self.track_info != new_info:
            self.track_info = new_info
            self.last_display_time = datetime.utcnow()
            return True
        if abs((new_info.created - self.track_info.created).total_seconds()) \
           > 60 * 5:
            self.track_info = new_info
            self.last_display_time = datetime.utcnow()
            return True
        return False

    def get_current_album_art(self) -> Optional[bytes]:
        if self.track_info is None:
            return None
        return self.track_info.album_art_image

    def fix_album_art_url(self, track_info) -> Optional[str]:
        if "metadata" not in track_info:
            return None

        xml = parseString(track_info["metadata"])
        tags = xml.getElementsByTagName("upnp:albumArtURI")
        if len(tags) == 0:
            return None

        url = xml_get_text(tags[0].childNodes)

        if not url.startswith("http"):
            device = self.get_sonos_device()
            if device is not None:
                url = f"http://{device.ip_address}{url}"
        return url

    def set_last_screen(self, screen: str) -> None:
        self.last_screen = screen

    def get_last_screen(self) -> str:
        return self.last_screen

    def show_quick(self) -> bool:
        if self.last_display_time is None:
            return False
        if (datetime.utcnow() - self.last_display_time).total_seconds() \
           > 2 * 60:
            self.last_display_time = datetime.utcnow()
            return True
        return False


@lru_cache(maxsize=20)
def get_album_art(art_uri: str) -> Optional[bytes]:
    sys.stderr.write(f"Getting album art {art_uri}\n")
    resp = requests.get(art_uri, stream=True)
    resp.raise_for_status()
    buffer = io.BytesIO()
    try:
        for chunk in resp.iter_content(chunk_size=128):
            buffer.write(chunk)
    except requests.exceptions.ChunkedEncodingError:
        return None
    buffer.seek(0)

    image_data: List[int] = []
    with Image.open(buffer) as im:
        try:
            im.thumbnail((64, 64), Image.Resampling.LANCZOS)
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

    return struct.pack("B" * (64 * 64 * 3), *image_data)


def xml_get_text(nodelist):
    rc = []
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc.append(node.data)
    return ''.join(rc)


if __name__ == "__main__":
    SonosHandler()._get_current_track_info()
