"""
Synthetic Swiss medical document generator with gold PII spans.

Every PII value is inserted through a template slot, so the exact character
offsets are known. That gives free, exact ground truth for evaluation.

Documents: discharge letter, lab report, referral letter. Languages: DE/FR/IT.
Templates deliberately include hard cases:
  - names without honorific in free text
  - first name only, surname-first, UPPERCASE surnames (FR style)
  - lowercase honorifics in Italian prose ("la signora Bianchi")
  - eponymous diagnoses (Morbus Parkinson) and insurer names as non-PII distractors
"""
import random
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta

from faker import Faker

from . import swiss_data as SD


@dataclass
class PII:
    value: str
    label: str


SLOT_RX = re.compile(r"\{(\w+)\}")


def render(template: str, ctx: dict):
    """Fill {slots}. PII slots produce gold spans, str slots are plain text."""
    out, spans, pos = [], [], 0
    last = 0
    for m in SLOT_RX.finditer(template):
        literal = template[last:m.start()]
        out.append(literal)
        pos += len(literal)
        val = ctx[m.group(1)]
        if isinstance(val, PII):
            out.append(val.value)
            spans.append({"start": pos, "end": pos + len(val.value), "label": val.label})
            pos += len(val.value)
        else:
            out.append(str(val))
            pos += len(str(val))
        last = m.end()
    out.append(template[last:])
    return "".join(out), spans


def concat(parts):
    """Join rendered blocks with newlines, shifting span offsets."""
    text, spans, off = [], [], 0
    for t, sp in parts:
        text.append(t)
        spans.extend({**s, "start": s["start"] + off, "end": s["end"] + off} for s in sp)
        off += len(t) + 1
    return "\n".join(text), spans


def ascii_fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z]", "", s).lower()


# --- value factories ---------------------------------------------------------

FAKER_LOCALE = {"de": "de_CH", "fr": "fr_CH", "it": "it_IT"}   # it_CH in Faker is broken
AREA = {"de": ["44", "43", "52", "56", "61", "62", "31", "41", "71", "81"],
        "fr": ["21", "22", "24", "26", "27", "32"],
        "it": ["91"]}
MOBILE = ["76", "77", "78", "79"]


class ValueFactory:
    def __init__(self, lang: str, rng: random.Random):
        self.lang, self.rng = lang, rng
        self.fk = Faker(FAKER_LOCALE[lang])
        self.fk.seed_instance(rng.randint(0, 10**9))
        self.fk_ch = Faker("de_CH")                   # AHV + IBAN generator
        self.fk_ch.seed_instance(rng.randint(0, 10**9))

    def person(self, sex):
        f = self.fk.first_name_female() if sex == "f" else self.fk.first_name_male()
        return f, self.fk.last_name()

    def locality(self):
        return self.rng.choice(SD.LOCALITIES[self.lang])

    def street(self):
        pat = self.rng.choice(SD.STREET_PATTERNS[self.lang])
        name = self.fk.last_name()
        street = pat.format(name=name)
        no = str(self.rng.randint(1, 120)) + (self.rng.choice("ab") if self.rng.random() < 0.1 else "")
        return f"{street} {no}"

    def hospital(self):
        pat = self.rng.choice(SD.HOSPITAL_PATTERNS[self.lang])
        return pat.format(city=self.locality()[1], name=self.fk.last_name())

    def phone(self, mobile=False):
        a = self.rng.choice(MOBILE if mobile else AREA[self.lang])
        d = [str(self.rng.randint(0, 9)) for _ in range(7)]
        d[0] = str(self.rng.randint(2, 9))
        x, y, z = "".join(d[:3]), "".join(d[3:5]), "".join(d[5:])
        fmt = self.rng.choices(
            [f"0{a} {x} {y} {z}", f"+41 {a} {x} {y} {z}", f"+41{a}{x}{y}{z}", f"0041 {a} {x} {y} {z}"],
            weights=[5, 4, 1, 1])[0]
        return fmt

    def email(self, first, last):
        f, l = ascii_fold(first), ascii_fold(last)
        local = self.rng.choice([f"{f}.{l}", f"{f[0]}.{l}", f"{f}{l}{self.rng.randint(1, 99)}", f"{l}.{f}"])
        return f"{local}@{self.rng.choice(SD.EMAIL_DOMAINS)}"

    def ahv(self):
        return self.fk_ch.ssn()   # 756.XXXX.XXXX.XC, valid EAN-13

    def iban(self):
        raw = self.fk_ch.iban()
        return raw if self.rng.random() < 0.3 else " ".join(raw[i:i + 4] for i in range(0, len(raw), 4))

    def card(self):
        digits = "80756" + "".join(str(self.rng.randint(0, 9)) for _ in range(15))
        return digits if self.rng.random() < 0.4 else " ".join(digits[i:i + 5] for i in range(0, 20, 5))

    def pid(self):
        return str(self.rng.randint(10_000_000, 19_999_999))

    def case_id(self, year):
        return f"{year}-{self.rng.randint(1_000_000, 9_999_999)}"

    def date(self, d: date):
        if self.rng.random() < 0.6:
            return d.strftime("%d.%m.%Y")
        m = SD.MONTHS[self.lang][d.month - 1]
        if self.lang == "de":
            return f"{d.day}. {m} {d.year}"
        return f"{d.day} {m} {d.year}"


