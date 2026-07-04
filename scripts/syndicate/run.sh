#!/usr/bin/env sh
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR/.." && exec "$DIR/venv/bin/python3" -m syndicate "$@"
