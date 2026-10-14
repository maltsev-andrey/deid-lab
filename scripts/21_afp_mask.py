"""
Step 21: anonymise AFP print streams in place.

    python scripts/21_afp_mask.py <in.afp | in_dir> <out_dir> [--pipeline B_presidio_pp]
                                  [--lang de] [--codepage cp500] [--dump-text] [--render]

For every *.afp in the input, writes <out_dir>/<name>.afp with the same size and structure,
PII bytes in the text layer, TLE index tags, page-group names and comments replaced by
config.AFP_FILLER. A JSON report per file and a summary CSV go to <out_dir>/reports/.

--dump-text   also writes the reconstructed text layer before/after (for review)
--render      also renders every page to PNG before/after (needs Pillow)

Settings: config.AFP_* (pipeline, language, code page, symbol fonts, zones).
"""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as cfg
from deidlab.afp import mask_document, read_text
from deidlab.pipelines import build, merge

ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("out")
ap.add_argument("--pipeline", default=cfg.AFP_PIPELINE)
ap.add_argument("--lang", default=cfg.AFP_LANG)
ap.add_argument("--codepage", default=cfg.AFP_CODEPAGE)
ap.add_argument("--dump-text", action="store_true")
ap.add_argument("--render", action="store_true")
args = ap.parse_args()

src = Path(args.src)
files = sorted(src.glob("*.afp")) + sorted(src.glob("*.AFP")) if src.is_dir() else [src]
if not files:
    sys.exit(f"no .afp files in {src}")
out = Path(args.out)
(out / "reports").mkdir(parents=True, exist_ok=True)

t0 = time.perf_counter()
pipe = build(args.pipeline, cfg)
print(f"pipeline {args.pipeline} loaded in {time.perf_counter() - t0:.1f}s, {len(files)} file(s)")


def detect(text):
    spans, offset = [], 0
    for page in text.split("\n\f\n"):          # one call per page keeps NER inputs short
        for s in merge(pipe.analyze(page, args.lang)):
            s.start += offset; s.end += offset
            spans.append(s)
        offset += len(page) + 3
    return spans


rows = []
for f in files:
    t = time.perf_counter()
    data = f.read_bytes()
    try:
        masked, rep = mask_document(data, detect, codepage=args.codepage, filler=cfg.AFP_FILLER,
                                    zones=cfg.AFP_ZONES, mask_tags=cfg.AFP_MASK_TAGS,
                                    symbol_fonts=cfg.AFP_SYMBOL_FONTS)
    except ValueError as e:
        print(f"  {f.name}: SKIPPED, not a MO:DCA stream ({e})")
        rows.append({"file": f.name, "status": "skipped", "error": str(e)})
        continue
    assert len(masked) == len(data)
    (out / f.name).write_bytes(masked)
    dt = time.perf_counter() - t
    by_label = {}
    for lab, _ in rep["spans"]:
        by_label[lab] = by_label.get(lab, 0) + 1
    row = {"file": f.name, "status": "ok", "pages": rep["pages"], "codepage": rep["codepage"],
           "fragments": rep["fragments"], "spans": len(rep["spans"]), "bytes_text": rep["bytes_text"],
           "bytes_tags": rep["bytes_tags"], "bytes_zones": rep["bytes_zones"], "seconds": round(dt, 2),
           **{f"n_{k}": v for k, v in sorted(by_label.items())}}
    rows.append(row)
    (out / "reports" / f"{f.stem}.json").write_text(json.dumps({**row, "spans": rep["spans"], "fonts": {str(k): v for k, v in rep["fonts"].items()}},
                                                               ensure_ascii=False, indent=1), encoding="utf-8")
    if args.dump_text:
        (out / "reports" / f"{f.stem}.before.txt").write_text(read_text(data, args.codepage).page_text()[0], encoding="utf-8")
        (out / "reports" / f"{f.stem}.after.txt").write_text(read_text(masked, args.codepage).page_text()[0], encoding="utf-8")
    if args.render:
        from deidlab.afp_render import render
        for i, (a, b) in enumerate(zip(render(data), render(masked)), 1):
            a.save(out / "reports" / f"{f.stem}.p{i}.before.png")
            b.save(out / "reports" / f"{f.stem}.p{i}.after.png")
    print(f"  {f.name}: {rep['pages']} page(s), {rep['codepage']}, {len(rep['spans'])} spans, "
          f"{rep['bytes_text']} text bytes + {rep['bytes_tags']} tag bytes masked, {dt:.2f}s")
    if rep["symbol_candidates"]:
        names = {i: rep["fonts"].get(i, (None, "?"))[1] for i in rep["symbol_candidates"]}
        print(f"    WARNING: text in fonts without a code page (barcode/OMR?): {names} "
              f"-> add to config.AFP_SYMBOL_FONTS after checking in the viewer")
        row["symbol_candidates"] = " ".join(str(i) for i in rep["symbol_candidates"])

keys = sorted({k for r in rows for k in r})
with open(out / "reports" / "summary.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=keys)
    w.writeheader(); w.writerows(rows)
print(f"done: {sum(r['status'] == 'ok' for r in rows)}/{len(rows)} files, reports in {out / 'reports'}")
