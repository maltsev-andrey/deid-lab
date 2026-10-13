#!/usr/bin/env bash
# Full cycle: generate corpus -> run pipelines A/B -> evaluate -> report.
# Run inside the "deid" conda environment.
set -euo pipefail
cd "$(dirname "$0")"

python scripts/01_generate.py
python scripts/02_run_and_evaluate.py
python scripts/03_report.py
