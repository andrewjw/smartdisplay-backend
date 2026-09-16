#!/bin/bash

set -e

mypy -m smartdisplay

mypy bin/server.py

black --check .
