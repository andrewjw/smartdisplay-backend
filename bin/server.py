#!/usr/bin/python3

import socketserver
import sys

from smartdisplay import SmartDisplayHandler


def main(port) -> None:
    with socketserver.TCPServer(("", port), SmartDisplayHandler) as httpd:
        httpd.allow_reuse_address = True
        print("serving at port", port)
        httpd.serve_forever()


if __name__ == "__main__":
    main(int(sys.argv[1]))
