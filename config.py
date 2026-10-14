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
# Stage 2 adds C_gliner (transformer PII model) and D_union (B + C). Both need torch + gliner
# (requirements-c.txt); the default list runs without them. Override per run:
#   DEID_PIPELINES=B_presidio_pp,C_gliner,C_gliner_pp ./run_eval.sh   (D_union = B+C, optional)
PIPELINES = ["A_regex", "A_regex_pp", "B_presidio", "B_presidio_pp"]
if os.environ.get("DEID_PIPELINES"):
    PIPELINES = [p.strip() for p in os.environ["DEID_PIPELINES"].split(",") if p.strip()]

# spaCy models used by pipeline B. "lg" gives the best NER on CPU.
# Swap to *_md for faster runs on small VMs (lower recall on PERSON/LOCATION).
SPACY_MODELS = {
    "de": "de_core_news_lg",
    "fr": "fr_core_news_lg",
    "it": "it_core_news_lg",
}
PRESIDIO_SCORE_THRESHOLD = 0.35

# --- Pipeline C: GLiNER PII (stage 2) ----------------------------------------
# Zero-shot span model: the keys below are the *prompts* the model sees, the values are our
# catalog labels. Change the wording, not the code, to tune what it looks for.
GLINER_MODEL = os.environ.get("DEID_GLINER_MODEL", "urchade/gliner_multi_pii-v1")
GLINER_LABELS = {
    "person":                     "PERSON",
    "date":                       "DATE",
    "date of birth":              "DATE",
    "phone number":               "PHONE",
    "email":                      "EMAIL",
    "street address":             "STREET_ADDRESS",
    "city":                       "LOCATION",
    "postal code":                "LOCATION",
    "organization":               "ORGANIZATION",
    "hospital":                   "ORGANIZATION",
    "patient id":                 "PATIENT_ID",
    "case number":                "PATIENT_ID",
    "social security number":     "AHV_NUMBER",
    "health insurance number":    "INSURANCE_CARD",
    "iban":                       "IBAN",
}
GLINER_THRESHOLD = float(os.environ.get("DEID_GLINER_THRESHOLD", "0.5"))
GLINER_MAX_WORDS = 180            # chunk size; the model truncates above 384 word tokens
TORCH_THREADS    = int(os.environ.get("DEID_TORCH_THREADS", "0")) or None   # None = torch default
MODEL_CACHE_DIR  = PROJECT_ROOT / "models"    # Hugging Face download cache, git-ignored
# Air-gapped hosts: DEID_OFFLINE=1 forbids every network call of huggingface_hub, so a
# missing checkpoint fails fast instead of hanging on a connect timeout.
if os.environ.get("DEID_OFFLINE", "0") == "1":
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# --- AFP print streams (stage 2) -----------------------------------------------
# scripts/21_afp_mask.py masks AFP files in place (deidlab/afp.py). Client-specific knobs:
AFP_PIPELINE     = os.environ.get("DEID_AFP_PIPELINE", "B_presidio_pp")
AFP_LANG         = os.environ.get("DEID_AFP_LANG", "de")     # NER language for the text layer
AFP_CODEPAGE     = os.environ.get("DEID_AFP_CODEPAGE") or None   # None = detect from MCF, else "cp500"/"cp1141"
AFP_FILLER       = "X"
AFP_SYMBOL_FONTS = ()        # local font ids whose text is barcode/OMR glyphs, e.g. (7,) ; blanked with spaces
AFP_ZONES        = []        # [(x0, y0, x1, y1), ...] in 1/1440 inch, masked unconditionally (recipient window)
AFP_MASK_TAGS    = True      # TLE / BNG / ENG / NOP

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
