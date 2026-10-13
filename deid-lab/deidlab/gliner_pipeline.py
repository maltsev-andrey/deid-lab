"""
Pipeline C: GLiNER PII model on CPU.

GLiNER (Generalist and Lightweight model for NER) takes the entity labels as *text prompts*,
so the label set is ours, not the model's: "person", "phone number", "health insurance
number" ... The multilingual PII checkpoint (urchade/gliner_multi_pii-v1, mDeBERTa-v3 base,
~280 M parameters) was trained on PII-style annotations, which is closer to our task than
the general news NER behind spaCy *_core_news_lg (pipeline B).

CPU cost: 0.3 to 2 s per clinical letter on one core, depending on length. The model is
downloaded once from Hugging Face into config.MODEL_CACHE_DIR (default <project>/models,
git-ignored). Everything else runs offline.

Layout: the same rules as A run alongside the model (as in B); GLiNER spans carry
source="GLiNERRecognizer" so the post-processing utility filter treats them as NER output.
"""
import re

from .rules import Span, detect as rules_detect

GLINER_SOURCE = "GLiNERRecognizer"
_WORD_RX = re.compile(r"\S+")


def chunk_text(text: str, max_words: int):
    """Split text into (offset, chunk) pieces of at most max_words words, cutting only at
    line breaks when possible. GLiNER truncates long inputs (384 word tokens), so the
    whole letter must never go in at once."""
    chunks, buf, buf_words, buf_start = [], [], 0, 0
    pos = 0
    for line in text.splitlines(keepends=True):
        n = len(_WORD_RX.findall(line))
        if n > max_words:
            # one very long line (no newlines in the document): cut it by words
            if buf:
                chunks.append((buf_start, "".join(buf)))
                buf, buf_words = [], 0
            words = list(_WORD_RX.finditer(line))
            for i in range(0, len(words), max_words):
                s = words[i].start()
                e = words[min(i + max_words, len(words)) - 1].end()
                chunks.append((pos + s, line[s:e]))
            pos += len(line)
            buf_start = pos
            continue
        if buf and buf_words + n > max_words:
            chunks.append((buf_start, "".join(buf)))
            buf, buf_words, buf_start = [], 0, pos
        if not buf:
            buf_start = pos
        buf.append(line)
        buf_words += n
        pos += len(line)
    if buf:
        chunks.append((buf_start, "".join(buf)))
    return [(o, c) for o, c in chunks if c.strip()]


def _clean_pieces(text, start, end):
    """Split a model span at line breaks / column gaps and trim punctuation, as for spaCy
    spans in pipeline B."""
    for m in re.finditer(r"[^\n\t]+?(?=\s{2,}|\n|\t|$)", text[start:end]):
        s, e = start + m.start(), start + m.end()
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1] in " \n\t,.;:":
            e -= 1
        if e > s:
            yield s, e


class GlinerPipeline:
    name = "C_gliner"

    def __init__(self, model_name, labels: dict, threshold=0.5, max_words=180,
                 num_threads=None, cache_dir=None, with_rules=True, model=None):
        """
        labels: {gliner prompt label -> catalog label}, e.g. {"person": "PERSON"}
        model:  injected object with predict_entities(text, labels, threshold) (tests);
                None loads the real GLiNER checkpoint.
        """
        self.labels = dict(labels)
        self.prompt_labels = list(self.labels)
        self.threshold = threshold
        self.max_words = max_words
        self.with_rules = with_rules
        if model is None:
            try:
                import torch
                from gliner import GLiNER
            except ImportError as e:   # pragma: no cover
                raise ImportError(
                    "pipeline C needs the gliner package and a CPU build of torch: "
                    "pip install -r requirements-c.txt  (see README, Pipeline C)") from e
            if num_threads:
                torch.set_num_threads(int(num_threads))
            kw = {"cache_dir": str(cache_dir)} if cache_dir else {}
            model = GLiNER.from_pretrained(model_name, **kw)
            model.eval()
        self.model = model

    # GLiNER returns [{"start", "end", "text", "label", "score"}] with chunk-relative offsets
    def _predict(self, chunks):
        texts = [c for _, c in chunks]
        bp = getattr(self.model, "batch_predict_entities", None)
        if bp is not None:
            try:
                return bp(texts, self.prompt_labels, threshold=self.threshold)
            except TypeError:
                pass
        return [self.model.predict_entities(t, self.prompt_labels, threshold=self.threshold) for t in texts]

    def analyze(self, text, lang):
        out = []
        chunks = chunk_text(text, self.max_words)
        if chunks:
            for (offset, chunk), ents in zip(chunks, self._predict(chunks)):
                for e in ents:
                    label = self.labels.get(e["label"])
                    if not label:
                        continue
                    for s, t in _clean_pieces(text, offset + e["start"], offset + e["end"]):
                        out.append(Span(s, t, label, float(e["score"]), GLINER_SOURCE))
        if self.with_rules:
            out.extend(rules_detect(text))
        return out


class UnionPipeline:
    """Pipeline D: union of several base pipelines' spans (recall first; precision is the
    post-processing's job). Overlaps are merged at masking / evaluation time."""

    def __init__(self, name, bases):
        self.name = name
        self.bases = bases

    def analyze(self, text, lang):
        out = []
        for b in self.bases:
            out.extend(b.analyze(text, lang))
        return out
