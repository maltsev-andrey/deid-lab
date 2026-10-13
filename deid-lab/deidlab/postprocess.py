"""
Document-level post-processing, pipeline-agnostic. Applied on top of A or B.

1. deny_filter   drop spans that are known non-PII words (salutations, form labels)
2. propagate     once a value is found anywhere in the document, mask every other
                 occurrence too: exact value, name parts, city from "PLZ City",
                 locality from a hospital name ("Kantonsspital Baden" -> "Baden").
                 Rationale: one unmasked copy of a name de-anonymises all masked copies.
3. PersonLinker  used by mask(): variants of one person ("Schwab Vivien",
                 "Vivien Schwab", "Frau Schwab") share one pseudonym token.
"""
import re

from .medical_terms import DENY as MEDICAL_DENY, DRUG_SUFFIXES, MEDICAL_SUFFIXES
from .rules import LC, ORG_WORDS, UC, Span, detect as rules_detect

# --- 1. deny list --------------------------------------------------------------

DENY = {
    # salutations DE / FR / IT
    "kollegin", "kollege", "kolleginnen", "kollegen", "frau kollegin", "herr kollege",
    "consœur", "consoeur", "confrère", "collègues", "chers collègues", "chère consœur",
    "collega", "colleghi", "gentile collega", "cari colleghi",
    # titles that NER tags as a person on their own
    "dr", "dr.", "dott", "dott.", "prof", "prof.", "med", "med.",
}


def deny_filter(text, spans):
    out = []
    for s in spans:
        v = re.sub(r"\s+", " ", text[s.start:s.end]).strip(" ,.;:").lower()
        if v in DENY:
            continue
        out.append(s)
    return out


# --- 1b. utility filter for NER spans --------------------------------------------------
# General-purpose NER on clinical text tags anatomy, drugs, lab values and abbreviations as
# names and places. Rules and propagation are trusted; only NER-sourced spans go through here.

NER_SOURCES = {"SpacyRecognizer", "TransformersRecognizer", "GLiNERRecognizer", "ner"}
ORG_WORDS_RX = re.compile(rf"(?i)(?:{ORG_WORDS})")
LOC_PREP_RX = re.compile(
    r"(?:\b(?:in|aus|nach|bei|von|zu|über|Richtung|wohnhaft|Herkunft|Ort|Wohnort|"      # DE
    r"à|de|en|vers|chez|depuis|habite|domicilié[e]?|ville|"                              # FR
    r"a|da|di|per|presso|in|verso|abita|domiciliat[oa]|città)\s*:?\s*|[,(]\s*)$", re.I)  # IT


def _is_medical(token: str) -> bool:
    t = token.lower().strip(".,;:()")
    if t in MEDICAL_DENY:
        return True
    return t.endswith(MEDICAL_SUFFIXES) or t.endswith(DRUG_SUFFIXES)


# Two context heuristics are domain-sensitive. On clinical letters each is worth ~15 points of
# precision at no measurable recall cost (GraSCCo); on short generic texts (forms, chats) they
# drop real names and cities. config.FILTER_PROFILE selects: "clinical" (default) or "generic".
def _profile():
    try:
        import config
        return getattr(config, "FILTER_PROFILE", "clinical")
    except ImportError:
        return "clinical"


def utility_filter(text, spans, profile=None):
    """Drop NER spans that cannot be PII by shape or vocabulary.
    clinical profile: single-token NER PERSON spans survive only when a confident multi-token
    person in the same document shares the token, and single-token NER LOCATION spans only
    after a locative preposition or inside an address."""
    profile = profile or _profile()
    strict = profile == "clinical"
    confident_person_tokens = set()
    for s in spans:
        if s.label == "PERSON" and s.source not in NER_SOURCES:
            confident_person_tokens.update(t.lower() for t in TOKEN_RX.findall(text[s.start:s.end]))
    out = []
    for s in spans:
        if s.source not in NER_SOURCES:
            out.append(s)
            continue
        v = text[s.start:s.end].strip()
        toks = v.split()
        if not any(c.isupper() for c in v):                       # "re", "für", "pall"
            continue
        if v.isupper() and len(v) <= 5 and s.label != "PERSON":   # "CCT", "BWS", "CEA"
            continue
        if s.label in ("LOCATION", "ORGANIZATION") and any(c.isdigit() for c in v):   # "BWK 10", "C20"
            continue
        if len(toks) == 1 and ("." in v or v.endswith(",")):      # "Z.n", "Körperl."
            continue
        if all(_is_medical(t) for t in toks):                      # "Os pubis", "Vena lienalis"
            continue
        if s.label != "PERSON" and any(_is_medical(t) for t in toks) and len(toks) <= 2:   # "Stadium IV"
            continue
        if s.label == "PERSON" and (_is_medical(toks[-1]) or re.match(r"^(?:M\.|Morbus)\s", v)):
            continue                                                # "Fortbestehender Nikotinabusus", "M. Parkinson"
        if s.label == "ORGANIZATION" and not ORG_WORDS_RX.search(v):
            continue
        if strict and s.label == "PERSON" and len(toks) == 1 and v.lower() not in confident_person_tokens:
            continue
        if strict and s.label == "LOCATION" and len(toks) == 1 \
                and not LOC_PREP_RX.search(text[max(0, s.start - 14):s.start]):
            continue
        out.append(s)
    return out