# --- language packs ----------------------------------------------------------

LANG = {
    "de": dict(
        hon={"f": "Frau", "m": "Herr"},
        noun={"f": "Die Patientin", "m": "Der Patient"},
        acc={"f": "die Patientin", "m": "den Patienten"},
        my={"f": "meine Patientin", "m": "meinen Patienten"},
        rel={"f": [("ihrem Ehemann", "m"), ("ihrer Tochter", "f"), ("ihrem Sohn", "m")],
             "m": [("seiner Ehefrau", "f"), ("seiner Tochter", "f"), ("seinem Sohn", "m")]},
        born={"f": "geb.", "m": "geb."},
        sexl={"f": "w", "m": "m"},
    ),
    "fr": dict(
        hon={"f": "Mme", "m": "M."},
        hon_long={"f": "Madame", "m": "Monsieur"},
        noun={"f": "La patiente", "m": "Le patient"},
        acc={"f": "la patiente", "m": "le patient"},
        my={"f": "ma patiente", "m": "mon patient"},
        rel={"f": [("son mari", "m"), ("sa fille", "f"), ("son fils", "m")],
             "m": [("son épouse", "f"), ("sa fille", "f"), ("son fils", "m")]},
        born={"f": "née le", "m": "né le"},
        acc_agree={"f": "e", "m": ""},
        sexl={"f": "F", "m": "M"},
    ),
    "it": dict(
        hon={"f": "Sig.ra", "m": "Sig."},
        hon_prose={"f": "la signora", "m": "il signor"},
        noun={"f": "La paziente", "m": "Il paziente"},
        acc={"f": "la paziente", "m": "il paziente"},
        my={"f": "la mia paziente", "m": "il mio paziente"},
        rel={"f": [("dal marito", "m"), ("dalla figlia", "f"), ("dal figlio", "m")],
             "m": [("dalla moglie", "f"), ("dalla figlia", "f"), ("dal figlio", "m")]},
        born={"f": "nata il", "m": "nato il"},
        agree={"f": "a", "m": "o"},
        sexl={"f": "F", "m": "M"},
    ),
}


