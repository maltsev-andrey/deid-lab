"""
Detection pipelines with one common interface:

    pipeline.analyze(text, lang) -> list[Span]

A_regex     deterministic Swiss rules only (rules.py)
B_presidio  Microsoft Presidio: spaCy NER (de/fr/it) + Presidio built-ins
            (email, IBAN, phone CH, dates) + the same Swiss rules as A
C_gliner    GLiNER multilingual PII model (gliner_pipeline.py) + the same rules as A
D_union     B and C together (recall first)
"<base>_pp" any of them wrapped with document-level post-processing (postprocess.py)

All run on CPU only.
"""
import logging
import re

from .rules import Span, detect as rules_detect

# tldextract (used by Presidio's e-mail/URL recognizers) tries to download the
# Public Suffix List on first use and dumps a traceback when that fails. It then
# falls back to its bundled snapshot, which is fine for us. Keep logs clean.
logging.getLogger("tldextract").setLevel(logging.CRITICAL)

# Presidio entity names -> catalog labels
PRESIDIO_TO_CATALOG = {
    "PERSON": "PERSON", "LOCATION": "LOCATION", "ORGANIZATION": "ORGANIZATION",
    "DATE_TIME": "DATE", "PHONE_NUMBER": "PHONE", "EMAIL_ADDRESS": "EMAIL",
    "IBAN_CODE": "IBAN", "URL": "URL",
}


class RegexPipeline:
    name = "A_regex"

    def analyze(self, text, lang):
        return rules_detect(text)


class PresidioPipeline:
    name = "B_presidio"

    def __init__(self, spacy_models: dict, score_threshold=0.35):
        from presidio_analyzer import AnalyzerEngine, EntityRecognizer, RecognizerRegistry, RecognizerResult
        from presidio_analyzer.nlp_engine import NlpEngineProvider
        from presidio_analyzer.predefined_recognizers import (
            DateRecognizer, EmailRecognizer, IbanRecognizer, PhoneRecognizer, SpacyRecognizer)

        langs = list(spacy_models)
        nlp_conf = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": l, "model_name": m} for l, m in spacy_models.items()],
            "ner_model_configuration": {
                "model_to_presidio_entity_mapping": {
                    "PER": "PERSON", "PERSON": "PERSON",
                    "LOC": "LOCATION", "GPE": "LOCATION",
                    "ORG": "ORGANIZATION",
                },
                "labels_to_ignore": ["MISC"],
                "low_confidence_score_multiplier": 0.4,
                "low_score_entity_names": [],
            },
        }
        nlp_engine = NlpEngineProvider(nlp_configuration=nlp_conf).create_engine()

        class SwissRulesRecognizer(EntityRecognizer):
            """Wraps rules.py so A's rules run inside Presidio."""
            LABELS = ["AHV_NUMBER", "INSURANCE_CARD", "IBAN", "EMAIL", "PHONE", "PATIENT_ID",
                      "DATE", "STREET_ADDRESS", "LOCATION", "PERSON"]

            def load(self):
                pass

            def analyze(self, text, entities, nlp_artifacts=None):
                return [RecognizerResult(s.label, s.start, s.end, s.score) for s in rules_detect(text)]

        registry = RecognizerRegistry(supported_languages=langs)
        for l in langs:
            registry.add_recognizer(SpacyRecognizer(
                supported_language=l, supported_entities=["PERSON", "LOCATION", "ORGANIZATION"]))
            registry.add_recognizer(EmailRecognizer(supported_language=l))
            registry.add_recognizer(IbanRecognizer(supported_language=l))
            registry.add_recognizer(PhoneRecognizer(supported_language=l, supported_regions=("CH",)))
            registry.add_recognizer(DateRecognizer(supported_language=l))
            registry.add_recognizer(SwissRulesRecognizer(
                supported_entities=SwissRulesRecognizer.LABELS, supported_language=l, name=f"swiss_rules_{l}"))

        self.engine = AnalyzerEngine(nlp_engine=nlp_engine, registry=registry, supported_languages=langs)
        self.threshold = score_threshold

    def analyze(self, text, lang):
        res = self.engine.analyze(text=text, language=lang, score_threshold=self.threshold)
        out = []
        for r in res:
            label = PRESIDIO_TO_CATALOG.get(r.entity_type, r.entity_type)
            src = (r.recognition_metadata or {}).get("recognizer_name", "")
            # spaCy spans sometimes run across a line break or a column gap
            # ("Capoclinica\n\nAllegra Giacconi"): split into pieces and keep every
            # piece, so the name survives as its own span. Recall first.
            for m in re.finditer(r"[^\n\t]+?(?=\s{2,}|\n|\t|$)", text[r.start:r.end]):
                s, e = r.start + m.start(), r.start + m.end()
                while s < e and text[s].isspace():
                    s += 1
                while e > s and text[e - 1] in " \n\t,.;:":
                    e -= 1
                if e > s:
                    out.append(Span(s, e, label, r.score, src))
        return out


