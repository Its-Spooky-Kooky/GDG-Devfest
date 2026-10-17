#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
echo "Starting Logistics Dispatch Server on http://localhost:8080..."
../gdg/bin/python app.py