def build_context(lang, rng: random.Random, vf: ValueFactory):
    L = LANG[lang]
    sex = rng.choice("fm")
    first, last = vf.person(sex)
    rel_phrase, rel_sex = rng.choice(L["rel"][sex])
    rel_first, rel_last = vf.person(rel_sex)
    if rel_phrase in ("ihrem Ehemann", "seiner Ehefrau", "son mari", "son épouse", "dal marito", "dalla moglie") \
            and rng.random() < 0.7:
        rel_last = last
    d1f, d1l = vf.person(rng.choice("fm"))
    d2f, d2l = vf.person(rng.choice("fm"))
    gpf, gpl = vf.person(rng.choice("fm"))
    plz, city = vf.locality()
    gp_plz, gp_city = vf.locality()

    dob = date(rng.randint(1932, 2004), rng.randint(1, 12), rng.randint(1, 28))
    adm = date(2025, 1, 1) + timedelta(days=rng.randint(0, 600))
    dis = adm + timedelta(days=rng.randint(2, 14))
    exam = adm + timedelta(days=rng.randint(0, 2))
    docd = dis + timedelta(days=rng.randint(0, 4))

    # FR documents often write the surname in capitals
    pat_last_disp = last.upper() if (lang == "fr" and rng.random() < 0.5) else last
    lab_rows = []
    for names, (lo, hi), unit, ref in SD.LAB["rows"]:
        v = rng.uniform(lo, hi)
        v = f"{v:.0f}" if hi > 50 else f"{v:.1f}"
        lab_rows.append(f"{names[lang]:<14} {v:>7} {unit:<7} ({ref})")

    dx = rng.sample(range(len(SD.DIAGNOSES[lang])), 2)
    drugs = rng.sample(SD.DRUGS, 3)
    ctx = dict(
        pat_full=PII(f"{first} {last}", "PERSON"),
        pat_rev=PII(f"{pat_last_disp} {first}", "PERSON"),
        pat_last=PII(last, "PERSON"),
        pat_first=PII(first, "PERSON"),
        rel_full=PII(f"{rel_first} {rel_last}", "PERSON"),
        rel_first=PII(rel_first, "PERSON"),
        doc1=PII(f"{d1f} {d1l}", "PERSON"),
        doc2=PII(f"{d2f} {d2l}", "PERSON"),
        gp=PII(f"{gpf} {gpl}", "PERSON"),
        gp_last=PII(gpl, "PERSON"),
        dob=PII(vf.date(dob), "DATE"),
        adm=PII(vf.date(adm), "DATE"),
        dis=PII(vf.date(dis), "DATE"),
        exam=PII(vf.date(exam), "DATE"),
        doc_date=PII(vf.date(docd), "DATE"),
        ahv=PII(vf.ahv(), "AHV_NUMBER"),
        card=PII(vf.card(), "INSURANCE_CARD"),
        pid=PII(vf.pid(), "PATIENT_ID"),
        case_id=PII(vf.case_id(adm.year), "PATIENT_ID"),
        phone=PII(vf.phone(), "PHONE"),
        mobile=PII(vf.phone(mobile=True), "PHONE"),
        rel_phone=PII(vf.phone(mobile=True), "PHONE"),
        gp_phone=PII(vf.phone(), "PHONE"),
        email=PII(vf.email(first, last), "EMAIL"),
        iban=PII(vf.iban(), "IBAN"),
        street=PII(vf.street(), "STREET_ADDRESS"),
        gp_street=PII(vf.street(), "STREET_ADDRESS"),
        plz_city=PII(f"{plz} {city}", "LOCATION"),
        city=PII(city, "LOCATION"),
        gp_plz_city=PII(f"{gp_plz} {gp_city}", "LOCATION"),
        gp_city=PII(gp_city, "LOCATION"),
        hospital=PII(vf.hospital(), "ORGANIZATION"),
        # plain text (not PII)
        hon=L["hon"][sex], noun=L["noun"][sex], acc=L["acc"][sex], my=L["my"][sex],
        rel=rel_phrase, born=L["born"][sex], sexl=L["sexl"][sex],
        dx1=SD.DIAGNOSES[lang][dx[0]], dx2=SD.DIAGNOSES[lang][dx[1]],
        icd1=SD.ICD[dx[0] % len(SD.ICD)], icd2=SD.ICD[dx[1] % len(SD.ICD)],
        drug1=drugs[0], drug2=drugs[1], drug3=drugs[2],
        insurer=rng.choice(SD.INSURERS), year=str(adm.year),
        lab="\n".join(lab_rows),
        t1=f"{rng.randint(6, 9):02d}:{rng.randint(0, 59):02d}",
        t2=f"{rng.randint(10, 12):02d}:{rng.randint(0, 59):02d}",
    )
    for k in ("hon_long", "hon_prose", "acc_agree", "agree"):
        if k in L:
            ctx[k] = L[k][sex]
    return ctx


# --- templates ---------------------------------------------------------------
# A document is a list of blocks. Each block is (probability, [alternatives]).

T = {}

