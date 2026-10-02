#!/usr/bin/env bash
set -euo pipefail
# These tests validate only the example and controller, NOT your business application.
python3 -m unittest discover -s tests -v