_CACHE = {}


def build(name, cfg):
    """Pipeline factory. "<base>_pp" wraps a base pipeline with document-level
    post-processing; base instances are cached so spaCy models load once."""
    if name in _CACHE:
        return _CACHE[name]
    if name.endswith("_pp"):
        from .postprocess import PostProcessed
        p = PostProcessed(build(name[:-3], cfg))
    elif name == "A_regex":
        p = RegexPipeline()
    elif name == "B_presidio":
        p = PresidioPipeline(cfg.SPACY_MODELS, cfg.PRESIDIO_SCORE_THRESHOLD)
    elif name == "C_gliner":
        from .gliner_pipeline import GlinerPipeline
        p = GlinerPipeline(cfg.GLINER_MODEL, cfg.GLINER_LABELS, cfg.GLINER_THRESHOLD,
                           cfg.GLINER_MAX_WORDS, cfg.TORCH_THREADS, cfg.MODEL_CACHE_DIR)
    elif name == "D_union":
        from .gliner_pipeline import UnionPipeline
        p = UnionPipeline("D_union", [build("B_presidio", cfg), build("C_gliner", cfg)])
    else:
        raise ValueError(f"unknown pipeline {name!r}; see config.PIPELINES")
    _CACHE[name] = p
    return p


# --- masking -----------------------------------------------------------------

def merge(spans):
    """Union overlapping spans. Label of the merged span = label of its longest part."""
    if not spans:
        return []
    spans = sorted(spans, key=lambda s: (s.start, -s.end))
    merged = []
    for s in spans:
        if merged and s.start < merged[-1].end:
            m = merged[-1]
            longest = m if (m.end - m.start) >= (s.end - s.start) else s
            merged[-1] = Span(m.start, max(m.end, s.end), longest.label, max(m.score, s.score), m.source)
        else:
            merged.append(Span(s.start, s.end, s.label, s.score, s.source))
    return merged


def mask_segments(text, spans):
    """Split text into (original, replacement, label) segments. replacement is None for
    untouched text. Name variants of one person share a token (see PersonLinker)."""
    from .postprocess import PersonLinker
    linker = PersonLinker()
    ids, segs, last = {}, [], 0
    for s in merge(spans):
        value = text[s.start:s.end]
        if s.label == "PERSON":
            token = f"<PERSON_{linker.link(value)}>"
        else:
            key = (s.label, value.lower())
            if key not in ids:
                n = sum(1 for k in ids if k[0] == s.label) + 1
                ids[key] = f"<{s.label}_{n}>"
            token = ids[key]
        if s.start > last:
            segs.append((text[last:s.start], None, None, last, s.start))
        segs.append((value, token, s.label, s.start, s.end))
        last = s.end
    if last < len(text):
        segs.append((text[last:], None, None, last, len(text)))
    return segs


def mask(text, spans):
    """Replace spans with consistent per-document pseudonyms: <PERSON_1>, <DATE_2> ..."""
    return "".join(rep if rep is not None else orig for orig, rep, *_ in mask_segments(text, spans))
