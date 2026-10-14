"""Offline tests for the AFP layer: write -> read round trip, in-place masking, tags."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deidlab.afp import AfpWriter, layout_text, mask_document, read_text, structured_fields, SF_NAME
from deidlab.rules import detect as rules_detect

LETTER = ("Kantonsspital Baden\n\nPatient: Schwab Vivien, geb. 19.02.2001\n"
          "AHV-Nr.: 756.4395.2071.69\nTelefon: 061 431 64 75\n\nDiagnosen: Morbus Crohn (K50.9)\n")


def build(cp="cp500"):
    w = AfpWriter("TESTDOC", codepage=cp)
    w.begin_group("G0000001", {"PatientName": "Schwab Vivien", "PatientID": "10768805", "DocType": "discharge"})
    frags, _ = layout_text(LETTER, lambda t, f: len(t) * 100)
    w.page(frags)
    w.end_group("G0000001")
    return w.tobytes("TESTDOC")


def test_structure_and_roundtrip():
    data = build()
    names = [SF_NAME.get(i) for _, i, _ in structured_fields(data)]
    assert names[0] == "BDT" and names[-1] == "EDT"
    assert names.count("BPG") == names.count("EPG") == 1
    assert names.count("TLE") == 3
    afp = read_text(data)
    assert afp.pages == 1 and afp.codepage == "cp500"
    assert afp.fonts[1] == ("T1V10500", "C0H200A0")
    text, _ = afp.page_text()
    assert "Schwab Vivien, geb. 19.02.2001" in text
    assert "756.4395.2071.69" in text and "Morbus Crohn (K50.9)" in text


def test_umlauts_survive_ebcdic():
    w = AfpWriter("UML")
    w.page([(1440, 1700, 1, "Glückwunsch"), (3000, 1700, 1, "Zürich"), (4500, 1700, 1, "Hôpital")])
    text, _ = read_text(w.tobytes("UML")).page_text()
    assert "Glückwunsch Zürich Hôpital" in text


def test_mask_in_place():
    data = build()
    masked, rep = mask_document(data, rules_detect)
    assert len(masked) == len(data)
    # every structured field keeps its id and length
    assert [(o, i) for o, i, _ in structured_fields(masked)] == [(o, i) for o, i, _ in structured_fields(data)]
    text, _ = read_text(masked).page_text()
    for leak in ("Schwab", "Vivien", "19.02.2001", "756.4395", "431 64 75"):
        assert leak not in text, leak
    assert "Morbus Crohn (K50.9)" in text
    tags = {(t.kind, t.name): t.value for t in read_text(masked).tags}
    assert tags[("TLE", "PatientName")] == "XXXXXX XXXXXX"
    assert tags[("TLE", "PatientID")] == "XXXXXXXX"
    assert tags[("TLE", "DocType")] == "discharge"      # not an identity tag, kept
    assert tags[("BNG", "")] == "XXXXXXXX"
    assert rep["bytes_text"] > 30 and rep["bytes_tags"] > 20


def test_width_fitted_filler():
    data = build()
    wide = lambda t, f: sum(200 if ch == "X" else 100 for ch in t)   # X twice as wide as anything else
    masked, _ = mask_document(data, rules_detect, width=wide)
    text, _ = read_text(masked).page_text()
    frag = next(f for f in read_text(masked).fragments if f.text.startswith("XXX"))
    assert frag.text.count("X") * 2 <= len(frag.text) + 1   # run shortened, padded with spaces


def test_zones_and_symbol_fonts():
    w = AfpWriter("ZON")
    w.page([(1440, 1700, 1, "Kopfzeile"), (6800, 3600, 1, "Max Muster"), (6800, 3900, 1, "Musterweg 1"),
            (283, 16000, 2, "\x81\x82\x83")])
    data = w.tobytes("ZON")
    masked, rep = mask_document(data, lambda t: [], zones=[(6500, 3400, 9000, 4200)], symbol_fonts=(2,))
    text, _ = read_text(masked).page_text()
    assert "Kopfzeile" in text and "Muster" not in text
    assert rep["bytes_zones"] == len("Max Muster".replace(" ", "")) + len("Musterweg 1".replace(" ", "")) + 3


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("ok", n)
