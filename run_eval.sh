#!/usr/bin/env bash
# Run pipelines + evaluation + report on the dataset selected in config.py
# (or override: DEID_DATASET=ai4privacy ./run_eval.sh). Does not regenerate data.
set -euo pipefail
cd "$(dirname "$0")"
python scripts/02_run_and_evaluate.py
python scripts/03_report.py