# --- 2. propagation --------------------------------------------------------------

NAME_STOP = {"dr", "med", "prof", "dent", "dott", "ssa", "sig", "ra", "herr", "frau", "mme", "madame",
             "monsieur", "signora", "signor", "de", "di", "da", "del", "della", "von", "van", "du",
             "la", "le", "les", "am", "an", "sur", "san", "st"}

INSTITUTION_WORDS = {"kantonsspital", "regionalspital", "stadtspital", "spital", "klinik", "hôpital",
                     "régional", "centre", "hospitalier", "clinique", "ospedale", "regionale", "civico",
                     "clinica", "labor", "laboratoire", "laboratorio"}

TOKEN_RX = re.compile(rf"[{UC}{LC}][{UC}{LC}'’\-]*")
PROPAGATE_LABELS = {"PERSON", "LOCATION", "ORGANIZATION", "STREET_ADDRESS", "PATIENT_ID",
                    "EMAIL", "PHONE", "AHV_NUMBER", "INSURANCE_CARD", "IBAN"}
# Only confident spans seed propagation; weak heuristics (score < 0.7) would spread their errors.
PROPAGATE_MIN_SCORE = 0.7
# Capitalised common words that are also parts of names in clinical letters; never propagate alone
PROPAGATE_STOP = {"hand", "patient", "patientin", "therapie", "mit", "mba", "klinik", "station", "praxis",
                  "zentrum", "abteilung", "institut", "universität", "medizin", "innere", "chirurgie"}


def _tokens(value):
    return [t for t in TOKEN_RX.findall(value)
            if len(t) >= 3 and t[0].isupper() and t.lower().strip(".") not in NAME_STOP | PROPAGATE_STOP]


def _find_all(text, needle, case_insensitive=False):
    flags = re.I if case_insensitive else 0
    for m in re.finditer(rf"(?<!\w){re.escape(needle)}s?(?!\w)", text, flags):
        if case_insensitive and not text[m.start()].isupper():
            continue   # "Frei" the surname yes, "frei" the adjective no
        yield m.start(), m.end()


def propagate(text, spans):
    found = []
    seen = set()
    for s in spans:
        if s.label not in PROPAGATE_LABELS or s.score < PROPAGATE_MIN_SCORE:
            continue
        value = text[s.start:s.end]
        targets = [(value, s.label, False)]
        if s.label == "PERSON":
            targets += [(t, "PERSON", True) for t in _tokens(value)]
        elif s.label == "LOCATION":
            city = re.sub(r"^(?:CH-)?\d{4}\s+", "", value)
            if city != value:
                targets.append((city, "LOCATION", False))
        elif s.label == "ORGANIZATION":
            targets += [(t, "LOCATION", False) for t in _tokens(value) if t.lower() not in INSTITUTION_WORDS]
        for needle, label, ci in targets:
            if len(needle) < 3 or (needle, ci) in seen:
                continue
            seen.add((needle, ci))
            for a, b in _find_all(text, needle, ci):
                found.append(Span(a, b, label, s.score * 0.95, "propagation"))
    return spans + found


# --- 3. person linking for pseudonyms ------------------------------------------------

class PersonLinker:
    """Assigns one id per real person inside a document.

    Full-name mentions link when their token sets are equal or one contains the other.
    A single-token mention ("Schwab") links only if exactly one known person has it,
    so "Daniele Valmarana" and his wife "Liliana Valmarana" stay two people.
    """

    def __init__(self):
        self.entities = []          # list of token sets, index = person number - 1

    def link(self, value):
        toks = {t.lower() for t in _tokens(value)}
        if not toks:
            toks = {value.lower()}
        if len(toks) == 1:
            hits = [i for i, e in enumerate(self.entities) if toks <= e]
            if len(hits) == 1:
                return hits[0] + 1
        else:
            for i, e in enumerate(self.entities):
                if toks <= e or (e <= toks and len(e) >= 1 and self._unique_owner(e, i)):
                    self.entities[i] = e | toks
                    return i + 1
        self.entities.append(toks)
        return len(self.entities)

    def _unique_owner(self, e, idx):
        # a single-token entity may only grow into a full name if no other person shares the token
        if len(e) > 1:
            return True
        return all(not (e <= other) for j, other in enumerate(self.entities) if j != idx)


class PostProcessed:
    """Wraps any pipeline with deny filter + propagation."""

    def __init__(self, base):
        self.base = base
        self.name = base.name + "_pp"

    def analyze(self, text, lang):
        spans = self.base.analyze(text, lang)
        # Presidio keeps one span per text range and may prefer the NER copy over the identical
        # rules copy. Re-adding the rules' own output keeps rule hits immune to the NER filter.
        if self.base.name != "A_regex":
            spans = spans + rules_detect(text)
        spans = deny_filter(text, spans)
        spans = utility_filter(text, spans)
        return propagate(text, spans)
