#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
echo "Starting GPS Driver Simulator..."
../gdg/bin/python simulate.py --url http://127.0.0.1:8080/location --speedup 4 "$@"

