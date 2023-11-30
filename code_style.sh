#!/bin/bash

set -e

mypy -m smartdisplay

mypy bin/server.py

${PYCODESTYLE:-pycodestyle} bin/server.py smartdisplay/
