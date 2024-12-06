#!/usr/bin/python3

from functools import lru_cache
import re
import math
import struct
from typing import Optional, List

from PIL import Image


@lru_cache(maxsize=20)
def load_image(art_uri: str) -> Optional[bytes]:
    if not re.match(r"\w+.png|\w+/\w+.png", art_uri):
        print(f"Invalid url {art_uri}")
        return None

    image_data: List[int] = []
    with Image.open(open("images/"+art_uri, "rb")) as im:
        if im.width > 64 or im.height > 64:
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
                elif len(pixel) == 4:
                    r, g, b, _ = pixel
                else:
                    raise ValueError(f"Got {len(pixel)} colour values.")

                image_data.extend([r, g, b])
            if xafter > 0:
                image_data.extend([0, 0, 0] * xafter)
        if yafter > 0:
            image_data.extend([0, 0, 0] * 64 * yafter)

    return struct.pack("B" * (64 * 64 * 3), *image_data)
