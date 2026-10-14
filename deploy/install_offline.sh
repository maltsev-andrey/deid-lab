#!/usr/bin/env bash
# Install the offline bundle on a clean air-gapped RHEL 9 host. No network access needed.
#
#   sudo deploy/install_offline.sh /path/to/bundle [/opt/deid]
#
# Afterwards:  source /opt/deid/env/bin/activate ; cd /opt/deid/deid-lab ; ./run_all.sh
set -euo pipefail
BUNDLE="${1:?usage: install_offline.sh <bundle dir> [install dir]}"
PREFIX="${2:-/opt/deid}"

echo "== 1/5 verify checksums"
( cd "$BUNDLE" && sha256sum -c SHA256SUMS )

echo "== 2/5 system packages (base RHEL 9 only; nothing from EPEL)"
# glibc, libstdc++, libgomp, zlib, bzip2, tar are in a minimal install; check instead of assume
for lib in libstdc++.so.6 libgomp.so.1 libz.so.1; do
    ldconfig -p | grep -q "$lib" || { echo "missing $lib: dnf install libstdc++ libgomp zlib"; exit 1; }
done

echo "== 3/5 unpack environment -> $PREFIX/env"
mkdir -p "$PREFIX/env"
tar xzf "$BUNDLE/deid-env.tar.gz" -C "$PREFIX/env"
# conda-pack leaves relocatable prefixes; conda-unpack fixes the shebangs/paths for this host
source "$PREFIX/env/bin/activate"
conda-unpack

echo "== 4/5 unpack project, models, external corpora"
tar xzf "$BUNDLE/deid-lab-src.tar.gz" -C "$PREFIX"
[ -f "$BUNDLE/deid-models.tar.gz" ]   && tar xzf "$BUNDLE/deid-models.tar.gz"   -C "$PREFIX/deid-lab"
[ -f "$BUNDLE/deid-external.tar.gz" ] && mkdir -p "$PREFIX/deid-lab/data" && tar xzf "$BUNDLE/deid-external.tar.gz" -C "$PREFIX/deid-lab/data"
cat > "$PREFIX/env.sh" <<ENV
# source this before using deid-lab on this host
source $PREFIX/env/bin/activate
export DEID_OFFLINE=1
export TOKENIZERS_PARALLELISM=false
ENV

echo "== 5/5 self-test without network"
source "$PREFIX/env.sh"
cd "$PREFIX/deid-lab"
python tests/test_afp.py
python tests/test_gliner_pipeline.py
python -c "import spacy; [spacy.load(m) for m in ('de_core_news_lg','fr_core_news_lg','it_core_news_lg')]; print('spaCy models ok')"
if [ -d models ] && [ -n "$(ls -A models)" ]; then
    python -c "import config as cfg; from deidlab.pipelines import build; build('C_gliner', cfg); print('GLiNER offline ok')"
fi
echo "installed. Next: ./run_all.sh  (synthetic corpus, all pipelines) and scripts/21_afp_mask.py"
