"""
AFP (MO:DCA) support: read the text layer with coordinates, mask it in place, write
simple AFP documents for tests and demos. Pure Python, standard library only.

MO:DCA in one paragraph: a file is a chain of structured fields, each 0x5A + 2-byte length
+ 3-byte ID + flags + sequence + data. Pages sit between BPG/EPG, optionally grouped by
BNG/ENG (one group per customer document in print streams). Page text lives in PTX fields as
control sequences (prefix 0x2BD3): absolute moves (AMB = baseline/y, AMI = inline/x), font
selection (SCFL) and the text itself (TRN), usually one word per TRN. Text bytes are in the
code page of the coded font, in Swiss print streams typically EBCDIC CP500 or CP1141.

Masking in place: AFP positions are absolute, so a replacement must keep the byte length.
We overwrite TRN bytes with a filler (default "X") and leave spaces; nothing else moves.
Index tags (TLE), page-group names (BNG/ENG) and comments (NOP) are masked as well.
"""
import re
from collections import defaultdict
from dataclasses import dataclass, field

# --- structured field ids ------------------------------------------------------
SF = {
    "BDT": 0xD3A8A8, "EDT": 0xD3A9A8, "BNG": 0xD3A8AD, "ENG": 0xD3A9AD, "BPG": 0xD3A8AF, "EPG": 0xD3A9AF,
    "BAG": 0xD3A8C9, "EAG": 0xD3A9C9, "BPT": 0xD3A89B, "EPT": 0xD3A99B, "PTX": 0xD3EE9B, "PTD": 0xD3B19B,
    "PGD": 0xD3A6AF, "MCF": 0xD3AB8A, "NOP": 0xD3EEEE, "TLE": 0xD3A090, "BIM": 0xD3A8FB, "EIM": 0xD3A9FB,
    "IPD": 0xD3EEFB, "BRS": 0xD3A8CE, "ERS": 0xD3A9CE, "BOC": 0xD3A892, "EOC": 0xD3A992,
}
SF_NAME = {v: k for k, v in SF.items()}

# PTX control sequence types (unchained value; chained = type | 1)
CS_AMB, CS_AMI, CS_RMB, CS_RMI, CS_SCFL, CS_TRN, CS_STO, CS_BLN = 0xD2, 0xC6, 0xD4, 0xC8, 0xF0, 0xDA, 0xF6, 0xD8

DEFAULT_CODEPAGE = "cp500"
UNITS_PER_INCH = 1440                    # unit base 0 (10 inches) with 14400 units
A4 = (11906, 16838)                      # A4 in 1/1440 inch


# --- reading -------------------------------------------------------------------

@dataclass
class Fragment:
    """One TRN run: text with its page position and its byte position in the file."""
    page: int
    y: int
    x: int
    font: int
    text: str
    fpos: int          # offset of the first text byte in the file
    nbytes: int
    group: str = ""    # enclosing page group name (BNG), "" if none


@dataclass
class Tag:
    """A TLE (index tag), BNG/ENG name or NOP comment with its byte position."""
    kind: str          # TLE | BNG | ENG | NOP
    name: str          # TLE attribute name, else ""
    value: str
    fpos: int
    nbytes: int


@dataclass
class AfpText:
    fragments: list = field(default_factory=list)
    tags: list = field(default_factory=list)
    pages: int = 0
    codepage: str = DEFAULT_CODEPAGE
    fonts: dict = field(default_factory=dict)   # local id -> (codepage name, charset name)

    def page_text(self, join_lines=True):
        """Reconstruct reading-order text per page: fragments grouped by baseline, sorted
        by x, joined with single spaces. Returns (text, charmap) where charmap maps text
        offsets back to fragments: list of (start, end, Fragment)."""
        lines = defaultdict(list)
        for f in self.fragments:
            lines[(f.page, f.y)].append(f)
        out, cmap, pos = [], [], 0
        last_page = None
        for key in sorted(lines):
            if last_page is not None and key[0] != last_page:
                out.append("\n\f\n"); pos += 3
            last_page = key[0]
            row = sorted(lines[key], key=lambda f: f.x)
            for k, f in enumerate(row):
                if k:
                    out.append(" "); pos += 1
                cmap.append((pos, pos + len(f.text), f))
                out.append(f.text); pos += len(f.text)
            out.append("\n"); pos += 1
        return "".join(out), cmap


def structured_fields(data):
    """Yield (offset, id, payload) for every structured field. offset points at 0x5A."""
    i, n = 0, len(data)
    while i < n:
        if data[i] != 0x5A:
            raise ValueError(f"not a structured field at byte {i}: {data[i:i + 4].hex()}")
        ln = int.from_bytes(data[i + 1:i + 3], "big")
        sfid = int.from_bytes(data[i + 3:i + 6], "big")
        yield i, sfid, data[i + 9:i + 1 + ln]
        i += 1 + ln


