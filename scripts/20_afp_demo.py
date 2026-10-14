"""
Step 20: build a synthetic multi-document AFP print stream from the generated corpus,
anonymise it in place and render before/after pages for slides.

Output (examples/afp/):
  demo_original.afp        3 patient documents DE/FR/IT, page groups + TLE index tags
  demo_anonymised.afp      same file after masking (same size, same structure)
  demo_original_pN.png     rendered text layer per page, PII highlighted
  demo_anonymised_pN.png
  demo_side_by_side.png    page 1 before/after, slide-ready
  demo_report.txt          what was found and masked

No real persons: every value comes from scripts/01_generate.py (Faker + templates).
Usage: python scripts/20_afp_demo.py [pipeline]      default B_presidio_pp
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as cfg
from deidlab.afp import AfpWriter, layout_text, mask_document, read_text
from deidlab.afp_render import measure_factory, render, side_by_side
from deidlab.pipelines import build, merge

pipe_name = sys.argv[1] if len(sys.argv) > 1 else "B_presidio_pp"
out_dir = cfg.PROJECT_ROOT / "examples" / "afp"
out_dir.mkdir(parents=True, exist_ok=True)

docs = [json.loads(l) for l in open(cfg.DOCS_JSONL, encoding="utf-8")]
by_key = {(d["lang"], d["doc_type"]): d for d in reversed(docs)}   # first of each kind
picked = [by_key[("de", "discharge")], by_key[("fr", "lab")], by_key[("it", "referral")]]


def first(d, label):
    for s in d["spans"]:
        if s["label"] == label:
            return d["text"][s["start"]:s["end"]]
    return ""


# --- build the print stream ----------------------------------------------------
w = AfpWriter("DEIDDEMO")
measure = measure_factory(w.fonts)
for n, d in enumerate(picked, 1):
    pid = first(d, "PATIENT_ID") or f"{n:08d}"
    group = f"G{pid[:7]}"
    w.begin_group(group, {"PatientName": first(d, "PERSON"), "PatientID": pid,
                          "AHV": first(d, "AHV_NUMBER"), "DocType": d["doc_type"], "Lang": d["lang"]})
    frags, y_end = layout_text(d["text"], measure, title_lines=1)
    # print-stream style footer: job id, page group, sequence number
    frags.append((1440, 16200, 1, f"JOB 2026-10-14 DEIDDEMO  PID {pid}  SEQ {n:06d}  1/1"))
    w.page(frags)
    w.end_group(group)
original = w.tobytes()
(out_dir / "demo_original.afp").write_bytes(original)

# --- anonymise -----------------------------------------------------------------
pipe = build(pipe_name, cfg)
lang_of_page = {i + 1: d["lang"] for i, d in enumerate(picked)}


def detect(text):
    # one pipeline call per page so each language gets its own NER model
    spans, offset = [], 0
    for i, page in enumerate(text.split("\n\f\n"), 1):
        for s in merge(pipe.analyze(page, lang_of_page.get(i, "de"))):
            s.start += offset; s.end += offset
            spans.append(s)
        offset += len(page) + 3
    return spans


masked, report = mask_document(original, detect, width=measure)
(out_dir / "demo_anonymised.afp").write_bytes(masked)
assert len(masked) == len(original)

# --- render ----------------------------------------------------------------------
before, after = read_text(original), read_text(masked)
masked_pos = {a.fpos for a, b in zip(before.fragments, after.fragments) if a.text != b.text}


def hl_before(f):
    return "#ffd6d6" if f.fpos in masked_pos else None


def hl_after(f):
    return "#d6f0d6" if f.fpos in masked_pos else None


pages_a = render(original, highlight=hl_before)
pages_b = render(masked, highlight=hl_after)
for i, (a, b) in enumerate(zip(pages_a, pages_b), 1):
    a.save(out_dir / f"demo_original_p{i}.png")
    b.save(out_dir / f"demo_anonymised_p{i}.png")
side_by_side(pages_a[0], pages_b[0]).save(out_dir / "demo_side_by_side.png")

# --- report ------------------------------------------------------------------------
lines = [f"pipeline {pipe_name}, codepage {report['codepage']}, pages {report['pages']}, "
         f"text fragments {report['fragments']}",
         f"bytes masked: text {report['bytes_text']}, tags (TLE/BNG/ENG/NOP) {report['bytes_tags']}",
         f"file size before/after: {len(original)} / {len(masked)}", "", "spans found:"]
lines += [f"  {lab:15s} {val}" for lab, val in report["spans"]]
lines += ["", "index tags after masking:"]
lines += [f"  {t.kind:3s} {t.name:12s} {t.value!r}" for t in after.tags]
(out_dir / "demo_report.txt").write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
print("\nwritten to", out_dir)
