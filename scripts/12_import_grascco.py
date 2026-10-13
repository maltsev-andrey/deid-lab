"""Step 12: convert GraSCCo_PII (Zenodo, INCEpTION export) to deid-lab docs.jsonl.

GraSCCo is a set of synthetic German clinical letters with manually curated PII
annotations (GeMTeX project). It is the independent benchmark: neither the texts
nor the annotations were written by us, so it shows how the pipelines generalise.

The INCEpTION layer and feature names are not documented, so this script discovers
them: it loads TypeSystem.xml, finds the custom annotation types, and builds each
label from the string features of an annotation (e.g. "NAME" + "PATIENT").
Run with INSPECT_ONLY = True first if the import reports zero spans.

After this script: set DATASET = "grascco" in config.py (or DEID_DATASET=grascco)
and run ./run_eval.sh
"""
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as cfg

from cassis import load_cas_from_json, load_cas_from_xmi, load_typesystem

RAW = cfg.EXTERNAL_RAW / "grascco"
WORK = RAW / "extracted"
DST_DIR = cfg.PROJECT_ROOT / "data" / "grascco"
INSPECT_ONLY = False        # True: print type system + label inventory, write nothing

# Built-in / technical UIMA and DKPro types that never carry PII labels
SKIP_TYPE_PREFIXES = ("uima.", "de.tudarmstadt.ukp.dkpro.core.api.segmentation", "de.tudarmstadt.ukp.dkpro.core.api.metadata",
                      "de.tudarmstadt.ukp.clarin.webanno.api", "de.tudarmstadt.ukp.inception", "webanno.custom.Relation")


def map_label(raw: str):
    """GraSCCo label (e.g. 'NAME_PATIENT', 'LOCATION CITY') -> deid-lab catalog label.
    None = known category outside catalog v0.1, not scored."""
    u = raw.upper()
    if "TITLE" in u:                     return None          # "Dr.", "Prof." - not PII on their own
    if "PROFESSION" in u:                return None
    if "AGE" in u:                       return None
    if "COUNTRY" in u:                   return None          # Safe Harbor keeps country
    if "NAME" in u or "USERNAME" in u:   return "PERSON"
    if "DATE" in u:                      return "DATE"
    if "STREET" in u:                    return "STREET_ADDRESS"
    if "ZIP" in u or "CITY" in u:        return "LOCATION"
    if "HOSPITAL" in u or "ORGANI" in u: return "ORGANIZATION"
    if "EMAIL" in u or "MAIL" in u:      return "EMAIL"
    if "PHONE" in u or "FAX" in u:       return "PHONE"
    if re.search(r"\bID\b|_ID\b|^ID", u): return "PATIENT_ID"
    if "LOCATION" in u:                  return "LOCATION"
    if "CONTACT" in u:                   return "PHONE"
    if "OTHER" in u:                     return "OTHER"
    return "UNMAPPED:" + raw


def extract_archives():
    WORK.mkdir(parents=True, exist_ok=True)
    for z in RAW.glob("*.zip"):
        target = WORK / z.stem
        if not target.exists():
            with zipfile.ZipFile(z) as zf:
                for m in zf.namelist():                         # guard against path traversal
                    if m.startswith("/") or ".." in Path(m).parts:
                        sys.exit(f"unsafe path in {z.name}: {m}")
                zf.extractall(target)
            # nested zips (INCEpTION exports often zip per document)
            for inner in target.rglob("*.zip"):
                with zipfile.ZipFile(inner) as zf:
                    zf.extractall(inner.with_suffix(""))


def find(pattern):
    return sorted({p for base in (RAW, WORK) for p in base.rglob(pattern)})


def candidate_types(ts):
    out = []
    for t in ts.get_types():
        if t.name.startswith(SKIP_TYPE_PREFIXES):
            continue
        feats = [f for f in t.all_features if f.name not in ("begin", "end", "sofa")
                 and f.rangeType.name == "uima.cas.String"]
        if feats:
            out.append((t, feats))
    return out


def label_of(anno, feats):
    vals = [getattr(anno, f.name, None) for f in feats]
    vals = [v.strip() for v in vals if isinstance(v, str) and v.strip()]
    return "_".join(vals) if vals else None


def doc_name(path: Path):
    # INCEpTION project exports store <doc>/<user>.xmi; plain exports store <doc>.xmi
    generic = {"curation_user", "initial_cas", "admin", "inception"}
    return path.parent.name if path.stem.lower() in generic or path.stem.lower().startswith("curation") else path.stem


