#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
docker build -t luz-token-extractor .
exec docker run --rm -it --network host luz-token-extractor "$@"
