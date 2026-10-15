"""
Deterministic Swiss PII rules (pipeline A core, also reused inside pipeline B).

Each rule is a compiled regex plus a label. If the regex has a named group
"v", only that group is reported (used to skip honorifics and field labels).
Validators reject structurally invalid hits (e.g. AHV check digit).
"""
import re
from dataclasses import dataclass

from .swiss_data import MONTHS


@dataclass
class Span:
    start: int
    end: int
    label: str
    score: float = 1.0
    source: str = ""

    def as_dict(self):
        return {"start": self.start, "end": self.end, "label": self.label,
                "score": round(self.score, 3), "source": self.source}


# --- validators --------------------------------------------------------------

def ean13_ok(digits: str) -> bool:
    """AHVN13 uses the EAN-13 check digit."""
    if len(digits) != 13 or not digits.isdigit():
        return False
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(digits[:12]))
    return (10 - total % 10) % 10 == int(digits[12])


def ahv_valid(text: str) -> bool:
    return ean13_ok(re.sub(r"\D", "", text))


# --- patterns ----------------------------------------------------------------

UC = "A-ZÀ-ÖØ-ÞĀĂĄĆĈĊČĎĐĒĖĘĚĞĢĪĮİĶĹĻĽŁŃŅŇŌŐŒŔŘŚŞŠŢŤŨŪŮŰŲŹŻŽ"
LC = "a-zß-öø-ÿāăąćĉċčďđēėęěğģīįıķĺļľłńņňōőœŕřśşšţťũūůűųźżž"
NAME_TOKEN = rf"[{UC}][{LC}]+(?:[-'’][{UC}]?[{LC}]+)*"
NAME_SEQ = rf"{NAME_TOKEN}(?:[ ](?:(?:de|di|da|del|della|von|van|du|De|Di|Da|Von)[ ])?{NAME_TOKEN}){{0,2}}"

# Titles and honorifics (CH/DE/AT/FR/IT). Order matters: longer first.
HONORIFICS = (
    r"(?:(?i:Univ\.?-?Prof\.|Prof\.|Priv\.-?\s?Doz\.|Dr\.?\s?med\.?(?:\s?(?:univ(?:ers)?|dent|vet|mult)\.?)?|"
    r"Dr\.\s?rer\.\s?nat\.|Dr\.\s?mult\.|DDr\.|Dr\.a\.?|Dipl\.-?(?:Med|Ing)\.|Mag\.|MUDr\.|Dott\.ssa|Dott\.|Dr\.ssa)|"
    r"Dr\.|Dre?\s|PD|OA|OÄ|Pat\.|Ass\.|Doz\.|Univ\.-?Doz\.|DGKS|DGKP|Ltd\.|Prim\.|mult\.|med\.|univ\.|habil\.|"
    r"Herrn?|Frau|Hr\.|Fr\.|Fräulein|HERRN?|FRAU|"
    r"Madame|Monsieur|Mme|Mlle|M\.|"
    r"Sig\.ra|Sig\.|[Ss]ignora|[Ss]ignor|madame|monsieur)"
)
HONORIFIC_SEQ = rf"(?:{HONORIFICS}[ ]{{0,2}}){{1,4}}"

INITIALS = rf"(?:(?:[{UC}]|Ch|Th|Ph|St)\.\s?){{1,3}}"          # "K. O. ", "Ch. "
PARTICLE = r"(?:(?:de|von|van|di|da|del|della|du|zu|zur|ter)\s)?"
CAPS_TOKEN = rf"[{UC}]{{2,}}(?:[-'’][{UC}]{{2,}})*"           # "JOUBERT", "GILLIÈRON"
PERSON_NAME = (rf"(?:{INITIALS})?{PARTICLE}(?:{CAPS_TOKEN}|{NAME_TOKEN})"
               rf"(?:[ ](?:(?:de|di|da|del|della|von|van|du|zu|zur)[ ])?(?:{CAPS_TOKEN}|{NAME_TOKEN}|[{UC}]\.)){{0,2}}")
