#!/usr/bin/python3

from functools import lru_cache
import io
from typing import Any, Optional, List
from xml.dom.minidom import parseString

from PIL import Image
import requests
import soco  # type: ignore

DEVICES = {device.player_name: device for device in soco.discover(timeout=60)}

TRACK_INFO = None


class TrackInfo:
    def __init__(self, track_info: Any) -> None:
        self.artist = track_info["artist"]
        self.album = track_info["album"]
        self.title = track_info["title"]
        self.album_art = track_info["album_art"]
        if self.album_art is None or len(self.album_art) == 0:
            self.album_art = fix_album_art_url(track_info)
        if self.album_art is not None and len(self.album_art) > 0:
            try:
                self.album_art_image: Optional[List[List[int]]] = \
                    get_album_art(self.album_art)
            except requests.exceptions.ConnectionError as e:
                print("Error loading Album Art")
                print(e)
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


def get_current_track_info() -> Optional[TrackInfo]:
    target = get_sonos_device()
    if target is None:
        return None
    transport_info = target.group.coordinator.get_current_transport_info()
    if transport_info['current_transport_state'] != "PLAYING":
        return None

    return TrackInfo(target.group.coordinator.get_current_track_info())


def get_sonos_device() -> Optional[Any]:
    try:
        return DEVICES["Kitchen"]
    except KeyError:
        print("No device Kitchen")
        return None


def has_track_changed() -> bool:
    global TRACK_INFO

    new_info = get_current_track_info()
    print(TRACK_INFO, new_info)
    if new_info is None:
        TRACK_INFO = None
        return False
    if TRACK_INFO is None or TRACK_INFO != new_info:
        TRACK_INFO = new_info
        return True
    print("no change")
    return False


def get_current_album_art() -> Optional[List[List[int]]]:
    if TRACK_INFO is None:
        return None
    return TRACK_INFO.album_art_image


@lru_cache(maxsize=20)
def get_album_art(art_uri: str) -> List[List[int]]:
    print(f"Getting album art {art_uri}")
    resp = requests.get(art_uri, stream=True)
    resp.raise_for_status()
    buffer = io.BytesIO()
    for chunk in resp.iter_content(chunk_size=128):
        buffer.write(chunk)
    buffer.seek(0)

    image_data: List[List[int]] = []
    with Image.open(buffer) as im:
        im.thumbnail((64, 64))
        for y in range(64):
            image_data.append([])
            for x in range(64):
                r, g, b = im.getpixel((x, y))
                image_data[y].append(r << 24 | g << 16 | b << 8 | 255)

    return image_data


def fix_album_art_url(track_info) -> Optional[str]:
    if "metadata" not in track_info:
        return None

    xml = parseString(track_info["metadata"])
    tags = xml.getElementsByTagName("upnp:albumArtURI")
    if len(tags) == 0:
        return None

    url = xml_get_text(tags[0].childNodes)

    if not url.startswith("http"):
        device = get_sonos_device()
        if device is not None:
            url = f"http://{device.ip_address}{url}"
    return url


def xml_get_text(nodelist):
    rc = []
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc.append(node.data)
    return ''.join(rc)


if __name__ == "__main__":
    get_current_track_info()
