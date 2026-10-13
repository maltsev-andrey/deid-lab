"""Step 11: convert ai4privacy (open-pii-masking-500k validation split) to deid-lab docs.jsonl.

Samples AI4PRIVACY_PER_LANG texts per language (de/fr/it) and maps the ai4privacy
labels onto the deid-lab catalog. Labels outside our catalog (TITLE, SEX, AGE, TIME)
are not scored and are reported in import_stats.json instead.

Note: these texts are generic (forms, mails, chats from many countries), not
medical and not Swiss. They test how well the pipelines generalise.
After this script: set DATASET = "ai4privacy" in config.py and run steps 02 and 03.
"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as cfg

SRC = cfg.EXTERNAL_RAW / "ai4privacy" / "test.jsonl"
DST_DIR = cfg.PROJECT_ROOT / "data" / "ai4privacy"

LABEL_MAP = {
    "GIVENNAME": "PERSON", "SURNAME": "PERSON",
    "DATE": "DATE",
    "CITY": "LOCATION", "ZIPCODE": "LOCATION",
    "STREET": "STREET_ADDRESS", "BUILDINGNUM": "STREET_ADDRESS",
    "TELEPHONENUM": "PHONE", "EMAIL": "EMAIL",
    "SOCIALNUM": "NATIONAL_ID", "IDCARDNUM": "NATIONAL_ID", "PASSPORTNUM": "NATIONAL_ID",
    "DRIVERLICENSENUM": "NATIONAL_ID", "TAXNUM": "NATIONAL_ID",
    "CREDITCARDNUMBER": "CREDIT_CARD",
    "ORGANISATIONPLACEHOLDER": "ORGANIZATION",
    # outside catalog v0.1: not scored
    "TITLE": None, "SEX": None, "GENDER": None, "AGE": None, "TIME": None,
}

if not SRC.exists():
    sys.exit(f"missing {SRC} - run scripts/10_fetch_external.py first")

rng = random.Random(cfg.RANDOM_SEED)
pool = {l: [] for l in cfg.LANGUAGES}
for line in open(SRC, encoding="utf-8"):
    r = json.loads(line)
    if r.get("language") in pool:
        pool[r["language"]].append(r)

stats = {"source_rows": {l: len(v) for l, v in pool.items()}, "kept_labels": Counter(),
         "unscored_labels": Counter(), "unknown_labels": Counter(), "offset_mismatch": 0}
docs = []
for lang, rows in pool.items():
    for r in rng.sample(rows, min(cfg.AI4PRIVACY_PER_LANG, len(rows))):
        text, spans = r["source_text"], []
        for m in r.get("privacy_mask") or []:
            src_label = m["label"]
            if src_label not in LABEL_MAP:
                stats["unknown_labels"][src_label] += 1
                continue
            label = LABEL_MAP[src_label]
            if label is None:
                stats["unscored_labels"][src_label] += 1
                continue
            s, e = int(m["start"]), int(m["end"])
            if text[s:e] != m.get("value", text[s:e]):
                stats["offset_mismatch"] += 1
                continue
            spans.append({"start": s, "end": e, "label": label})
            stats["kept_labels"][label] += 1
        docs.append({"id": f"{lang}-ai4p-{r.get('uid', len(docs))}", "lang": lang,
                     "doc_type": "ai4privacy", "text": text, "spans": spans})

DST_DIR.mkdir(parents=True, exist_ok=True)
(DST_DIR / "txt").mkdir(exist_ok=True)
with open(DST_DIR / "docs.jsonl", "w", encoding="utf-8") as f:
    for d in docs:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")
        (DST_DIR / "txt" / f"{d['id']}.txt").write_text(d["text"], encoding="utf-8")
(DST_DIR / "import_stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")

per_lang = Counter(d["lang"] for d in docs)
print(f"documents : {len(docs)}  ({', '.join(f'{l}={per_lang[l]}' for l in pool)})")
print(f"gold spans: {sum(stats['kept_labels'].values())}")
for k, v in stats["kept_labels"].most_common():
    print(f"  {k:<15} {v:>6}")
print(f"not scored: {dict(stats['unscored_labels'])}")
if stats["unknown_labels"]:
    print(f"UNKNOWN labels (add to LABEL_MAP): {dict(stats['unknown_labels'])}")
print(f"offset mismatches skipped: {stats['offset_mismatch']}")
print(f"written   : {DST_DIR / 'docs.jsonl'}")
