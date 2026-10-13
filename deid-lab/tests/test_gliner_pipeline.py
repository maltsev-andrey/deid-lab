"""Offline tests for pipeline C plumbing (chunking, offsets, label mapping, post-processing).
The real GLiNER model is replaced by a regex stand-in, so this runs without torch."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as cfg
from deidlab.gliner_pipeline import GlinerPipeline, UnionPipeline, chunk_text
from deidlab.pipelines import mask
from deidlab.postprocess import PostProcessed


class FakeGliner:
    """Finds a few hard-coded values, returns chunk-relative offsets like GLiNER."""
    PATTERNS = {
        "person": r"Vivien Schwab|Schwab Vivien|Kristina Tanner|Leticia Aebi|Stephan Kohler|Kristian Merz",
        "hospital": r"Kantonsspital Baden",
        "city": r"\bAarau\b|\bBaden\b",
        "date": r"\d{2}\.\d{2}\.\d{4}|\d{1,2}\. März \d{4}",
    }
    calls = 0

    def predict_entities(self, text, labels, threshold=0.5):
        self.calls += 1
        out = []
        for lab in labels:
            rx = self.PATTERNS.get(lab)
            if not rx:
                continue
            for m in re.finditer(rx, text):
                out.append({"start": m.start(), "end": m.end(), "text": m.group(), "label": lab, "score": 0.9})
        return out


def test_chunk_offsets_roundtrip():
    text = Path(cfg.PROJECT_ROOT / "examples" / "01_de_discharge_original.txt").read_text(encoding="utf-8")
    for max_words in (5, 40, 180, 10_000):
        chunks = chunk_text(text, max_words)
        for off, ch in chunks:
            assert text[off:off + len(ch)] == ch
        covered = set()
        for off, ch in chunks:
            covered.update(range(off, off + len(ch)))
        assert all(i in covered for i, ch in enumerate(text) if not ch.isspace())


def test_long_single_line_is_cut():
    text = " ".join(f"w{i}" for i in range(1000))
    chunks = chunk_text(text, 180)
    assert len(chunks) == 6
    for off, ch in chunks:
        assert text[off:off + len(ch)] == ch
        assert len(ch.split()) <= 180


def test_pipeline_c_end_to_end():
    text = Path(cfg.PROJECT_ROOT / "examples" / "01_de_discharge_original.txt").read_text(encoding="utf-8")
    fake = FakeGliner()
    c = GlinerPipeline("fake", cfg.GLINER_LABELS, threshold=0.5, max_words=40, model=fake)
    spans = c.analyze(text, "de")
    assert fake.calls > 1                                       # chunked
    gl = [s for s in spans if s.source == "GLiNERRecognizer"]
    assert {text[s.start:s.end] for s in gl if s.label == "PERSON"} >= {"Vivien Schwab", "Kristina Tanner"}
    assert any(s.label == "ORGANIZATION" and text[s.start:s.end] == "Kantonsspital Baden" for s in gl)
    assert any(s.label == "AHV_NUMBER" for s in spans)         # rules ran alongside

    masked = mask(text, PostProcessed(c).analyze(text, "de"))
    for leak in ("Schwab", "Tanner", "Aebi", "Kohler", "Merz", "756.4395", "Kirchweg", "swissonline"):
        assert leak not in masked, leak
    assert "Morbus Crohn" in masked and "Atorvastatin" in masked


def test_union_pipeline():
    text = "Patient Vivien Schwab, AHV-Nr.: 756.4395.2071.69"
    c = GlinerPipeline("fake", cfg.GLINER_LABELS, model=FakeGliner(), with_rules=False)
    d = UnionPipeline("D_union", [c, c])
    spans = d.analyze(text, "de")
    assert sum(1 for s in spans if s.label == "PERSON") == 2
    assert "<PERSON_1>" in mask(text, spans)


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("ok", n)
