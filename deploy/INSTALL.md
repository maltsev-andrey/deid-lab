# Offline installation on an air-gapped RHEL 9 host

The production host has no network. Everything is built and tested on a build host with
internet access, carried over as one directory, and installed without a single download.

## What goes on the media

| File | Content | Size (approx.) |
|---|---|---|
| `deid-env.tar.gz` | the complete conda environment: Python 3.11, Presidio, spaCy + de/fr/it `lg` models, torch CPU, gliner, pandas, matplotlib, Pillow | 3 GB |
| `deid-lab-src.tar.gz` | project code, examples, docs, tests | 3 MB |
| `deid-models.tar.gz` | `models/` with the GLiNER checkpoint (pipeline C). Optional | 1.1 GB |
| `deid-external.tar.gz` | GraSCCo + ai4privacy raw downloads for benchmarks. Optional | 200 MB |
| `SHA256SUMS`, `MANIFEST.txt` | integrity check, package list, build host info | |

No RPM beyond a minimal RHEL 9 is required: the environment carries its own Python and
libraries and only needs glibc, libstdc++, libgomp and zlib from the base system.
Tesseract (OCR for scanned images) and Java are **not** needed for the current scope.

## Build host requirements

- Same architecture as the target (x86_64) and a glibc **not newer** than the target's.
  RHEL 8 -> RHEL 9 works; RHEL 9 -> RHEL 9 is the safe choice. Recommended: a RHEL 9 minimal
  VM that mirrors the production host.
- conda env `deid` that runs `./run_all.sh` and, for pipeline C, has run it once online so
  `models/` holds the checkpoint.

```bash
[ansible@rhel9-build ~]$ conda activate deid
[ansible@rhel9-build ~]$ cd /nfs/shared/projects/deid-lab
[ansible@rhel9-build deid-lab]$ DEID_DATASET=grascco DEID_PIPELINES=C_gliner ./run_eval.sh    # fills models/
[ansible@rhel9-build deid-lab]$ deploy/make_offline_bundle.sh /nfs/shared/bundle
```

## Install on the target

```bash
[admin@deid-prod ~]$ sudo mkdir -p /opt/deid && sudo chown $USER /opt/deid
[admin@deid-prod ~]$ deploy/install_offline.sh /media/bundle /opt/deid
```

The installer verifies checksums, unpacks the environment, runs `conda-unpack`, unpacks the
project and models, writes `/opt/deid/env.sh` and runs the offline self-test (AFP tests,
pipeline C plumbing, spaCy model load, GLiNER offline load).

Daily use:

```bash
[admin@deid-prod ~]$ source /opt/deid/env.sh
[admin@deid-prod ~]$ cd /opt/deid/deid-lab
[admin@deid-prod deid-lab]$ ./run_all.sh                                    # synthetic corpus, all pipelines, reports
[admin@deid-prod deid-lab]$ python scripts/21_afp_mask.py /data/in /data/out --render   # AFP batch
```

`DEID_OFFLINE=1` (set by `env.sh`) tells huggingface_hub never to touch the network, so a
missing model fails immediately instead of waiting for a connect timeout.

## Validate before carrying it over

Do the whole install once at home on a **second** RHEL 9 VM with the network interface down.
If `./run_all.sh` there prints the same numbers as the build host, the bundle is good.

## Updating

Code-only changes: a new `deid-lab-src.tar.gz` (3 MB) replaces `/opt/deid/deid-lab`
(keep `models/`, `data/`, `runs/`). Dependency changes: rebuild `deid-env.tar.gz`.

## Minimal variant (AFP + rules only)

If the first production step is AFP masking with rules (pipeline A) and no NER, the host
needs only Python 3.11 and the project code: `python3.11` from the RHEL 9 AppStream repo and
`deid-lab-src.tar.gz`. `deidlab/afp.py` and `deidlab/rules.py` import nothing outside the
standard library. The NER layer (3 GB env) can follow as a second phase.
