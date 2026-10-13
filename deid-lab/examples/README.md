# Examples: original vs anonymized

Each pair is one input document and the output of pipeline `B_presidio_pp`
(Presidio + spaCy NER + Swiss/German rules + document-level post-processing), exactly as
written to `runs/<dataset>/B_presidio_pp/masked/`. Nothing was edited by hand.

| Pair | Source | Language | Document type |
|---|---|---|---|
| `01_de_discharge_*` | deid-lab synthetic corpus | DE | Austrittsbericht (discharge letter) |
| `02_fr_lab_*` | deid-lab synthetic corpus | FR | Rapport de laboratoire |
| `03_it_referral_*` | deid-lab synthetic corpus | IT | Richiesta di consulenza (referral) |
| `04_grascco_Weil_*` | GraSCCo_PII v2, test split | DE | Ambulanter Arztbrief (orthopaedics) |

**No real patient data.** Pairs 01 to 03 are generated with Faker and templates. Pair 04 is from
GraSCCo (Graz Synthetic Clinical text Corpus), a synthetic German clinical corpus with curated
PII annotations by the GeMTeX project, Zenodo record 11502329, licence CC-BY-4.0:
Modersohn L, Schulz S, Lohr C, Hahn U. *GRASCCO - The First Publicly Shareable, Multiply-Alienated
German Clinical Text Corpus.* Stud Health Technol Inform 2022;296:66-72.
Lohr C et al. *De-Identifying GRASCCO.* Stud Health Technol Inform 2024;317:171-179.

## How to read the output

- `<PERSON_1>`, `<DATE_2>` ... are per-document pseudonyms. The same value gets the same token
  everywhere in the document; name variants of one person (`Schwab Vivien`, `Vivien Schwab`,
  `Frau Schwab`) share one token.
- Diagnoses, medication, lab values and insurer names are kept on purpose (catalog `not_pii`).
- Bare years and month/year are masked as dates, following the GeMTeX guideline. That is a
  business decision still open in `catalog/entities.yaml`.

## What to look for in pair 04

This letter is from the GraSCCo **test** half, which was never used for tuning. It shows what the
pipeline does on a document nobody on this project wrote: letterhead with institution, street,
ZIP and phone extensions (`o. 2522`), a patient line in `Surname, Firstname, geb. date, PIZ`
format, dates in running text, and a signature. Compare it with the original side by side with
`diff`, or open `reports/grascco/compare.html` after a run for the full corpus with leaks and
false positives highlighted.
