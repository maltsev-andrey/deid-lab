# AFP (MO:DCA) demo: synthetic print stream before and after anonymisation

Built by `scripts/20_afp_demo.py` from the synthetic corpus. **No real persons, no client
files**: every name, number and address comes from Faker and templates (`scripts/01_generate.py`).

| File | What |
|---|---|
| `demo_original.afp` | 3 patient documents (DE discharge, FR lab, IT referral), one page group each, TLE index tags, EBCDIC CP500, word-positioned text like a real print stream |
| `demo_anonymised.afp` | same file after `deidlab.afp.mask_document` with pipeline B_presidio_pp: identical size and structure, PII bytes replaced in place |
| `demo_original_pN.png`, `demo_anonymised_pN.png` | rendered text layer, masked fragments highlighted |
| `demo_side_by_side.png` | page 1 before/after, slide-ready |
| `demo_report.txt` | spans found, bytes masked, index tags after masking |

Open the `.afp` files in any AFP viewer (AFPView, AFP Workbench) to check the rendering;
the fonts are IBM core Helvetica names (`C0H200A0`), viewers substitute if missing.
