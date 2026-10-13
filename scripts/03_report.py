"""Step 3: compare pipelines, write charts (PNG) and a markdown report."""
import csv
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as cfg
from deidlab.evaluate import coverage
from deidlab.pipelines import mask, mask_segments, merge
from deidlab.rules import Span

FIG = cfg.REPORTS_DIR / "figures"
FIG.mkdir(parents=True, exist_ok=True)

# palette: categorical slots 1/2, recessive ink and grid
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
# categorical slots in fixed order, one per pipeline
COLORS = {"A_regex": "#2a78d6", "A_regex_pp": "#1baf7a", "B_presidio": "#eb6834", "B_presidio_pp": "#6250d6"}
LABELS = {"A_regex": "A  regex rules", "A_regex_pp": "A + post-processing",
          "B_presidio": "B  Presidio + spaCy", "B_presidio_pp": "B + post-processing"}
NP = len(cfg.PIPELINES)
HERO_PIPE = "B_presidio_pp" if "B_presidio_pp" in cfg.PIPELINES else cfg.PIPELINES[-1]

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK,
    "text.color": INK, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
    "axes.spines.left": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.axisbelow": True,
})

docs = [json.loads(l) for l in open(cfg.DOCS_JSONL, encoding="utf-8")]
LANGS = [l for l in cfg.LANGUAGES if any(d["lang"] == l for d in docs)]
SPLITS = [sp for sp in ("dev", "test") if any(d.get("split") == sp for d in docs)]
N_GOLD = sum(len(d["spans"]) for d in docs)
CORPUS = f"{len(docs)} {cfg.DATASET} documents ({'/'.join(l.upper() for l in LANGS)})"

summ, tables = {}, {}
for p in cfg.PIPELINES:
    summ[p] = json.loads((cfg.RUNS_DIR / p / "summary.json").read_text(encoding="utf-8"))
    tables[p] = list(csv.DictReader(open(cfg.RUNS_DIR / p / "metrics_by_entity.csv", encoding="utf-8")))


def rec(p, lang, label, key="recall_strict"):
    for r in tables[p]:
        if r["lang"] == lang and r["label"] == label:
            return float(r[key])
    return None


def load_preds(p):
    out = {}
    for line in open(cfg.RUNS_DIR / p / "predictions.jsonl", encoding="utf-8"):
        r = json.loads(line)
        out[r["id"]] = [Span(**{k: s[k] for k in ("start", "end", "label", "score", "source")}) for s in r["spans"]]
    return out


PREDS = {p: load_preds(p) for p in cfg.PIPELINES}

# --- figure 1: strict recall per entity --------------------------------------
labels = sorted({r["label"] for r in tables[cfg.PIPELINES[0]] if r["label"] != "ALL" and r["lang"] == "ALL"},
                key=lambda l: rec(cfg.PIPELINES[0], "ALL", l))
fig, ax = plt.subplots(figsize=(9, 2.2 + 0.18 * NP * len(labels)))
h = 0.84 / NP
for i, p in enumerate(cfg.PIPELINES):
    ys = [k + (i - (NP - 1) / 2) * h for k in range(len(labels))]
    vals = [100 * rec(p, "ALL", l) for l in labels]
    ax.barh(ys, vals, height=h - 0.06, color=COLORS[p], label=LABELS[p])
    for y, v in zip(ys, vals):
        if v < 99.95:
            ax.text(v + 0.8, y, f"{v:.1f}", va="center", fontsize=7.5, color=INK2)
ax.set_yticks(range(len(labels)), labels)
ax.set_xlim(0, 108)
ax.set_xlabel("Gold spans fully masked, %  (strict recall)")
ax.grid(axis="y", visible=False)
ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False)
ax.set_title(f"Recall by entity type, {CORPUS}", loc="left", fontsize=12, pad=46)
fig.tight_layout()
fig.savefig(FIG / "recall_by_entity.png", dpi=150)
plt.close(fig)

# --- figure 2: recall vs precision per language (two panels, one axis each) --
langs = (LANGS if len(LANGS) > 1 else []) + SPLITS + (["ALL"] if len(LANGS) + len(SPLITS) > 1 else [])
fig, axes = plt.subplots(1, 2, figsize=(4 + 2 * len(langs), 4.2), sharey=False)
w = 0.84 / NP
for ax, metric, title in [(axes[0], "recall", "Recall (leak protection)"),
                          (axes[1], "precision", "Precision (data utility)")]:
    for i, p in enumerate(cfg.PIPELINES):
        xs = [k + (i - (NP - 1) / 2) * w for k in range(len(langs))]
        if metric == "recall":
            vals = [100 * rec(p, l, "ALL") for l in langs]
        else:
            vals = [100 * summ[p]["precision"][l]["precision"] for l in langs]
        ax.bar(xs, vals, width=w - 0.06, color=COLORS[p], label=LABELS[p])
        for x, v in zip(xs, vals):
            ax.text(x, v + 1.2, f"{v:.0f}", ha="center", fontsize=7, color=INK2)
    ax.set_xticks(range(len(langs)), [l.upper() for l in langs])
    ax.set_ylim(0, 110)
    ax.grid(axis="x", visible=False)
    ax.set_title(title, loc="left", fontsize=11)
axes[0].set_ylabel("%")
handles, labs = axes[0].get_legend_handles_labels()
fig.legend(handles, labs, loc="upper right", ncol=2 if len(langs) < 3 else NP, frameon=False, fontsize=9)
fig.tight_layout(rect=(0, 0, 1, 0.86 if len(langs) < 3 else 0.92))
fig.savefig(FIG / "recall_precision_by_language.png", dpi=150)
plt.close(fig)

