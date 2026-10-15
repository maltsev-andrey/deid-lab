#!/usr/bin/env bash
# Build the offline bundle for an air-gapped RHEL 9 host. Run on the BUILD host (internet,
# same architecture, same or older glibc than the target; ideally a RHEL 9 VM) inside the
# conda env that already runs ./run_all.sh and pipeline C.
#
#   conda activate deid
#   deploy/make_offline_bundle.sh /path/to/bundle
#
# Output: <bundle>/deid-env.tar.gz    the whole conda env (python + presidio + spacy models + torch + gliner)
#         <bundle>/deid-lab-src.tar.gz project code, examples, docs (no data/, runs/, .git)
#         <bundle>/deid-models.tar.gz  models/ (GLiNER checkpoint), only if present
#         <bundle>/deid-external.tar.gz data/external_raw (GraSCCo, ai4privacy), only if present
#         <bundle>/SHA256SUMS, MANIFEST.txt
set -euo pipefail
BUNDLE="${1:?usage: make_offline_bundle.sh <bundle dir>}"
PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_NAME="${CONDA_DEFAULT_ENV:-deid}"
mkdir -p "$BUNDLE"

echo "== 1/5 environment check ($ENV_NAME)"
python - <<'PY'
import importlib, sys
mods = ["presidio_analyzer", "spacy", "faker", "pandas", "matplotlib", "PIL", "cassis"]
opt = ["torch", "gliner"]
for m in mods:
    importlib.import_module(m)
missing = [m for m in opt if importlib.util.find_spec(m) is None]
print("python", sys.version.split()[0], "| core ok | optional missing:", missing or "none")
for m in ("de_core_news_lg", "fr_core_news_lg", "it_core_news_lg"):
    assert importlib.util.find_spec(m), f"spaCy model {m} not installed"
PY

echo "== 2/5 conda-pack env -> deid-env.tar.gz (takes a few minutes, ~3 GB)"
python -c "import conda_pack" 2>/dev/null || pip install conda-pack
conda pack -n "$ENV_NAME" -o "$BUNDLE/deid-env.tar.gz" --force

echo "== 3/5 project source"
tar czf "$BUNDLE/deid-lab-src.tar.gz" -C "$(dirname "$PROJECT")" \
    --exclude='deid-lab/data' --exclude='deid-lab/runs' --exclude='deid-lab/.git' \
    --exclude='deid-lab/models' --exclude='__pycache__' --exclude='*.pyc' "$(basename "$PROJECT")"

echo "== 4/5 models and external corpora (optional)"
if [ -d "$PROJECT/models" ] && [ -n "$(ls -A "$PROJECT/models")" ]; then
    tar czf "$BUNDLE/deid-models.tar.gz" -C "$PROJECT" models
else
    echo "   models/ empty: pipeline C will not be available offline (run it once online first)"
fi
if [ -d "$PROJECT/data/external_raw" ]; then
    tar czf "$BUNDLE/deid-external.tar.gz" -C "$PROJECT/data" external_raw
fi

echo "== 5/5 checksums and manifest"
( cd "$BUNDLE" && sha256sum *.tar.gz > SHA256SUMS )
{
  echo "deid-lab offline bundle, built $(date -Is) on $(hostname) ($(cat /etc/redhat-release 2>/dev/null || uname -sr))"
  echo "arch: $(uname -m)  glibc: $(ldd --version | head -1 | awk '{print $NF}')"
  echo "env: $ENV_NAME  python: $(python -c 'import sys;print(sys.version.split()[0])')"
  echo "git: $(git -C "$PROJECT" rev-parse --short HEAD 2>/dev/null || echo n/a)"
  echo; pip list --format=freeze
} > "$BUNDLE/MANIFEST.txt"
ls -la "$BUNDLE"
echo "bundle ready: $BUNDLE"
