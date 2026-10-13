"""Step 2: run every pipeline over the corpus, write predictions, masked samples and metrics."""
import csv
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as cfg
from deidlab.evaluate import evaluate, groups_of, summarize
from deidlab.pipelines import build, mask, merge


def write_csv(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


docs = [json.loads(l) for l in open(cfg.DOCS_JSONL, encoding="utf-8")]
print(f"dataset {cfg.DATASET}: loaded {len(docs)} documents")

for name in cfg.PIPELINES:
    out = cfg.RUNS_DIR / name
    (out / "masked").mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    pipe = build(name, cfg)
    load_s = time.perf_counter() - t0

    preds, t_doc = {}, []
    for d in docs:
        t = time.perf_counter()
        preds[d["id"]] = pipe.analyze(d["text"], d["lang"])
        t_doc.append(time.perf_counter() - t)

    with open(out / "predictions.jsonl", "w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps({"id": d["id"], "spans": [s.as_dict() for s in preds[d["id"]]]},
                               ensure_ascii=False) + "\n")

    per_lang = Counter()
    cap = cfg.MASKED_SAMPLE_PER_LANG
    for d in docs:
        if cap is None or per_lang[d["lang"]] < cap:
            (out / "masked" / f"{d['id']}.txt").write_text(mask(d["text"], preds[d["id"]]), encoding="utf-8")
            per_lang[d["lang"]] += 1

    gold_rows, fp_rows = evaluate(docs, preds, cfg.FULL_COVERAGE)
    n_pred = defaultdict(int)
    for d in docs:
        n = len(merge(preds[d["id"]]))
        for g in groups_of({"lang": d["lang"], "split": d.get("split", "")}):
            n_pred[g] += n
    table, prec = summarize(gold_rows, fp_rows, n_pred)

    leaks = [r for r in gold_rows if r["status"] != "FULL"]
    leaks.sort(key=lambda r: (r["status"] != "MISSED", r["label"], r["lang"]))
    write_csv(out / "metrics_by_entity.csv", table)
    write_csv(out / "leaks.csv", leaks[: cfg.LEAK_REPORT_TOP_N])
    fp_counts = Counter((r["lang"], r["label"], r["value"]) for r in fp_rows)
    write_csv(out / "false_positives_top.csv",
              [{"lang": k[0], "label": k[1], "value": k[2], "count": v} for k, v in fp_counts.most_common(200)])

    total_s = sum(t_doc)
    summary = {
        "pipeline": name, "documents": len(docs), "model_load_s": round(load_s, 2),
        "analyze_total_s": round(total_s, 2), "ms_per_doc": round(1000 * total_s / len(docs), 1),
        "docs_per_s": round(len(docs) / total_s, 1),
        "overall": next(r for r in table if r["lang"] == "ALL" and r["label"] == "ALL"),
        "precision": prec,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    o = summary["overall"]
    print(f"\n=== {name} ===")
    print(f"load {load_s:.1f}s | {summary['ms_per_doc']} ms/doc | {summary['docs_per_s']} docs/s")
    print(f"gold {o['gold']} | full {o['full']} | partial {o['partial']} | missed {o['missed']}")
    print(f"recall strict {o['recall_strict']:.3f} | lenient {o['recall_lenient']:.3f} | "
          f"precision {prec['ALL']['precision']:.3f} ({prec['ALL']['false_pos']} FP of {prec['ALL']['predicted']})")
    for sp in ("dev", "test"):
        row = next((r for r in table if r["lang"] == sp and r["label"] == "ALL"), None)
        if row:
            print(f"  [{sp:<4}] gold {row['gold']:>5} | recall strict {row['recall_strict']:.3f} | "
                  f"lenient {row['recall_lenient']:.3f} | precision {prec[sp]['precision']:.3f} "
                  f"({prec[sp]['false_pos']} FP of {prec[sp]['predicted']})")
    print(f"{'label':<15} {'gold':>6} {'strict':>8} {'lenient':>8}")
    for r in table:
        if r["lang"] == "ALL" and r["label"] != "ALL":
            print(f"{r['label']:<15} {r['gold']:>6} {r['recall_strict']:>8.3f} {r['recall_lenient']:>8.3f}")
