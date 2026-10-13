"""
Clinical vocabulary that general-purpose NER mistakes for names, places and organisations.
Used by the utility filter (postprocess.utility_filter) on NER-sourced spans only; rules and
propagation are not affected. Lower-case, German with the usual Latin/English loans.

Extend from runs/<dataset>/<pipeline>/false_positives_top.csv, but only from the dev split.
"""

ANATOMY = """
kopf hals thorax abdomen becken wirbelsäule hws bws lws lendenwirbelsäule halswirbelsäule brustwirbelsäule
schädel gehirn hirn kleinhirn hirnstamm hypophyse schilddrüse thyreoidea larynx pharynx trachea bronchien
lunge lungen pulmo pleura mediastinum herz cor myokard perikard aorta vena arteria arterie vene
leber hepar galle gallenblase gallenwege pankreas milz lien niere nieren ren nebenniere harnblase blase
ureter urethra prostata hoden uterus ovar ovarien adnexe vagina zervix cervix mamma mammae brust
magen gaster ösophagus duodenum jejunum ileum colon kolon sigma rektum rectum anus darm dünndarm dickdarm
appendix peritoneum retroperitoneum omentum mesenterium zwerchfell diaphragma
schulter oberarm ellenbogen unterarm handgelenk hand finger daumen hüfte oberschenkel knie unterschenkel
sprunggelenk fuß zehe femur tibia fibula humerus radius ulna patella calcaneus talus os pubis os ilium
os sacrum sacrum coccyx sternum rippe rippen clavicula scapula pedikel lamina wirbel wirbelkörper bwk lwk hwk
bandscheibe diskus meniskus kreuzband ligament sehne muskel musculus m. nerv nervus n. plexus
haut cutis subcutis schleimhaut mukosa lymphknoten lymphknotenstation axilla axillär inguinal cervical
auge augen bulbus retina netzhaut makula macula linse hornhaut cornea iris vorderkammer glaskörper
sehnerv papille lid lider tränenwege ohr ohren innenohr mittelohr trommelfell nase nasennebenhöhlen
mund zunge zähne kiefer unterkiefer oberkiefer gaumen tonsillen
""".split()

CLINICAL_WORDS = """
pat patient patientin patienten befund befunde diagnose diagnosen anamnese therapie therapien verlauf
procedere prozedere empfehlung aufnahme entlassung entlassungsbefund aufnahmebefund status labor laborwerte
medikation medikamente medikament dosis dosierung tabletten tbl kapseln tropfen gtt injektion infusion
chemotherapie radiotherapie strahlentherapie immuntherapie antikörpertherapie hormontherapie
operation op eingriff resektion exstirpation biopsie punktion drainage stent katheter sonde
untersuchung kontrolle nachsorge vorstellung wiedervorstellung termin tumorboard tumorkonferenz
stadium staging restaging grading remission progression rezidiv metastase metastasen filiae
karzinom carcinom ca adenokarzinom adeno-ca plattenepithelkarzinom lymphom leukämie sarkom melanom
tumor tumoren neoplasie raumforderung läsion knoten zyste polyp
fraktur ruptur luxation kontusion distorsion prellung wunde narbe ulkus ulcus
entzündung infekt infektion sepsis pneumonie bronchitis zystitis pyelonephritis gastritis kolitis
hypertonie hypotonie diabetes adipositas niereninsuffizienz herzinsuffizienz vorhofflimmern
anämie tumoranämie thrombozytopenie leukopenie leukozytose nikotinabusus alkoholabusus
unauff unauffällig unauffällige auffällig regelrecht regelrechte altersentsprechend
bds beidseits rechts links re li bilateral zentral peripher proximal distal kranial kaudal ventral dorsal
klinisch klinische klinischer körperlich körperl körperliche neurologisch neurologische
sonographie sono ultraschall echokardiographie echo röntgen rö ct mrt mr pet szintigraphie endoskopie
koloskopie gastroskopie bronchoskopie zystoskopie ekg eeg emg lufu spirometrie plethysmographie
histologie histo zytologie pathologie referenzpathologie immunhistochemie
hämoglobin hb hämatokrit hk leukozyten leuko erythrozyten ery thrombozyten thrombo
kreatinin serum-kreatinin harnstoff gfr natrium kalium kalzium calcium chlorid phosphat magnesium
bilirubin got gpt ggt ap ldh lipase amylase crp bsg pct inr ptt quick fibrinogen d-dimer
tsh ft3 ft4 hba1c glukose glucose cholesterin ldl hdl triglyceride ferritin transferrin eisen
cea ca19-9 ca-125 psa afp hcg nse ldh mch mchc mcv rdw
protokoll schema zyklus zyklen woche wochen tag tage monat monate jahr jahre stunden uhr
salbe lsg lösung drg dragees tbl supp creme gel formel level grad grades plastik
department abteilung ambulanz hochschulambulanz poliklinik sprechstunde sekretariat direktor
bekannter bekannte bekannt mit ohne bei nach vor seit unter zur zum vom aus der des die das
""".split()