def _triplets(buf):
    """Yield (type, data) from a run of MO:DCA triplets (len, type, data)."""
    j = 0
    while j + 1 < len(buf):
        tl, tt = buf[j], buf[j + 1]
        if tl < 2:
            break
        yield tt, buf[j + 2:j + tl], j
        j += tl


def _ptx_sequences(payload):
    """Yield (data_offset_in_payload, type, data) for every PTX control sequence."""
    i, n, chained = 0, len(payload), False
    while i + 1 < n:
        if not chained:
            if payload[i:i + 2] != b"\x2b\xd3":
                i += 1
                continue
            i += 2
        ln, typ = payload[i], payload[i + 1]
        if ln < 2:
            break
        yield i + 2, typ, payload[i + 2:i + ln]
        chained = bool(typ & 0x01)
        i += ln


CODEPAGE_NAMES = {   # IBM code page names seen in MCF -> Python codec
    "T1V10500": "cp500", "T1V10037": "cp037", "T1V11141": "cp1141", "T1V10273": "cp273",
    "T1X00500": "cp500", "T1XFACT0": "cp500",
}


def read_text(data, codepage=None):
    """Parse an AFP byte string into fragments and tags. codepage overrides detection."""
    res = AfpText()
    cp = codepage or DEFAULT_CODEPAGE
    page, in_page, group = 0, False, ""
    y = x = 0
    font = 0
    for off, sfid, payload in structured_fields(data):
        name = SF_NAME.get(sfid)
        base = off + 9
        if name == "MCF":
            i = 0
            while i + 2 <= len(payload):
                glen = int.from_bytes(payload[i:i + 2], "big")
                if glen < 3:
                    break
                cpn = csn = None
                lid = None
                for tt, td, _ in _triplets(payload[i + 2:i + glen]):
                    if tt == 0x02 and len(td) >= 2:
                        fqn_type, nm = td[0], td[2:].decode("cp500", "replace").strip()
                        if fqn_type == 0x85:
                            cpn = nm
                        elif fqn_type == 0x86:
                            csn = nm
                        elif fqn_type == 0x8E:      # data-object (TrueType/OpenType) font, no code page
                            csn = nm
                    elif tt == 0x24 and len(td) >= 2:
                        lid = td[1]
                if lid is not None:
                    res.fonts[lid] = (cpn, csn)
                    if cpn in CODEPAGE_NAMES and codepage is None:
                        cp = CODEPAGE_NAMES[cpn]
                i += glen
        elif name == "BNG":
            group = payload[:8].decode(cp, "replace").strip()
            res.tags.append(Tag("BNG", "", group, base, min(8, len(payload))))
        elif name == "ENG":
            res.tags.append(Tag("ENG", "", payload[:8].decode(cp, "replace").strip(), base, min(8, len(payload))))
            group = ""
        elif name == "NOP":
            res.tags.append(Tag("NOP", "", payload.decode(cp, "replace"), base, len(payload)))
        elif name == "TLE":
            tname, tval, vpos, vlen = "", "", None, 0
            for tt, td, j in _triplets(payload):
                if tt == 0x02 and len(td) >= 2:
                    tname = td[2:].decode(cp, "replace").strip()
                elif tt == 0x36 and len(td) >= 2:
                    tval = td[2:].decode(cp, "replace")
                    vpos, vlen = base + j + 4, len(td) - 2
            if vpos is not None:
                res.tags.append(Tag("TLE", tname, tval, vpos, vlen))
        elif name == "BPG":
            page += 1; in_page = True; y = x = 0
        elif name == "EPG":
            in_page = False
        elif name == "PTX" and in_page:
            for dpos, typ, dat in _ptx_sequences(payload):
                t = typ & 0xFE
                if t == CS_AMB and len(dat) >= 2:
                    y = int.from_bytes(dat[:2], "big")
                elif t == CS_RMB and len(dat) >= 2:
                    y += int.from_bytes(dat[:2], "big", signed=True)
                elif t == CS_AMI and len(dat) >= 2:
                    x = int.from_bytes(dat[:2], "big")
                elif t == CS_RMI and len(dat) >= 2:
                    x += int.from_bytes(dat[:2], "big", signed=True)
                elif t == CS_SCFL and dat:
                    font = dat[0]
                elif t == CS_TRN and dat:
                    txt = dat.decode(cp, "replace")
                    res.fragments.append(Fragment(page, y, x, font, txt, base + dpos, len(dat), group))
                    x += len(dat) * 100   # placeholder advance; real width needs font metrics
    res.pages = page
    res.codepage = cp
    return res