NAME_SEQ_CAPS = PERSON_NAME

FIELD_LABELS_PERSON = (
    r"(?:Name|Vorname|Patient(?:in)?|Versicherte[rn]?|Kontaktperson|Notfallkontakt|Angehörige|"
    r"Validiert|Visiert|Unterschrift|Geschrieben von|Diktat|dikt\.\s?Arzt|Arzt|Ärztin|Orthoptistin|"
    r"Betr(?:ifft|eff|\.)|"
    r"Nom|Prénom|Patiente?|Patient\(e\)|Personne de contact|Proche de référence|Validé par|"
    r"Nome|Cognome(?: e nome)?|Paziente|Persona di contatto|Familiare di riferimento|Validato da)"
)

# "M. Crohn" is Morbus Crohn, not a person called M. Crohn
EPONYMS = (r"Crohn|Parkinson|Alzheimer|Basedow|Bechterew|Addison|Hodgkin|Wilson|Menière|Meniere|Paget|"
           r"Scheuermann|Raynaud|Cushing|Dupuytren|Sudeck|Perthes|Osgood|Still|Fabry|Gaucher|Behçet|Behcet|"
           r"Waldenström|Waldenstrom|Hirschsprung|Huntington|Kienböck|Köhler|Ledderhose|Ormond|Pick|Whipple")

# signature block: a line holding only a name, directly followed by a role line
ROLE_LINE = (r"(?:Ober|Assistenz|Chef|Leitende[rn]? |Stations|Fach)?[Aa]rzt|Oberärztin|Assistenzärztin|Chefarzt|"
             r"Stationsärztin|Ltd\.|Direktor|Klinikvorstand|"
             r"Chef de clinique|Médecin(?: assistant| adjoint| chef)?|Capoclinica|Medico(?: assistente| capo)?|"
             r"Primario|Facharzt[^\n]*|Fachärztin[^\n]*|Spécialiste[^\n]*|Specialista[^\n]*")

MONTHS_ALL = "|".join(sorted({m for ms in MONTHS.values() for m in ms}, key=len, reverse=True))
MONTHS_ABBR = r"Jan|Feb|Mär|Mrz|Apr|Jun|Jul|Aug|Sept?|Okt|Nov|Dez|Janv|Févr|Avr|Juil|Déc|Gen|Mag|Giu|Lug|Ago|Set|Ott|Dic"
MONTH = rf"(?:{MONTHS_ALL}|(?:{MONTHS_ABBR})\.?)"
YEAR = r"(?:19|20)\d{2}"
DAY = r"(?:0?[1-9]|[12]\d|3[01])"
MON = r"(?:0?[1-9]|1[0-2])"

# German hospital / practice vocabulary (also matched inside compounds and in CAPS)
ORG_WORDS = (r"universitätsklinikum|uniklinik|klinikum|krankenhaus|krankenanstalt(?:en)?(?:verbund)?|"
             r"lehrkrankenhaus|kinderklinik|fachklinik|privatklinik|tagesklinik|poliklinik|klinik|"
             r"gemeinschaftspraxis|facharztpraxis|praxis|ordination|rehabilitationskrankenhaus|"
             r"rehabilitationsklinik|rehaklinik|reha[ -]?zentrum|landeskrankenhaus|bezirkskrankenhaus|"
             r"kreiskrankenhaus|kantonsspital|regionalspital|stadtspital|spital|sanatorium|hospiz|"
             r"hôpital|clinique|centre hospitalier|ospedale|clinica|"
             r"universität|hochschule|institut|mvz|lkh|kh|stiftung|zentrum|nervenklinik")