extract_archives()
# any *typesystem*.xml, any case ("TypeSystem.xml", "GeMTeX_PII_2_Typesystem.xml");
# a top-level file from the Zenodo record wins over copies inside the archives
ts_files = sorted((p for p in find("*.xml") if "typesystem" in p.name.lower()),
                  key=lambda p: (p.parent != RAW, len(p.parts)))
if not ts_files:
    sys.exit(f"no *typesystem*.xml found under {RAW}. Run scripts/10_fetch_external.py first.")
ts = load_typesystem(open(ts_files[0], "rb"))
cands = candidate_types(ts)
print(f"type system: {ts_files[0].relative_to(cfg.PROJECT_ROOT)}")
print("candidate PII layers:")
for t, feats in cands:
    print(f"  {t.name}  features: {[f.name for f in feats]}")

xmis = [p for p in find("*.xmi") if p.stem.upper() != "INITIAL_CAS"]
jsons = [p for p in find("*.json") if p.name != "record.json" and "layer" not in p.name.lower()
         and "exportedproject" not in p.name]
cur = [p for p in xmis if "curation" in str(p).lower()]
xmis = cur or xmis                                       # prefer curated version when present
sources = [("xmi", p) for p in xmis] or [("json", p) for p in jsons]
print(f"documents found: {len(sources)} ({'xmi' if xmis else 'json'})")

raw_labels, docs, seen = Counter(), [], set()
for kind, path in sources:
    name = doc_name(path)
    if name in seen:
        continue
    try:
        cas = load_cas_from_xmi(open(path, "rb"), typesystem=ts, lenient=True) if kind == "xmi" \
            else load_cas_from_json(open(path, "rb"), typesystem=ts)
    except Exception as e:                                  # noqa: BLE001  one bad file must not stop the import
        print(f"  skip {path.name}: {e}")
        continue
    seen.add(name)
    text = cas.sofa_string or ""
    spans = []
    for t, feats in cands:
        for a in cas.select(t.name):
            lab = label_of(a, feats)
            if not lab or a.end <= a.begin:
                continue
            raw_labels[lab] += 1
            m = map_label(lab)
            if m is None:
                continue
            s, e = a.begin, a.end
            while s < e and text[s].isspace():
                s += 1
            while e > s and text[e - 1].isspace():
                e -= 1
            if e > s:
                spans.append({"start": s, "end": e, "label": m, "source_label": lab})
    docs.append({"id": f"de-grascco-{len(docs):03d}-{re.sub(r'[^A-Za-z0-9_-]+', '_', name)[:40]}",
                 "lang": "de", "doc_type": "grascco", "text": text, "spans": spans})

# Deterministic dev/test split by document name: tune rules and filters on "dev",
# quote numbers from "test". Alternating over the name-sorted list keeps both halves
# similar in size and document mix.
for i, d in enumerate(sorted(docs, key=lambda d: d["id"])):
    d["split"] = "dev" if i % 2 == 0 else "test"

print("\nlabel inventory (raw -> catalog):")
for lab, n in raw_labels.most_common():
    print(f"  {lab:<32} {n:>5}  -> {map_label(lab)}")

if INSPECT_ONLY:
    sys.exit("\nINSPECT_ONLY = True, nothing written")
if not docs or not raw_labels:
    sys.exit("\nno annotated documents imported - set INSPECT_ONLY = True and send the output")

DST_DIR.mkdir(parents=True, exist_ok=True)
(DST_DIR / "txt").mkdir(exist_ok=True)
with open(DST_DIR / "docs.jsonl", "w", encoding="utf-8") as f:
    for d in docs:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")
        (DST_DIR / "txt" / f"{d['id']}.txt").write_text(d["text"], encoding="utf-8")
kept = Counter(s["label"] for d in docs for s in d["spans"])
(DST_DIR / "import_stats.json").write_text(json.dumps(
    {"documents": len(docs), "raw_labels": raw_labels, "kept": kept}, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\ndocuments : {len(docs)}  (dev={sum(d['split'] == 'dev' for d in docs)}, test={sum(d['split'] == 'test' for d in docs)})")
print(f"gold spans: {sum(kept.values())}  {dict(kept)}")
unm = {k: v for k, v in kept.items() if k.startswith("UNMAPPED")}
if unm:
    print(f"UNMAPPED labels are scored as-is; extend map_label() if needed: {unm}")
print(f"written   : {DST_DIR / 'docs.jsonl'}")
