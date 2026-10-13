"""Step 1: generate the synthetic corpus with gold spans."""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as cfg
from deidlab.generator import generate_corpus

cfg.DATA_DIR.mkdir(parents=True, exist_ok=True)
cfg.DOCS_TXT_DIR.mkdir(parents=True, exist_ok=True)

docs = generate_corpus(cfg.LANGUAGES, cfg.DOC_TYPES, cfg.DOCS_PER_LANG, cfg.RANDOM_SEED)

with open(cfg.DOCS_JSONL, "w", encoding="utf-8") as f:
    for d in docs:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")
for d in docs:
    (cfg.DOCS_TXT_DIR / f"{d['id']}.txt").write_text(d["text"], encoding="utf-8")

labels = Counter(s["label"] for d in docs for s in d["spans"])
per_lang = Counter(d["lang"] for d in docs)
print(f"documents : {len(docs)}  ({', '.join(f'{l}={per_lang[l]}' for l in cfg.LANGUAGES)})")
print(f"gold spans: {sum(labels.values())}")
for k, v in labels.most_common():
    print(f"  {k:<15} {v:>6}")
print(f"written   : {cfg.DOCS_JSONL}")