T[("de", "discharge")] = [
    (1, ["{hospital}\nKlinik für Innere Medizin"]),
    (1, ["\nAustrittsbericht vom {doc_date}\n"]),
    (1, ["Patient: {pat_rev}, {born} {dob}", "Name: {pat_full}\nGeburtsdatum: {dob}"]),
    (1, ["AHV-Nr.: {ahv}"]),
    (1, ["Adresse: {street}, {plz_city}"]),
    (0.8, ["Tel.: {phone}", "Telefon: {phone}, mobil {mobile}"]),
    (0.4, ["E-Mail: {email}"]),
    (1, ["Versichertenkarte: {card} ({insurer})"]),
    (1, ["PID {pid} / Fall-Nr. {case_id}\n"]),
    (1, ["Sehr geehrte Frau Kollegin, sehr geehrter Herr Kollege\n"]),
    (1, ["Wir berichten über {hon} {pat_full}, {born} {dob}, hospitalisiert vom {adm} bis {dis}.",
         "Wir berichten über {acc} {pat_full}, wohnhaft in {city}, hospitalisiert vom {adm} bis {dis}."]),
    (1, ["\nDiagnosen:\n1. {dx1} ({icd1})\n2. {dx2} ({icd2})\n"]),
    (1, ["Anamnese:\n{noun} wurde von {rel} {rel_full} auf die Notfallstation gebracht. Vorbekannt: {dx2}.",
         "Anamnese:\n{pat_full} stellte sich am {adm} notfallmässig vor. Vorbekannt: {dx2}.",
         "Anamnese:\nBei {hon} {pat_last} ist seit {year} ein {dx1} bekannt. Zuweisung durch Dr. med. {gp}."]),
    (1, ["\nVerlauf:\nUnter Therapie besserte sich der Zustand rasch. Visite durch Dr. med. {doc2} am {exam}.",
         "\nVerlauf:\n{pat_first} berichtete am {exam} über deutlich weniger Beschwerden. Die Mobilisation gelang problemlos.",
         "\nVerlauf:\nDie Laborwerte normalisierten sich. Gespräch mit {rel_first} über das weitere Procedere."]),
    (1, ["\nMedikation bei Austritt:\n- {drug1}\n- {drug2}\n- {drug3}"]),
    (1, ["\nProcedere:\nKontrolle beim Hausarzt Dr. med. {gp} in {gp_city} in zwei Wochen.",
         "\nProcedere:\nKlinische Kontrolle in 14 Tagen bei Dr. {gp_last}."]),
    (0.7, ["Angehörige: {rel_full}, Tel. {rel_phone}", "Notfallkontakt: {rel_full} ({rel_phone})"]),
    (1, ["\nFreundliche Grüsse\n\nDr. med. {doc1}\nOberarzt Innere Medizin\n\n{doc2}\nAssistenzarzt"]),
    (1, ["\nKopie an: Dr. med. {gp}, {gp_street}, {gp_plz_city}"]),
]

T[("de", "lab")] = [
    (1, ["{hospital}\nZentrallabor\n", "Labor {hospital}\n"]),
    (1, ["LABORBEFUND"]),
    (1, ["Auftraggeber: Dr. med. {gp}, {gp_plz_city}"]),
    (1, ["Patient: {pat_rev}    Geb.-Datum: {dob}    Geschlecht: {sexl}",
         "Name: {pat_full}, {dob}, {sexl}"]),
    (1, ["PID: {pid}"]),
    (1, ["Entnahme: {exam} {t1}    Eingang: {exam} {t2}\n"]),
    (1, ["Parameter       Wert    Einheit (Referenz)\n{lab}\n"]),
    (1, ["Kommentar: CRP erhöht, vereinbar mit {dx1}. Telefonische Rücksprache mit {hon} {pat_last} ({mobile}) erfolgt.",
         "Kommentar: Befund an Dr. {gp_last} übermittelt. Verlaufskontrolle empfohlen.",
         "Kommentar: Hämolytische Probe, Kalium nur eingeschränkt beurteilbar. {pat_first} wird erneut aufgeboten."]),
    (0.4, ["Rückerstattung via {insurer}, Konto des Versicherten: {iban}"]),
    (1, ["\nValidiert: {doc1}, {doc_date}"]),
]