ORG_PREFIX = (r"(?:Städt\.|Städtisches|Evangelisches|Evang\.|Katholisches|Kath\.|Allgemeines|Akademisches|"
              r"Medizinische[sn]?|Private|Öffentliches|Diakonie|Barmherzige[n]?|Landes|St\.)\s")
ORG_TAIL_WORD = rf"(?:[{UC}][\w\-\.&]+|der|des|an der|de|di|du|des|régional|regionale|civico|San|St\.|Dr\.(?: med\.)?)"

CITY_TOKEN = rf"[{UC}][{LC}\.]*(?:-[{UC}{LC}][{LC}\.]*)*"      # "Yverdon-les-Bains", "St. Anna", "Alt-Neudorf"

STREET_SUFFIX = (r"straße|strasse|strße|str\.|gasse|weg|platz|allee|ring|damm|ufer|pfad|steig|promenade|"
                 r"chaussee|markt|hof|berg|tal|graben|zeile|landstraße|rain|halde|bühl|matte|kamp|busch|feld|wall")
STREET_NAME = rf"(?:[{UC}][{LC}]{{1,10}}(?:er|e|sche)[ ])?(?:[{UC}][\w\-]*(?i:{STREET_SUFFIX})|(?i:Straße|Strasse|Str\.|Gasse|Weg|Platz|Allee))\.?"

PHONE_KEY = r"(?:Tel(?:efon|efax|\.)?|Fax|Handy|Mobil(?:e|tel)?|Durchwahl|DW|Info|Sekretariat|Telefono|Cellulare|Tél(?:éphone)?|Portable)"
PHONE_BODY = r"(?:\+\d{2,3} ?)?(?:\(0?\d{1,5}\) ?)?\d[\d /().\-]{5,}\d(?: ?- ?DW)?"

ID_KEY = (r"(?:PIZ|PID|Patienten-?ID|Pat\.?-?ID|Vorgangs-?Nr|E-Nr|H-?Nr|Fallzahl|Fall-?Nr|Fallnummer|Fall|SV[ -]?Nr|SVNR|Sozialversicherungs-?Nr|SV|Aufnahme-?Nr|Pat\.?-?Nr|Patienten-?Nr|Protokoll[ -]?Nr|"
          r"Journal-?Nr|Auftrags-?Nr|Befund-?Nr|Labor-?Nr|Vers\.?-?Nr|Versicherungs-?Nr|Versichertennummer|KVNR|"
          r"Histologie|Histo|Zytologie|Präparat|Aktenzeichen|Az|Unsere Zeichen|Unser Zeichen|Ihr Zeichen|"
          r"N°\s?(?:de\s)?(?:dossier|patient|cas)|No\.?\s?patient|N\.\s?(?:paziente|caso|cartella)|Numero (?:paziente|caso))")
STATION_KEY = r"(?:Station|Stat\.|Zi\.?|Zimmer|Bett|Ambulanz|Abteilung)"


def phone_valid(v: str) -> bool:
    d = re.sub(r"\D", "", v)
    return 7 <= len(d) <= 16


TITLE_WORDS = {"dr", "prof", "med", "mba", "oa", "oä", "pd", "msc", "bsc", "univ", "dent", "phil", "jur", "nat"}


def person_valid(v: str) -> bool:
    toks = re.findall(r"[^\s.]+", v)
    if not toks:
        return False
    if re.match(rf"^M\.\s?(?:{EPONYMS})$", v):                 # Morbus, not Monsieur
        return False
    # "B. Pantozol", "T. Fieber": an initial followed by a drug or clinical word is an abbreviation
    from .medical_terms import DENY as _MED, DRUG_SUFFIXES as _DS, MEDICAL_SUFFIXES as _MS
    last = toks[-1].lower()
    if len(toks) >= 2 and len(toks[0]) == 1 and (last in _MED or last.endswith(_DS) or last.endswith(_MS)):
        return False                                             # initial-led only: "Dr. Heinz Hals" is a name
    return True


