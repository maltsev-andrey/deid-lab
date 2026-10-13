"""Step 10: download external benchmark corpora (needs internet on this host).

ai4privacy  open-pii-masking-500k, validation split (~142 MB, CC-BY-4.0), Hugging Face
grascco     GraSCCo_PII, latest version, all files of the Zenodo record (~2.5 MB)

Files land in data/external_raw/<name>/. Already downloaded files are skipped.
Honors HTTPS_PROXY / https_proxy from the environment.
"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as cfg

# --- what to fetch -----------------------------------------------------------
FETCH_AI4PRIVACY = True
FETCH_GRASCCO = True

AI4PRIVACY_URL = ("https://huggingface.co/datasets/ai4privacy/open-pii-masking-500k-ai4privacy/"
                  "resolve/main/data/validation/test.jsonl")
GRASCCO_RECORD = "11502329"   # any version id of the record; the API resolves the latest


def download(url, dest: Path):
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  skip  {dest.name} (exists, {dest.stat().st_size / 1e6:.1f} MB)")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "deid-lab/0.3"})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  get   {dest.name}: {done / 1e6:6.1f} / {total / 1e6:.1f} MB", end="", flush=True)
    tmp.rename(dest)
    print(f"\r  done  {dest.name}: {dest.stat().st_size / 1e6:.1f} MB" + " " * 20)


if FETCH_AI4PRIVACY:
    print("ai4privacy:")
    download(AI4PRIVACY_URL, cfg.EXTERNAL_RAW / "ai4privacy" / "test.jsonl")

if FETCH_GRASCCO:
    print("GraSCCo_PII:")
    api = f"https://zenodo.org/api/records/{GRASCCO_RECORD}/versions/latest"
    with urllib.request.urlopen(urllib.request.Request(api, headers={"Accept": "application/json", "User-Agent": "deid-lab/0.3"}), timeout=60) as r:
        rec = json.load(r)
    out = cfg.EXTERNAL_RAW / "grascco"
    out.mkdir(parents=True, exist_ok=True)
    meta = {"id": rec.get("id"), "version": rec.get("metadata", {}).get("version"),
            "title": rec.get("metadata", {}).get("title"),
            "license": (rec.get("metadata", {}).get("license") or {}).get("id"),
            "files": [f["key"] for f in rec.get("files", [])]}
    (out / "record.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  record {meta['id']} version {meta['version']} license {meta['license']}")
    for f in rec.get("files", []):
        download(f["links"]["self"], out / f["key"])

print(f"\nraw data in {cfg.EXTERNAL_RAW}")