T[("de", "referral")] = [
    (1, ["Dr. med. {gp}\nFacharzt für Allgemeine Innere Medizin FMH\n{gp_street}\n{gp_plz_city}\nTel. {gp_phone}\n"]),
    (1, ["{gp_city}, {doc_date}\n"]),
    (1, ["An: {hospital}, Medizinische Poliklinik\n"]),
    (1, ["Überweisung\nBetrifft: {hon} {pat_full}, {dob}\n{street}, {plz_city}\nAHV {ahv}\n"]),
    (1, ["Liebe Kolleginnen und Kollegen\n\nGerne überweise ich Ihnen {my} {pat_full} zur weiteren Abklärung bei Verdacht auf {dx1}.",
         "Liebe Kolleginnen und Kollegen\n\nIch bitte um Beurteilung von {hon} {pat_last} bei bekannter {dx2} und neuem Verdacht auf {dx1}."]),
    (1, ["{noun} wird von {rel} {rel_full} begleitet (erreichbar unter {rel_phone}).",
         "Kontakt: {mobile}, {email}.",
         "{pat_first} wünscht Korrespondenz per E-Mail an {email}."]),
    (1, ["Aktuelle Medikation: {drug1}, {drug2}.\nVersicherung: {insurer}, Karte {card}"]),
    (1, ["\nBesten Dank und freundliche Grüsse\n{gp}"]),
]

T[("fr", "discharge")] = [
    (1, ["{hospital}\nService de médecine interne"]),
    (1, ["\nLettre de sortie du {doc_date}\n"]),
    (1, ["Patient{acc_agree}: {pat_rev}, {born} {dob}", "Nom: {pat_rev}\nDate de naissance: {dob}"]),
    (1, ["N° AVS: {ahv}"]),
    (1, ["Adresse: {street}, {plz_city}"]),
    (0.8, ["Tél.: {phone}", "Téléphone: {phone}, portable {mobile}"]),
    (0.4, ["E-mail: {email}"]),
    (1, ["Carte d'assuré: {card} ({insurer})"]),
    (1, ["N° de dossier {pid} / N° de cas {case_id}\n"]),
    (1, ["Chère Consœur, cher Confrère,\n"]),
    (1, ["Nous vous adressons nos conclusions concernant {hon} {pat_full}, hospitalisé{acc_agree} du {adm} au {dis}.",
         "{hon_long} {pat_last}, domicilié{acc_agree} à {city}, a séjourné dans notre service du {adm} au {dis}."]),
    (1, ["\nDiagnostics:\n1. {dx1} ({icd1})\n2. {dx2} ({icd2})\n"]),
    (1, ["Anamnèse:\n{noun} a été amené{acc_agree} aux urgences par {rel} {rel_full}. Connu{acc_agree} pour une {dx2}.",
         "Anamnèse:\n{pat_full} s'est présenté{acc_agree} aux urgences le {adm}.",
         "Anamnèse:\nAdressé{acc_agree} par le Dr {gp} pour une {dx1} connue depuis {year}."]),
    (1, ["\nÉvolution:\nÉvolution favorable sous traitement. Visite du Dr {doc2} le {exam}.",
         "\nÉvolution:\n{pat_first} rapporte le {exam} une nette amélioration des symptômes.",
         "\nÉvolution:\nEntretien avec {rel_first} concernant la suite de la prise en charge."]),
    (1, ["\nTraitement à la sortie:\n- {drug1}\n- {drug2}\n- {drug3}"]),
    (1, ["\nSuite:\nContrôle chez le médecin traitant, Dr {gp}, à {gp_city} dans deux semaines.",
         "\nSuite:\nContrôle clinique dans 14 jours chez le Dr {gp_last}."]),
    (0.7, ["Proche de référence: {rel_full}, tél. {rel_phone}", "Personne de contact: {rel_full} ({rel_phone})"]),
    (1, ["\nAvec nos meilleures salutations confraternelles\n\nDr {doc1}\nChef de clinique\n\n{doc2}\nMédecin assistant"]),
    (1, ["\nCopie: Dr {gp}, {gp_street}, {gp_plz_city}"]),
]

