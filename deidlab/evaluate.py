"""
Evaluation: what leaked, what was over-masked, per entity and language.

Leak view (what matters for privacy, type-agnostic):
  each gold span is FULL (>= FULL_COVERAGE of its chars masked),
  PARTIAL (some chars masked) or MISSED (nothing masked).
  recall_strict  = FULL / gold
  recall_lenient = (FULL + PARTIAL) / gold

Utility view:
  a predicted (merged) span is a false positive if it overlaps no gold span.
  precision = 1 - FP / predicted
"""
from collections import defaultdict

from .pipelines import merge
from .rules import Span


def coverage(gold, preds, text=None):
    """Share of the gold span's characters covered by predictions. Whitespace inside the
    gold span (line breaks in multi-line institution headers) never counts as a leak."""
    gs, ge = gold["start"], gold["end"]
    hit = bytearray(ge - gs)
    for p in preds:
        lo, hi = max(gs, p.start), min(ge, p.end)
        if hi > lo:
            hit[lo - gs:hi - gs] = b"\x01" * (hi - lo)
    idx = [i for i in range(ge - gs) if text is None or not text[gs + i].isspace()]
    if not idx:
        return 1.0
    return sum(hit[i] for i in idx) / len(idx)


def evaluate(docs, predictions, full_cov=0.999):
    """docs: list of gold docs. predictions: {doc_id: [Span]}"""
    gold_rows, fp_rows = [], []
    for d in docs:
        text = d["text"]
        preds = merge(predictions[d["id"]])
        for g in d["spans"]:
            c = coverage(g, preds, text)
            status = "FULL" if c >= full_cov else ("PARTIAL" if c > 0 else "MISSED")
            ctx_s, ctx_e = max(0, g["start"] - 40), min(len(text), g["end"] + 40)
            gold_rows.append({
                "doc_id": d["id"], "lang": d["lang"], "split": d.get("split", ""), "doc_type": d["doc_type"],
                "label": g["label"], "value": text[g["start"]:g["end"]],
                "coverage": round(c, 3), "status": status,
                "context": text[ctx_s:ctx_e].replace("\n", " | "),
            })
        for p in preds:
            hit = any(min(g["end"], p.end) > max(g["start"], p.start) for g in d["spans"])
            if not hit:
                fp_rows.append({"doc_id": d["id"], "lang": d["lang"], "split": d.get("split", ""), "label": p.label,
                                "value": text[p.start:p.end].replace("\n", " "), "source": p.source})
    return gold_rows, fp_rows


def groups_of(r):
    """Aggregation groups of a row: its language, its split (dev/test) when present, ALL."""
    g = [r["lang"], "ALL"]
    if r.get("split"):
        g.insert(1, r["split"])
    return g


def summarize(gold_rows, fp_rows, n_pred_by_group):
    """Aggregate to per (group, label) and overall tables. Groups are languages,
    dev/test splits and ALL; they all live in the "lang" column."""
    agg = defaultdict(lambda: {"gold": 0, "FULL": 0, "PARTIAL": 0, "MISSED": 0})
    for r in gold_rows:
        for g in groups_of(r):
            for label in (r["label"], "ALL"):
                agg[(g, label)]["gold"] += 1
                agg[(g, label)][r["status"]] += 1
    out = []
    for (lang, label), v in sorted(agg.items()):
        out.append({
            "lang": lang, "label": label, "gold": v["gold"],
            "full": v["FULL"], "partial": v["PARTIAL"], "missed": v["MISSED"],
            "recall_strict": round(v["FULL"] / v["gold"], 4),
            "recall_lenient": round((v["FULL"] + v["PARTIAL"]) / v["gold"], 4),
        })
    fp_by_lang = defaultdict(int)
    for r in fp_rows:
        for g in groups_of(r):
            fp_by_lang[g] += 1
    prec = {}
    for lang, n in n_pred_by_group.items():
        prec[lang] = {"predicted": n, "false_pos": fp_by_lang[lang],
                      "precision": round(1 - fp_by_lang[lang] / n, 4) if n else 0.0}
    return out, prec