def year_valid(v: str) -> bool:
    return 1900 <= int(v) <= 2099


RULES = [
    # --- identifiers with fixed structure ---------------------------------------
    ("AHV_NUMBER", re.compile(r"\b756[.\s]?\d{4}[.\s]?\d{4}[.\s]?\d{2}\b"), 1.0, ahv_valid),
    ("INSURANCE_CARD", re.compile(r"\b80756(?:[ ]?\d){15}\b"), 1.0, None),
    ("IBAN", re.compile(r"\b(?:CH|DE|AT|FR|IT|LI)\d{2}(?:[ ]?[0-9A-Z]){11,30}\b"), 1.0, None),
    ("EMAIL", re.compile(r"\b[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+\b"), 1.0, None),

    # --- phones ------------------------------------------------------------------
    # Swiss, with or without keyword
    ("PHONE", re.compile(
        r"(?<![\d.])(?:\+41|0041)[ ]?(?:\(0\)[ ]?)?\d{2}[ ]?\d{3}[ ]?\d{2}[ ]?\d{2}\b"
        r"|(?<![\d.])0\d{2}[ ]?\d{3}[ ]?\d{2}[ ]?\d{2}\b"), 0.95, None),
    # international +49 / +43 / +33 ...
    ("PHONE", re.compile(r"(?<![\d\w])\+\d{2,3} ?\(?0?\)? ?\d[\d /().\-]{5,}\d(?: ?- ?DW)?"), 0.9, phone_valid),
    # German / Austrian national: 0xxx/xxx-xxxx, 030 110-2401, 0699-15099887, (0461) 708 - 223
    ("PHONE", re.compile(r"(?<![\d\w.])\(?0\d{2,4}\)?[ /\-] ?\d{2,}(?: ?[ \-/] ?\d{2,})*\b"), 0.85, phone_valid),
    # after a keyword, anything phone-shaped
    ("PHONE", re.compile(rf"\b{PHONE_KEY}\s*[:.]?\s*(?P<v>{PHONE_BODY})"), 0.9, phone_valid),
    # alternative extension: "Tel 030 110-2612 o. 2522"
    ("PHONE", re.compile(r"(?<=\d)\s(?:o\.|od\.|oder|/)\s(?P<v>\d{3,5})\b"), 0.7, None),

    # --- patient / case / station numbers ----------------------------------------
    ("PATIENT_ID", re.compile(
        rf"\b{ID_KEY}\.?\s*:?\s*\(?(?P<v>[A-Z]{{0,3}}-?\d[\w\-/]{{3,}})"), 0.95, None),
    ("PATIENT_ID", re.compile(
        rf"\b{STATION_KEY}\s*:?\s*(?P<v>[A-Z]{{1,3}}-?\d+|\d{{1,4}}(?:\s?(?:Süd|Nord|Ost|West))?|[A-Z]\d+)(?!\w)"), 0.7, None),
    # histology / specimen numbers in parentheses: "(37848/2019: tumorfrei)"
    ("PATIENT_ID", re.compile(r"\((?P<v>[A-Z]?\d{4,7}[a-z]?/\d{2,4})(?=[:)])"), 0.7, None),

    # --- dates -------------------------------------------------------------------
    # d.m.yyyy, d/m/yyyy, d.m.yy, "10. 03. 2043", "23.04 2029", "8.11. 2064"
    ("DATE", re.compile(rf"\b{DAY}[./]\s?{MON}(?:[./]\s?|\s){YEAR}(?!\d)"), 0.95, None),
    ("DATE", re.compile(rf"\b{DAY}[./]{MON}[./]\d{{2}}\b(?![./]\d)"), 0.9, None),
    ("DATE", re.compile(rf"\b{YEAR}-\d{{2}}-\d{{2}}\b"), 0.95, None),
    # day.month. without year: "2.11.", "vom 2.11. – 24.11.28"
    ("DATE", re.compile(rf"\b{DAY}\.{MON}\.(?!\s?\d)"), 0.8, None),
    # month/year: 11/18, 07/2022, 9/20 ; and first month of a range "03-06/2022", "10-11/2022"
    ("DATE", re.compile(rf"(?<![\d/.])\b{MON}/(?:{YEAR}|\d{{2}})\b(?!/)"), 0.85, None),
    ("DATE", re.compile(rf"(?<![\d/.])\b(?P<v>{MON})\s?-\s?{MON}/(?:{YEAR}|\d{{2}})\b"), 0.8, None),
    # "27. März 2025", "1. Nov", "5. März2063", "17. August 2033"
    ("DATE", re.compile(rf"\b{DAY}\.?\s?{MONTH}(?:\s?{YEAR})?(?![{LC}])"), 0.9, None),
    # "November 2019", "Sept. 2063", "Oktober\n2012"
    ("DATE", re.compile(rf"\b{MONTH}\s*{YEAR}\b"), 0.9, None),
    # "August 27" (US style)
    ("DATE", re.compile(rf"\b{MONTH}\s{DAY}\b(?![./])"), 0.6, None),
    # month name alone in a temporal phrase: "von Juni bis November 2019", "im Oktober"
    ("DATE", re.compile(rf"\b(?:im|seit|ab|von|bis|Ende|Anfang|Mitte|Beginn)\s(?P<v>{MONTH})(?![{LC}])"), 0.6, None),
    # bare year: GeMTeX/GraSCCo guideline treats "Z.n. Mamma-Ca 2037" as a date.
    # Guarded against doses and ranges ("2000 mg", "1500-2000")
    ("DATE", re.compile(rf"(?<![\w.,/\-])(?P<v>{YEAR})(?![\w/\-]|[.,]\d|\s?(?:mg|ml|g|µg|mcg|U|IE|E|%|kcal|mm|cm|ms|Hz|x)\b)"), 0.6, year_valid),
    # range starts: "05.11-18.11.2024", "06-07.11.2024", "1. - 21. Juli 2022", "vom 10 und 11.10.2033", "26 09.2033"
    ("DATE", re.compile(rf"\b(?P<v>{DAY}\.{MON})\.?(?=\s?[-–]\s?{DAY}\.{MON}\.)"), 0.8, None),
    ("DATE", re.compile(rf"\b(?P<v>{DAY})\.?(?=\s?(?:[-–]|und|bis)\s?{DAY}\.\s?(?:{MON}\.|{MONTH}))"), 0.7, None),
    ("DATE", re.compile(rf"\b{DAY}\s{MON}\.{YEAR}\b"), 0.8, None),

    # --- addresses ---------------------------------------------------------------
    ("STREET_ADDRESS", re.compile(rf"\b{STREET_NAME} ?\d{{1,4}}(?: ?[a-z])?\b"), 0.9, None),
    ("STREET_ADDRESS", re.compile(rf"\b{STREET_NAME}(?=,?\s+(?:D-|A-|CH-|L-)?\d{{4,5}}\s)"), 0.85, None),
    ("STREET_ADDRESS", re.compile(
        rf"\b(?:Im|Am|Auf der|In der|An der|Zum|Zur)[ ][{UC}][{LC}\-]+(?:[ ]\d{{1,4}}\s?[a-z]?)?\b(?=\s*(?:,|\n|$))"), 0.8, None),
    ("STREET_ADDRESS", re.compile(
        rf"\b(?:Rue|Avenue|Chemin|Route|Place|Boulevard|Via|Viale|Piazza|Vicolo|Strada)"
        rf"(?:[ ][\w'’\-]+){{1,5}}?[ ]\d{{1,4}}[a-z]?\b"), 0.9, None),
    # ZIP + locality: CH 4 digits, DE 5 digits, A-/D-/CH- prefixes
    ("LOCATION", re.compile(
        rf"\b(?:(?:CH|D|A|L|F|I)-)?(?:[1-9]\d{{3}}|\d{{5}})[ ]+(?P<v>{CITY_TOKEN}(?:[ ](?:{CITY_TOKEN}|les|la|de|sur|am|an|im|in|bei|an der|im Tal)){{0,3}})"),
        0.85, None),
    # locality before a date in a letter head: "Berlin, den 22.06.2032", "Flensburg, 27. März 2025"
    ("LOCATION", re.compile(rf"(?m)^[ \t]*(?P<v>{NAME_TOKEN}(?:[ \-]{NAME_TOKEN})?),\s(?:den\s|am\s|le\s|il\s)?(?=\d{{1,2}}[. ])"), 0.8, None),
    # "wohnhaft in Wiesental", "domiciliée à Nyon", "domiciliato a Savosa"
    ("LOCATION", re.compile(rf"\b(?:wohnhaft(?: in)?|domicilié[e]?\sà|domiciliat[oa]\sa)\s(?P<v>{NAME_TOKEN}(?:[ \-]{NAME_TOKEN})?)(?=[\s,.])"), 0.6, None),

    # --- institutions --------------------------------------------------------------
    ("ORGANIZATION", re.compile(
        rf"(?i)\b(?:{ORG_PREFIX})?[\w\-]*(?:{ORG_WORDS})(?-i:(?:[ ]{ORG_TAIL_WORD}){{1,4}})"), 0.85, None),
    ("ORGANIZATION", re.compile(
        rf"\b[{UC}][\w\-]+-(?:Klinik|Krankenhaus|Spital|Klinikum|Praxis|Zentrum)\b"), 0.85, None),
    ("ORGANIZATION", re.compile(
        rf"\b(?:Praxis|Ordination|Gemeinschaftspraxis)\s(?:{HONORIFIC_SEQ})?{PERSON_NAME}"), 0.85, None),

    # --- names ---------------------------------------------------------------------
    # honorific(s) + name, with initials and particles: "Prof. Dr. Ch. Janssen", "Frau de Beauharnais"
    ("PERSON", re.compile(rf"(?<![\w])(?:{HONORIFIC_SEQ})(?P<v>{PERSON_NAME})"), 0.85, person_valid),
    # honorific + lone initial: "Herr V.", "Frau W."
    ("PERSON", re.compile(rf"\b(?:Herrn?|Frau|Hr\.|Fr\.)\s(?P<v>[{UC}]\.)(?!\s?[{UC}])"), 0.8, None),
    # field label + name: "Patient: Schwab Vivien", "Betrifft: Tupolev, Konstantin"
    ("PERSON", re.compile(rf"\b{FIELD_LABELS_PERSON}(?:[ \t]*:[ \t]*|[ \t]+)(?P<v>{PERSON_NAME}(?:,\s{NAME_TOKEN}(?:-{NAME_TOKEN})?)?)"), 0.85, None),
    # surname-first with comma after a person context: "Patientin Haefner, Heinz", "über Frau CHRIST, Charlotte"
    ("PERSON", re.compile(
        rf"\b(?:Patient(?:en|in)?|Frau|Herrn?|Betrifft:?|Betr\.?:?)\s(?P<v>(?:{CAPS_TOKEN}|{NAME_TOKEN}),\s{NAME_TOKEN}(?:-{NAME_TOKEN})?)"), 0.85, None),
    # initials + surname without honorific: "J. Thiel", "K. O. von Hausen"; not "M. Crohn"
    ("PERSON", re.compile(rf"(?<![\w.])(?<![zusovZUSOV]\. )(?<![zusovZUSOV]\.)(?P<v>(?!I\.|V\.\s?a|Z\.\s?n){INITIALS}{PARTICLE}{NAME_TOKEN})(?![{LC}])"), 0.6, person_valid),
    # surname + initial (signature list): "Hendlbein H.", "Brunzli B."
    ("PERSON", re.compile(rf"(?:(?m:^)|:\s|\|\s|\t)[ ]*(?P<v>(?!(?:Herrn?|Frau|Hr|Fr)\b){NAME_TOKEN} (?!M\.|N\.|V\.|A\.)[{UC}]\.)(?=\s|$)"), 0.6, None),
    # signature block: name line followed by a role line
    ("PERSON", re.compile(rf"(?m)^(?P<v>(?:{INITIALS})?{NAME_TOKEN}(?:[ ]{NAME_TOKEN}){{1,2}})[ \t]*\n(?:{ROLE_LINE})"), 0.8, None),
    ("PERSON", re.compile(rf"(?m)^(?P<v>{NAME_TOKEN}(?:[ ]{NAME_TOKEN}){{1,2}})[ ]*$(?![\s\S])"), 0.6, None),
    # name directly followed by a birth marker or a date: "Luise Utz, * 3.4.1959", "Evelyn Dewald * 13.08.1948",
    # "Andrea Ilgner,  21.10.1982", "Irina Popovic, geb. am 17.08.1958"
    ("PERSON", re.compile(
        rf"(?<![\w.])(?P<v>{NAME_TOKEN}(?:[ ](?:(?:von|van|de|zur|zu)[ ])?{NAME_TOKEN}){{1,2}}),?[ ]{{1,3}}(?:\*|geb\.(?:\sam)?|geboren(?:\sam)?)?[ ]?(?={DAY}\.{MON}\.\d{{2}})"), 0.85, None),
    # "Weil, Klementine, geb. 16.01.1993" at line start, no trigger word
    ("PERSON", re.compile(
        rf"(?m)^[ \t]*(?P<v>(?:{CAPS_TOKEN}|{NAME_TOKEN}),\s{NAME_TOKEN}(?:-{NAME_TOKEN})?)(?=,?\s*(?:\*|geb\.|geboren|né[e]?\sle|nat[oa]\sil))"), 0.85, None),
    # signature line with role in parentheses or title after the name: "Kevin Schlauberger (Stationsarzt)", "Ida Fuß, Dr. med."
    ("PERSON", re.compile(
        rf"(?m)^[ \t]*(?P<v>{NAME_TOKEN}(?:[ ]{NAME_TOKEN}){{1,2}})(?:\s\((?:{ROLE_LINE})\)|,\s(?:{HONORIFIC_SEQ}))"), 0.8, None),
    # "gez. Dr.med.univers. B. Supanic", "i.A. Müller"
    ("PERSON", re.compile(rf"\b(?:gez\.|i\.\s?A\.|i\.\s?V\.)\s?(?:{HONORIFIC_SEQ})?(?P<v>{PERSON_NAME})"), 0.8, None),
]

# LOCATION rule above captures the locality only. Include the PLZ too.
_LOC_FULL = True


def detect(text: str):
    spans = []
    for label, rx, score, validator in RULES:
        for m in rx.finditer(text):
            if "v" in rx.groupindex:
                s, e = m.start("v"), m.end("v")
                if label == "LOCATION" and _LOC_FULL:
                    s = m.start()
            else:
                s, e = m.start(), m.end()
            if label == "PERSON":                       # "Hanns Wurst OA" -> "Hanns Wurst"
                while True:
                    m2 = re.search(r"\s[^\s.]+\.?$", text[s:e])
                    if m2 and m2.group(0).strip(" .").lower() in TITLE_WORDS:
                        e = s + m2.start()
                    else:
                        break
            if validator and not validator(text[s:e]):
                continue
            if label == "PERSON" and re.fullmatch(rf"(?:{EPONYMS})", text[s:e]) \
                    and re.search(r"(?:\bM\.|\bMorbus|\bMb\.)\s?$", text[:s]):
                continue
            spans.append(Span(s, e, label, score, "rules"))
    return spans
