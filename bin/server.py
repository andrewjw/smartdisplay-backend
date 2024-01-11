#!/usr/bin/python3

import socketserver
import os
import sys

import sentry_sdk  # type:ignore

from smartdisplay import SmartDisplayHandler


def main(port) -> None:
    sentry_sdk.init(
        dsn=os.environ.get("SENTRY_DSN"),
        traces_sample_rate=0.0,
        profiles_sample_rate=0.0,
    )

    with socketserver.TCPServer(("", port), SmartDisplayHandler) as httpd:
        httpd.allow_reuse_address = True
        print("serving at port", port)
        httpd.serve_forever()


if __name__ == "__main__":
    main(int(sys.argv[1]))
