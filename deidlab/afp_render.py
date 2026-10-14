"""
Render the text layer of an AFP file to PNG with Pillow: true page coordinates, fonts
approximated with DejaVu Sans. For slides and for eyeballing masked output without an
AFP viewer. Images, overlays and barcodes are not drawn (a grey box marks image objects).
"""
import os

from PIL import Image, ImageDraw, ImageFont

from .afp import read_text, UNITS_PER_INCH, A4


def _find_font(bold):
    """First TrueType font that exists: system DejaVu/Liberation (Debian and RHEL paths),
    then the DejaVu copy that ships inside matplotlib (always present in the deid env)."""
    names = (["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"] if bold
             else ["DejaVuSans.ttf", "LiberationSans-Regular.ttf"])
    dirs = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu-sans-fonts", "/usr/share/fonts/dejavu",
            "/usr/share/fonts/truetype/liberation", "/usr/share/fonts/liberation-sans", "/usr/share/fonts/liberation"]
    try:
        import matplotlib
        dirs.append(os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf"))
    except ImportError:
        pass
    for d in dirs:
        for n in names:
            path = os.path.join(d, n)
            if os.path.exists(path):
                return path
    return None


FONT_REGULAR = _find_font(False)
FONT_BOLD = _find_font(True) or FONT_REGULAR
_SIZE_CODES = {"60": 6, "70": 7, "80": 8, "90": 9, "A0": 10, "B0": 11, "C0": 12, "D0": 14,
               "E0": 16, "F0": 18, "G0": 20, "H0": 24, "J0": 30}


def font_spec(charset):
    """IBM charset name -> (bold, point size). C0H200A0 = Helvetica 10, C0H400D0 = bold 14."""
    if not charset:
        return False, 10
    bold = len(charset) > 4 and charset[3] in "4567"
    return bold, _SIZE_CODES.get(charset[-2:], 10)


_font_cache = {}


def pil_font(bold, pt, px_per_pt):
    key = (bold, pt, px_per_pt)
    if key not in _font_cache:
        size = max(4, round(pt * px_per_pt))
        path = FONT_BOLD if bold else FONT_REGULAR
        if path:
            _font_cache[key] = ImageFont.truetype(path, size)
        else:   # no TrueType font anywhere: Pillow's built-in (Pillow >= 10.1 scales it)
            try:
                _font_cache[key] = ImageFont.load_default(size)
            except TypeError:
                _font_cache[key] = ImageFont.load_default()
    return _font_cache[key]


def measure_factory(fonts):
    """measure(text, font_id) in 1/1440 inch, using the same fonts the renderer draws with."""
    def measure(text, fid):
        bold, pt = font_spec((fonts.get(fid) or (None, None))[1])
        return int(pil_font(bold, pt, UNITS_PER_INCH / 72).getlength(text))
    return measure


def render(data, dpi=110, page_size=A4, highlight=None):
    """Render every page. highlight: callable(Fragment) -> colour or None, draws a box
    behind the fragment. Returns list of PIL images."""
    afp = read_text(data)
    scale = dpi / UNITS_PER_INCH
    w, h = int(page_size[0] * scale), int(page_size[1] * scale)
    pages = [Image.new("RGB", (w, h), "white") for _ in range(max(1, afp.pages))]
    draws = [ImageDraw.Draw(p) for p in pages]
    # image objects: grey placeholder at their page position is not known without IDD/IOCA
    # parsing, so just count them per page
    for f in afp.fragments:
        d = draws[f.page - 1]
        bold, pt = font_spec((afp.fonts.get(f.font) or (None, None))[1])
        font = pil_font(bold, pt, dpi / 72)
        x, y = f.x * scale, f.y * scale
        asc = font.getmetrics()[0]
        if highlight:
            col = highlight(f)
            if col:
                tw = font.getlength(f.text)
                d.rectangle([x - 2, y - asc - 2, x + tw + 2, y + 4], fill=col)
        d.text((x, y - asc), f.text, fill="black", font=font)
    for i, p in enumerate(pages):
        ImageDraw.Draw(p).rectangle([0, 0, w - 1, h - 1], outline="#9a9a9a")
    return pages


def side_by_side(img_a, img_b, gap=40, labels=("original", "anonymised"), label_h=60):
    """Two page images next to each other with captions, for a slide."""
    w = img_a.width + img_b.width + gap * 3
    h = max(img_a.height, img_b.height) + gap * 2 + label_h
    out = Image.new("RGB", (w, h), "#f4f4f2")
    d = ImageDraw.Draw(out)
    font = pil_font(True, 34, 1.0)
    for k, (img, lab) in enumerate(((img_a, labels[0]), (img_b, labels[1]))):
        x = gap + k * (img_a.width + gap)
        d.text((x, gap), lab, fill="#222", font=font)
        out.paste(img, (x, gap + label_h))
    return out