# --- figure 3: hero, original vs masked snippet ------------------------------
short = [d for d in docs if 600 < len(d["text"]) < 2500] or docs
doc = next((d for d in short if d["id"].startswith("de-referral")), None) or max(short[:50], key=lambda d: len(d["spans"]))
import textwrap
wrap = lambda t: "\n".join(textwrap.fill(l, 64) if l else "" for l in t.splitlines()[:22])
orig = wrap(doc["text"])
masked = wrap(mask(doc["text"], PREDS[HERO_PIPE][doc["id"]]))
fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))
for ax, txt, ttl in [(axes[0], orig, f"Input  ({cfg.DATASET})"), (axes[1], masked, f"Output  {LABELS[HERO_PIPE]}")]:
    ax.axis("off")
    ax.set_title(ttl, loc="left", fontsize=11, color=INK2)
    ax.text(0, 1, txt, va="top", ha="left", family="monospace", fontsize=8.2, transform=ax.transAxes)
fig.suptitle("deid-lab  |  Swiss medical document de-identification, CPU only", x=0.01, ha="left",
             fontsize=13, fontweight="bold")
fig.tight_layout()
fig.savefig(FIG / "hero_before_after.png", dpi=150)
plt.close(fig)

# --- markdown report ---------------------------------------------------------
lines = [f"# deid-lab evaluation report: {cfg.DATASET}", "",
         f"Corpus: {CORPUS}, {N_GOLD} gold PII spans."
         + (" Tuning on **dev**, numbers to quote are **test**." if SPLITS else ""), "",
         "| Pipeline | Recall strict | Recall lenient | Precision | False positives | ms/doc | Model load |",
         "|---|---|---|---|---|---|---|"]
for p in cfg.PIPELINES:
    s, o = summ[p], summ[p]["overall"]
    lines.append(f"| {p} | {100*o['recall_strict']:.1f}% | {100*o['recall_lenient']:.1f}% | "
                 f"{100*s['precision']['ALL']['precision']:.1f}% | {s['precision']['ALL']['false_pos']} | "
                 f"{s['ms_per_doc']} | {s['model_load_s']} s |")
if SPLITS:
    lines += ["", "| Pipeline | " + " | ".join(f"{sp} recall" for sp in SPLITS) + " | "
              + " | ".join(f"{sp} precision" for sp in SPLITS) + " |",
              "|---" * (1 + 2 * len(SPLITS)) + "|"]
    for p in cfg.PIPELINES:
        lines.append(f"| {p} | " + " | ".join(f"{100*rec(p, sp, 'ALL'):.1f}%" for sp in SPLITS) + " | "
                     + " | ".join(f"{100*summ[p]['precision'][sp]['precision']:.1f}%" for sp in SPLITS) + " |")
lines += ["", "![recall by entity](figures/recall_by_entity.png)", "",
          "![recall and precision by language](figures/recall_precision_by_language.png)", "",
          "## Strict recall per entity and language", ""]
fmt = lambda v: "n/a" if v is None else f"{100*v:.1f}"
hdr = "| Entity | " + " | ".join(f"{p} {l.upper()}" for p in cfg.PIPELINES for l in LANGS) + " |"
lines += [hdr, "|---" * (1 + len(cfg.PIPELINES) * len(LANGS)) + "|"]
for l in labels:
    lines.append(f"| {l} | " + " | ".join(fmt(rec(p, lg, l)) for p in cfg.PIPELINES for lg in LANGS) + " |")
lines += ["", f"Side-by-side viewer: `reports/{cfg.DATASET}/compare.html`.",
          f"Details per pipeline: `runs/{cfg.DATASET}/<pipeline>/leaks.csv`, `false_positives_top.csv`, "
          f"`metrics_by_entity.csv`, masked output in `runs/{cfg.DATASET}/<pipeline>/masked/`."]
(cfg.REPORTS_DIR / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

# --- side-by-side HTML viewer ------------------------------------------------
view = []
for d in docs[: cfg.COMPARE_MAX_DOCS]:
    rec_d = {"id": d["id"], "lang": d["lang"], "text": d["text"],
             "gold": [[g["start"], g["end"], g["label"]] for g in d["spans"]], "p": {}}
    for p in cfg.PIPELINES:
        preds = merge(PREDS[p][d["id"]])
        status = []
        for g in d["spans"]:
            c = coverage(g, preds)
            status.append(2 if c >= cfg.FULL_COVERAGE else (1 if c > 0 else 0))
        segs = []
        for orig_t, rep, lab, a, b in mask_segments(d["text"], PREDS[p][d["id"]]):
            if rep is None:
                segs.append([orig_t, a])
            else:
                fp = not any(min(g["end"], b) > max(g["start"], a) for g in d["spans"])
                segs.append([orig_t, rep, 1 if fp else 0])
        rec_d["p"][p] = {"st": status, "seg": segs}
    view.append(rec_d)
meta = {"dataset": cfg.DATASET, "pipelines": cfg.PIPELINES, "labels": LABELS}
html = (Path(__file__).resolve().parent / "compare_template.html").read_text(encoding="utf-8")
html = html.replace("/*__DATA__*/null", json.dumps(view, ensure_ascii=False).replace("</", "<\\/"))
html = html.replace("/*__META__*/null", json.dumps(meta, ensure_ascii=False))
(cfg.REPORTS_DIR / "compare.html").write_text(html, encoding="utf-8")

print(f"report : {cfg.REPORTS_DIR / 'REPORT.md'}")
print(f"viewer : {cfg.REPORTS_DIR / 'compare.html'}")
print(f"figures: {FIG}")