T[("fr", "lab")] = [
    (1, ["{hospital}\nLaboratoire central\n"]),
    (1, ["RAPPORT DE LABORATOIRE"]),
    (1, ["Prescripteur: Dr {gp}, {gp_plz_city}"]),
    (1, ["Patient: {pat_rev}    Date de naissance: {dob}    Sexe: {sexl}",
         "Nom: {pat_rev}, {dob}, {sexl}"]),
    (1, ["N° patient: {pid}"]),
    (1, ["Prélèvement: {exam} {t1}    Réception: {exam} {t2}\n"]),
    (1, ["Paramètre       Valeur  Unité   (Référence)\n{lab}\n"]),
    (1, ["Commentaire: CRP élevée, compatible avec une {dx1}. Contact téléphonique avec {hon} {pat_last} ({mobile}).",
         "Commentaire: Résultats transmis au Dr {gp_last}. Contrôle recommandé.",
         "Commentaire: Échantillon hémolysé. {pat_first} sera reconvoqué{acc_agree}."]),
    (0.4, ["Remboursement via {insurer}, compte de l'assuré: {iban}"]),
    (1, ["\nValidé par: {doc1}, {doc_date}"]),
]

T[("fr", "referral")] = [
    (1, ["Dr {gp}\nSpécialiste FMH en médecine interne générale\n{gp_street}\n{gp_plz_city}\nTél. {gp_phone}\n"]),
    (1, ["{gp_city}, le {doc_date}\n"]),
    (1, ["À: {hospital}, Policlinique médicale\n"]),
    (1, ["Demande de consultation\nConcerne: {hon} {pat_full}, {born} {dob}\n{street}, {plz_city}\nAVS {ahv}\n"]),
    (1, ["Chers Collègues,\n\nJe vous adresse {my} {pat_full} pour bilan d'une suspicion de {dx1}.",
         "Chers Collègues,\n\nMerci de bien vouloir évaluer {hon_long} {pat_last}, connu{acc_agree} pour une {dx2}."]),
    (1, ["{noun} est accompagné{acc_agree} par {rel} {rel_full}, joignable au {rel_phone}.",
         "Contact: {mobile}, {email}.",
         "{pat_first} souhaite recevoir la correspondance par e-mail: {email}."]),
    (1, ["Traitement actuel: {drug1}, {drug2}.\nAssurance: {insurer}, carte {card}"]),
    (1, ["\nAvec mes remerciements et mes salutations distinguées\n{gp}"]),
]

T[("it", "discharge")] = [
    (1, ["{hospital}\nServizio di medicina interna"]),
    (1, ["\nLettera di dimissione del {doc_date}\n"]),
    (1, ["Paziente: {pat_rev}, {born} {dob}", "Cognome e nome: {pat_rev}\nData di nascita: {dob}"]),
    (1, ["N. AVS: {ahv}"]),
    (1, ["Indirizzo: {street}, {plz_city}"]),
    (0.8, ["Tel.: {phone}", "Telefono: {phone}, cellulare {mobile}"]),
    (0.4, ["E-mail: {email}"]),
    (1, ["Tessera d'assicurato: {card} ({insurer})"]),
    (1, ["N. paziente {pid} / N. caso {case_id}\n"]),
    (1, ["Gentile Collega,\n"]),
    (1, ["Le scriviamo in merito a {hon_prose} {pat_full}, ricoverat{agree} dal {adm} al {dis}.",
         "{hon} {pat_last}, domiciliat{agree} a {city}, è stat{agree} degent{agree} presso il nostro servizio dal {adm} al {dis}."]),
    (1, ["\nDiagnosi:\n1. {dx1} ({icd1})\n2. {dx2} ({icd2})\n"]),
    (1, ["Anamnesi:\n{noun} è stat{agree} accompagnat{agree} in pronto soccorso {rel} {rel_full}. Nota {dx2}.",
         "Anamnesi:\n{pat_full} si è presentat{agree} in pronto soccorso il {adm}.",
         "Anamnesi:\nInviat{agree} dal Dr. {gp} per {dx1} nota dal {year}."]),
    (1, ["\nDecorso:\nDecorso favorevole sotto terapia. Visita del Dr. {doc2} il {exam}.",
         "\nDecorso:\n{pat_first} riferisce il {exam} un netto miglioramento dei sintomi.",
         "\nDecorso:\nColloquio con {rel_first} sul proseguimento delle cure."]),
    (1, ["\nTerapia alla dimissione:\n- {drug1}\n- {drug2}\n- {drug3}"]),
    (1, ["\nProcedere:\nControllo dal medico curante, Dr. {gp}, a {gp_city} tra due settimane.",
         "\nProcedere:\nControllo clinico tra 14 giorni dal Dr. {gp_last}."]),
    (0.7, ["Familiare di riferimento: {rel_full}, tel. {rel_phone}", "Persona di contatto: {rel_full} ({rel_phone})"]),
    (1, ["\nCordiali saluti\n\nDr. {doc1}\nCapoclinica\n\n{doc2}\nMedico assistente"]),
    (1, ["\nCopia: Dr. {gp}, {gp_street}, {gp_plz_city}"]),
]

