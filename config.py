"""
deid-lab central configuration.

All paths and run parameters live here. Edit and re-run, no CLI flags needed.
"""
import os
from pathlib import Path

# --- Dataset -----------------------------------------------------------------
# Which corpus steps 02 (run + evaluate) and 03 (report) work on:
#   "synthetic"   our generated Swiss documents        (scripts/01_generate.py)
#   "ai4privacy"  external multilingual PII texts       (scripts/11_import_ai4privacy.py)
#   "grascco"     external German clinical letters      (scripts/12_import_grascco.py)
DATASET = os.environ.get("DEID_DATASET", "synthetic")   # env var overrides, e.g. DEID_DATASET=grascco ./run_eval.sh

# --- Paths -------------------------------------------------------------------
# Project root defaults to the directory of this file. On srv-anaconda-01 this
# resolves to /nfs/shared/projects/deid-lab
PROJECT_ROOT = Path(__file__).resolve().parent

CATALOG_FILE   = PROJECT_ROOT / "catalog" / "entities.yaml"
DATA_DIR       = PROJECT_ROOT / "data" / DATASET
DOCS_JSONL     = DATA_DIR / "docs.jsonl"          # text + gold spans, same format for every dataset
DOCS_TXT_DIR   = DATA_DIR / "txt"                 # plain text copies for eyeballing
RUNS_DIR       = PROJECT_ROOT / "runs" / DATASET  # predictions + masked output per pipeline
REPORTS_DIR    = PROJECT_ROOT / "reports" / DATASET
EXTERNAL_RAW   = PROJECT_ROOT / "data" / "external_raw"   # downloads from Zenodo / Hugging Face

# --- Generator (synthetic only) ----------------------------------------------
LANGUAGES         = ["de", "fr", "it"]
DOC_TYPES         = ["discharge", "lab", "referral"]
DOCS_PER_LANG     = 200        # 200 x 3 languages = 600 documents
RANDOM_SEED       = 42

# --- External import ---------------------------------------------------------
AI4PRIVACY_PER_LANG = 500      # sampled texts per language from the validation split

# --- Pipelines ---------------------------------------------------------------
# "<base>_pp" = base pipeline + document-level post-processing
# (deny list, propagation of found values, person linking). See deidlab/postprocess.py
PIPELINES = ["A_regex", "A_regex_pp", "B_presidio", "B_presidio_pp"]

# spaCy models used by pipeline B. "lg" gives the best NER on CPU.
# Swap to *_md for faster runs on small VMs (lower recall on PERSON/LOCATION).
SPACY_MODELS = {
    "de": "de_core_news_lg",
    "fr": "fr_core_news_lg",
    "it": "it_core_news_lg",
}
PRESIDIO_SCORE_THRESHOLD = 0.35

# NER utility filter profile for the *_pp pipelines (deidlab/postprocess.py):
#   "clinical"  for medical letters: also drops uncorroborated single-token names and
#               cities without a locative preposition (+15 points precision on GraSCCo)
#   "generic"   for short non-medical texts (ai4privacy): keeps them (recall first)
FILTER_PROFILE = os.environ.get("DEID_FILTER_PROFILE", "clinical")

# Masked output written per pipeline. None = every document.
MASKED_SAMPLE_PER_LANG = None

# --- Evaluation --------------------------------------------------------------
# A gold span counts as "fully masked" when this fraction of its characters
# is covered by predictions. Anything below is a leak (partial or full).
FULL_COVERAGE = 0.999
LEAK_REPORT_TOP_N = None   # None = write every leak

# Side-by-side HTML viewer (reports/<dataset>/compare.html). Caps size for big corpora.
COMPARE_MAX_DOCS = 600
