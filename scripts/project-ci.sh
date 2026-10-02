#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Aplikacja używa wyłącznie biblioteki standardowej Python 3.12+ i JavaScript.
# Brak instalacji zależności: nie ma nieprzypiętych pakietów pobieranych w CI.
python3 -m compileall -q gus_app
node --check gus_app/static/app.js
node tests/test_gus_ui.cjs
python3 -m unittest discover -s tests -v