T[("it", "lab")] = [
    (1, ["{hospital}\nLaboratorio centrale\n"]),
    (1, ["REFERTO DI LABORATORIO"]),
    (1, ["Richiedente: Dr. {gp}, {gp_plz_city}"]),
    (1, ["Paziente: {pat_rev}    Data di nascita: {dob}    Sesso: {sexl}",
         "Cognome e nome: {pat_rev}, {dob}, {sexl}"]),
    (1, ["N. paziente: {pid}"]),
    (1, ["Prelievo: {exam} {t1}    Ricezione: {exam} {t2}\n"]),
    (1, ["Parametro       Valore  Unità   (Riferimento)\n{lab}\n"]),
    (1, ["Commento: PCR elevata, compatibile con {dx1}. Contatto telefonico con {hon_prose} {pat_last} ({mobile}).",
         "Commento: Risultati trasmessi al Dr. {gp_last}. Si consiglia controllo.",
         "Commento: Campione emolizzato. {pat_first} sarà riconvocat{agree}."]),
    (0.4, ["Rimborso tramite {insurer}, conto dell'assicurato: {iban}"]),
    (1, ["\nValidato da: {doc1}, {doc_date}"]),
]

T[("it", "referral")] = [
    (1, ["Dr. med. {gp}\nSpecialista FMH in medicina interna generale\n{gp_street}\n{gp_plz_city}\nTel. {gp_phone}\n"]),
    (1, ["{gp_city}, {doc_date}\n"]),
    (1, ["A: {hospital}, Policlinico medico\n"]),
    (1, ["Richiesta di consulenza\nConcerne: {hon} {pat_full}, {born} {dob}\n{street}, {plz_city}\nAVS {ahv}\n"]),
    (1, ["Cari Colleghi,\n\nVi invio {my} {pat_full} per accertamenti in caso di sospetto {dx1}.",
         "Cari Colleghi,\n\nVi chiedo una valutazione per {hon_prose} {pat_last}, affett{agree} da {dx2}."]),
    (1, ["{noun} è accompagnat{agree} {rel} {rel_full}, raggiungibile al {rel_phone}.",
         "Contatto: {mobile}, {email}.",
         "{pat_first} desidera ricevere la corrispondenza via e-mail: {email}."]),
    (1, ["Terapia attuale: {drug1}, {drug2}.\nAssicurazione: {insurer}, tessera {card}"]),
    (1, ["\nRingraziando, porgo cordiali saluti\n{gp}"]),
]


def generate_doc(lang, doc_type, rng, vf, doc_id):
    ctx = build_context(lang, rng, vf)
    parts = []
    for prob, alts in T[(lang, doc_type)]:
        if rng.random() <= prob:
            parts.append(render(rng.choice(alts), ctx))
    text, spans = concat(parts)
    for s in spans:                      # self-check: offsets must match values
        assert text[s["start"]:s["end"]].strip() == text[s["start"]:s["end"]]
    return {"id": doc_id, "lang": lang, "doc_type": doc_type, "text": text, "spans": spans}


def generate_corpus(languages, doc_types, per_lang, seed):
    rng = random.Random(seed)
    docs = []
    for lang in languages:
        vf = ValueFactory(lang, rng)
        for i in range(per_lang):
            dt = doc_types[i % len(doc_types)]
            docs.append(generate_doc(lang, dt, rng, vf, f"{lang}-{dt}-{i:04d}"))
    return docs