DRUGS = """
metformin insulin ramipril enalapril lisinopril candesartan valsartan losartan amlodipin nifedipin
bisoprolol metoprolol carvedilol atorvastatin simvastatin rosuvastatin pantoprazol omeprazol esomeprazol
ass aspirin clopidogrel marcumar phenprocoumon xarelto rivaroxaban eliquis apixaban pradaxa dabigatran
heparin enoxaparin clexane fragmin torasemid furosemid lasix hct spironolacton
paracetamol novalgin metamizol novaminsulfon ibuprofen diclofenac naproxen tramadol tilidin oxycodon
morphin fentanyl hydromorphon dafalgan tramal targin
prednison prednisolon dexamethason methylprednisolon cortison hydrocortison
amoxicillin ampicillin penicillin cefuroxim ceftriaxon ciprofloxacin levofloxacin moxifloxacin
clarithromycin azithromycin doxycyclin metronidazol vancomycin piperacillin tazobactam meropenem
cisplatin carboplatin oxaliplatin paclitaxel docetaxel taxol gemcitabin capecitabin xeloda 5-fu
fluorouracil irinotecan folfox folfiri folfirinox vincristin vinorelbin etoposid cyclophosphamid
ifosfamid doxorubicin epirubicin mitomycin bleomycin methotrexat ixoten trastuzumab herceptin
bevacizumab avastin rituximab mabthera cetuximab pembrolizumab nivolumab ipilimumab
tamoxifen letrozol anastrozol exemestan zoladex goserelin leuprorelin
levothyroxin euthyrox l-thyroxin thiamazol carbimazol
molaxole movicol macrogol lactulose laxoberal
ondansetron mcp metoclopramid domperidon dimenhydrinat
lorazepam tavor diazepam zolpidem mirtazapin citalopram sertralin venlafaxin quetiapin risperidon
haloperidol olanzapin valproat levetiracetam lamotrigin carbamazepin gabapentin pregabalin
subutex buprenorphin methadon naloxon
orgalutran lonquex neulasta filgrastim epo erythropoetin
""".split()

ABBREVIATIONS = """
z.n zn v.a va i.v iv i.m im s.c sc p.o po o.b ob o.p.b z.b zb u.a ua ggf evtl ca
dd ed vd eh ez az bz rr hf af sao2 spo2 bmi kg cm mm ml mg µg ug ie
ap ped vipr tep hüft-tep knie-tep osg usg
sd lnn ln ddx cct mrt ct pet pet-ct mr tee tte
vaia vaia-protokoll cwv ccv ves vt sr es
""".split()

DENY = set(ANATOMY) | set(CLINICAL_WORDS) | set(DRUGS) | set(ABBREVIATIONS)

# Word endings typical of clinical nouns. Deliberately without short endings (-ie, -om, -ose)
# that also end first names and surnames (Marie, Strom, Rose).
MEDICAL_SUFFIXES = (
    "itis", "ektomie", "skopie", "graphie", "plastik", "punktion", "resektion", "fixation", "therapie",
    "abusus", "befund", "syndrom", "karzinom", "carcinom", "metastase", "metastasen", "fraktur", "gelenk",
    "pathie", "ämie", "stenose", "sklerose", "dysplasie", "zyste", "tumor", "ologie", "urgie", "logie",
    "manschette", "bolus", "spiegel", "kreatinin", "insuffizienz", "störung", "erkrankung", "entzündung",
    "schmerzen", "symptome", "symptomatik", "diagnostik", "behandlung", "untersuchung", "kontrolle",
    "wert", "werte", "status", "protokoll", "schema", "zyklus", "stand", "pädie", "iatrie", "ambulanz", "deckung", "wechsel", "bildung",
    "empfinden", "affektion", "lamelle", "falte", "stranding", "punktat", "abstrich", "ausscheidung",
)
DRUG_SUFFIXES = (
    "mycin", "mab", "tinib", "azol", "sulfon", "coumon", "taxel", "platin", "statin", "pril", "sartan",
    "olol", "dipin", "zepam", "zolam", "prazol", "tidin", "cillin", "cyclin", "floxacin", "navir",
    "ciclovir", "ximab", "zumab", "solon", "dronat", "oxacin", "relin", "trexat", "rubicin", "tecan",
)