# --- masking -------------------------------------------------------------------

def mask_bytes(data: bytearray, fpos: int, text: str, lo: int, hi: int, codepage: str, filler="X",
               width=None, font=None):
    """Overwrite characters lo:hi of a fragment (text offsets) with filler, keeping spaces.
    Single-byte code pages only (EBCDIC / Latin-1): char i == byte i.

    width(text, font) -> advance in 1/1440 inch, optional: with font metrics the filler run
    is shortened to the width of the original word and padded with spaces, so masked words
    in a proportional font do not run into their neighbours (byte length stays the same)."""
    fb, sb = filler.encode(codepage)[0], " ".encode(codepage)[0]
    seg = text[lo:hi]
    n = sum(1 for ch in seg if not ch.isspace())
    k = n
    if width and n:
        k = min(n, max(1, round(width(seg, font) / max(1, width(filler, font)))))
    done = 0
    for c in range(lo, hi):
        if text[c].isspace():
            continue
        data[fpos + c] = fb if done < k else sb
        done += 1
    return n


# TLE attribute names that hold identity by definition, whatever the value looks like
TLE_IDENTITY_RX = re.compile(r"(?i)name|vorname|nachname|id\b|nr|number|nummer|ahv|svn|birth|geb|dob|"
                             r"kunde|customer|client|patient|versich|insur|polic|adresse|address|strasse|"
                             r"street|plz|ort|city|phone|tel|mail|iban|konto|account")


def mask_document(data: bytes, detect, codepage=None, filler="X", zones=None, mask_tags=True,
                  symbol_fonts=(), width=None):
    """Mask PII in an AFP document.

    detect(text) -> list of spans with .start/.end (any pipeline from deidlab.pipelines)
    zones: optional list of (x0, y0, x1, y1) in 1/1440 inch; fragments inside are masked
           unconditionally (address window of a C5/C6 envelope, for instance)
    symbol_fonts: local font ids whose TRNs are barcode / OMR glyphs: blanked with spaces
    width: optional width(text, font_id) metric, see mask_bytes

    Returns (masked bytes, report dict)."""
    buf = bytearray(data)
    afp = read_text(data, codepage)
    text, cmap = afp.page_text()
    spans = detect(text)
    masked = 0
    found = []
    for s in spans:
        for ts, te, f in cmap:
            lo, hi = max(s.start, ts), min(s.end, te)
            if lo < hi:
                masked += mask_bytes(buf, f.fpos, f.text, lo - ts, hi - ts, afp.codepage, filler, width, f.font)
        found.append((getattr(s, "label", "?"), text[s.start:s.end]))
    zoned = 0
    for f in afp.fragments:
        if zones and any(x0 <= f.x <= x1 and y0 <= f.y <= y1 for x0, y0, x1, y1 in zones):
            zoned += mask_bytes(buf, f.fpos, f.text, 0, len(f.text), afp.codepage, filler, width, f.font)
        if f.font in symbol_fonts:
            sp = " ".encode(afp.codepage)[0]
            for k in range(f.nbytes):
                buf[f.fpos + k] = sp
            zoned += f.nbytes
    tagged = 0
    if mask_tags:
        for t in afp.tags:
            if t.kind in ("BNG", "ENG") or (t.kind == "TLE" and TLE_IDENTITY_RX.search(t.name)):
                # group names and identity index tags always identify the customer
                tagged += mask_bytes(buf, t.fpos, t.value, 0, len(t.value), afp.codepage, filler)
            elif t.value.strip():
                # other tags and comments: whatever the detector finds (dates, numbers ...)
                for s in detect(t.value):
                    tagged += mask_bytes(buf, t.fpos, t.value, s.start, s.end, afp.codepage, filler)
    suspects = sorted({f.font for f in afp.fragments
                       if f.font not in symbol_fonts and afp.fonts.get(f.font, (None,))[0] is None})
    return bytes(buf), {"pages": afp.pages, "codepage": afp.codepage, "fragments": len(afp.fragments),
                        "spans": found, "bytes_text": masked, "bytes_zones": zoned, "bytes_tags": tagged,
                        "fonts": afp.fonts, "symbol_candidates": suspects}


# --- writing (minimal MO:DCA for tests and demos) -------------------------------

def _sf(name, data=b""):
    body = SF[name].to_bytes(3, "big") + b"\x00" + b"\x00\x00" + data
    return b"\x5a" + (len(body) + 2).to_bytes(2, "big") + body


def _name8(s, cp):
    return s[:8].ljust(8).encode(cp)


def _cs(typ, data=b""):
    return b"\x2b\xd3" + bytes([len(data) + 2, typ]) + data


class AfpWriter:
    """Builds a one-document AFP: page groups, TLE index tags, positioned text.

    fonts: {local id: (codepage name, charset name)}; the viewer substitutes unknown fonts.
    Coordinates in 1/1440 inch, origin top-left, y = baseline."""

    def __init__(self, doc_name="DEIDDEMO", codepage=DEFAULT_CODEPAGE, page_size=A4,
                 fonts=None):
        self.cp = codepage
        self.size = page_size
        self.fonts = fonts or {1: ("T1V10500", "C0H200A0"),   # Helvetica 10
                               2: ("T1V10500", "C0H400D0"),   # Helvetica bold 14
                               3: ("T1V10500", "C0H400A0")}   # Helvetica bold 10
        self.parts = [_sf("BDT", _name8(doc_name, codepage) + b"\x00\x00")]
        self.nop(f"deid-lab synthetic AFP, no real persons, {doc_name}")
        self._page = 0

    # --- document structure
    def nop(self, comment):
        self.parts.append(_sf("NOP", comment.encode(self.cp)))

    def begin_group(self, name, tags=None):
        self.parts.append(_sf("BNG", _name8(name, self.cp)))
        for k, v in (tags or {}).items():
            fqn = bytes([len(k) + 4, 0x02, 0x0B, 0x00]) + k.encode(self.cp)
            val = bytes([len(v) + 4, 0x36, 0x00, 0x00]) + v.encode(self.cp)
            self.parts.append(_sf("TLE", fqn + val))

    def end_group(self, name):
        self.parts.append(_sf("ENG", _name8(name, self.cp)))

    def _mcf(self):
        groups = b""
        for lid, (cpn, csn) in self.fonts.items():
            trip = (bytes([12, 0x02, 0x85, 0x00]) + _name8(cpn, "cp500") +
                    bytes([12, 0x02, 0x86, 0x00]) + _name8(csn, "cp500") +
                    bytes([4, 0x24, 0x05, lid]))
            groups += (len(trip) + 2).to_bytes(2, "big") + trip
        return _sf("MCF", groups)

    def _descriptor(self, name):
        w, h = self.size
        return _sf(name, b"\x00\x00" + (14400).to_bytes(2, "big") * 2 + w.to_bytes(3, "big") + h.to_bytes(3, "big") + b"\x00\x00")

    def page(self, fragments):
        """fragments: iterable of (x, y, font_id, text). One TRN per fragment."""
        self._page += 1
        pname = _name8(f"PAGE{self._page:04d}", self.cp)
        p = [_sf("BPG", pname), _sf("BAG", pname), self._mcf(), self._descriptor("PGD"),
             self._descriptor("PTD"), _sf("EAG", pname), _sf("BPT", pname)]
        cur_font, cur_y = None, None
        buf = _cs(CS_STO, b"\x00\x00\x2d\x00")        # orientation 0 / 90 degrees: normal portrait
        for x, y, fid, text in fragments:
            if fid != cur_font:
                buf += _cs(CS_SCFL, bytes([fid])); cur_font = fid
            if y != cur_y:
                buf += _cs(CS_AMB, y.to_bytes(2, "big")); cur_y = y
            buf += _cs(CS_AMI, x.to_bytes(2, "big"))
            raw = text.encode(self.cp, "replace")
            for k in range(0, len(raw), 250):          # control sequence length is one byte
                buf += _cs(CS_TRN, raw[k:k + 250])
            if len(buf) > 30000:                       # keep PTX fields well under 32 KB
                p.append(_sf("PTX", buf)); buf = b""
        if buf:
            p.append(_sf("PTX", buf))
        p += [_sf("EPT", pname), _sf("EPG", pname)]
        self.parts.extend(p)

    def tobytes(self, doc_name="DEIDDEMO"):
        return b"".join(self.parts) + _sf("EDT", _name8(doc_name, self.cp))


# --- layout helper: plain text -> positioned words ------------------------------

def layout_text(text, measure, left=1440, top=1700, line_height=260, font=1, title_font=2,
                title_lines=1, space=None, max_x=10800):
    """Turn a plain-text letter into (x, y, font, word) fragments, one word per fragment,
    like real print streams. measure(text, font) -> width in 1/1440 inch."""
    frags, y = [], top
    for li, line in enumerate(text.split("\n")):
        fid = title_font if li < title_lines and line.strip() else font
        if not line.strip():
            y += line_height // 2
            continue
        x = left
        sp = space or measure(" ", fid)
        for word in re.split(r"[ \t]+", line.strip()):
            w = measure(word, fid)
            if x + w > max_x and x > left:
                y += line_height; x = left
            frags.append((x, y, fid, word))
            x += w + sp
        y += line_height
    return frags, y
