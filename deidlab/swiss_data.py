"""
Static Swiss reference data used by the synthetic generator.

Localities are real PLZ/locality pairs. Street names are built from
patterns plus Faker surnames. Everything else (people, numbers) is fake.
"""

LOCALITIES = {
    "de": [
        ("8001", "Zürich"), ("8610", "Uster"), ("8400", "Winterthur"), ("5400", "Baden"),
        ("5000", "Aarau"), ("3011", "Bern"), ("3600", "Thun"), ("4051", "Basel"),
        ("4410", "Liestal"), ("6003", "Luzern"), ("6300", "Zug"), ("9000", "St. Gallen"),
        ("7000", "Chur"), ("8953", "Dietikon"), ("8302", "Kloten"), ("4500", "Solothurn"),
        ("8200", "Schaffhausen"), ("8500", "Frauenfeld"), ("6430", "Schwyz"), ("3920", "Zermatt"),
    ],
    "fr": [
        ("1003", "Lausanne"), ("1201", "Genève"), ("1950", "Sion"), ("2000", "Neuchâtel"),
        ("1700", "Fribourg"), ("1820", "Montreux"), ("1400", "Yverdon-les-Bains"), ("1260", "Nyon"),
        ("2300", "La Chaux-de-Fonds"), ("1110", "Morges"), ("1870", "Monthey"), ("2800", "Delémont"),
        ("1920", "Martigny"), ("1630", "Bulle"), ("1800", "Vevey"), ("1227", "Carouge"),
    ],
    "it": [
        ("6900", "Lugano"), ("6500", "Bellinzona"), ("6600", "Locarno"), ("6850", "Mendrisio"),
        ("6830", "Chiasso"), ("6710", "Biasca"), ("6780", "Airolo"), ("6612", "Ascona"),
        ("6982", "Agno"), ("6616", "Losone"), ("6648", "Minusio"), ("6900", "Massagno"),
        ("6533", "Lumino"), ("6942", "Savosa"), ("7742", "Poschiavo"), ("6760", "Faido"),
    ],
}

STREET_PATTERNS = {
    "de": ["{name}strasse", "{name}weg", "{name}gasse", "Bahnhofstrasse", "Dorfstrasse",
           "Seestrasse", "Kirchweg", "Hauptstrasse", "Lindenweg", "Rosenstrasse", "Im {name}rain"],
    "fr": ["Rue du Lac", "Avenue de la Gare", "Chemin des Vignes", "Rue de Lausanne",
           "Route de Berne", "Rue du Marché", "Avenue des Alpes", "Chemin du Bois",
           "Rue {name}", "Avenue {name}", "Chemin de la Forêt"],
    "it": ["Via Cantonale", "Via San Gottardo", "Via Lugano", "Viale Stazione", "Via Nassa",
           "Via Motta", "Via Ciseri", "Via Monte Ceneri", "Via {name}", "Vicolo {name}",
           "Piazza Grande"],
}

HOSPITAL_PATTERNS = {
    "de": ["Kantonsspital {city}", "Spital {city}", "Regionalspital {city}", "Klinik {name}",
           "Stadtspital {city}"],
    "fr": ["Hôpital de {city}", "Centre hospitalier de {city}", "Clinique {name}",
           "Hôpital régional de {city}"],
    "it": ["Ospedale Regionale di {city}", "Ospedale Civico di {city}", "Clinica {name}",
           "Ospedale San {name}"],
}

EMAIL_DOMAINS = ["bluewin.ch", "gmx.ch", "sunrise.ch", "hotmail.com", "gmail.com", "hispeed.ch",
                 "swissonline.ch", "proton.me"]

# Insurers are organisations, not patient data. Used as distractors.
INSURERS = ["CSS", "Helsana", "Swica", "Sanitas", "Visana", "Groupe Mutuel", "Concordia", "Assura"]

DIAGNOSES = {
    "de": ["Morbus Crohn", "Morbus Parkinson", "Hashimoto-Thyreoiditis", "Morbus Bechterew",
           "Diabetes mellitus Typ 2", "arterielle Hypertonie", "Vorhofflimmern",
           "Pneumonie rechts basal", "Cholezystolithiasis", "Alzheimer-Demenz",
           "Guillain-Barré-Syndrom", "Morbus Basedow", "Cushing-Syndrom"],
    "fr": ["maladie de Crohn", "maladie de Parkinson", "thyroïdite de Hashimoto",
           "spondylarthrite ankylosante", "diabète de type 2", "hypertension artérielle",
           "fibrillation auriculaire", "pneumonie basale droite", "maladie d'Alzheimer",
           "syndrome de Guillain-Barré", "maladie de Basedow", "syndrome de Cushing"],
    "it": ["morbo di Crohn", "morbo di Parkinson", "tiroidite di Hashimoto",
           "spondilite anchilosante", "diabete mellito di tipo 2", "ipertensione arteriosa",
           "fibrillazione atriale", "polmonite basale destra", "malattia di Alzheimer",
           "sindrome di Guillain-Barré", "morbo di Basedow", "sindrome di Cushing"],
}

ICD = ["K50.9", "G20", "E06.3", "M45", "E11.9", "I10", "I48.0", "J18.9", "K80.2", "G30.9", "G61.0"]

DRUGS = ["Metformin 1000 mg 1-0-1", "Pantoprazol 40 mg 1-0-0", "Eliquis 5 mg 1-0-1",
         "Ramipril 5 mg 1-0-0", "Dafalgan 1 g max. 4x/24h", "Torasemid 10 mg 1-0-0",
         "Atorvastatin 20 mg 0-0-1", "Levothyroxin 75 mcg 1-0-0", "Madopar 125 mg 1-1-1",
         "Prednison 20 mg 1-0-0"]

LAB = {
    # parameter name per language, value, unit, reference range
    "rows": [
        ({"de": "Hämoglobin", "fr": "Hémoglobine", "it": "Emoglobina"}, (105, 165), "g/L", "120-160"),
        ({"de": "Leukozyten", "fr": "Leucocytes", "it": "Leucociti"}, (3.2, 14.5), "G/L", "3.5-10.0"),
        ({"de": "Thrombozyten", "fr": "Thrombocytes", "it": "Piastrine"}, (110, 420), "G/L", "150-400"),
        ({"de": "Kreatinin", "fr": "Créatinine", "it": "Creatinina"}, (55, 180), "umol/L", "59-104"),
        ({"de": "CRP", "fr": "CRP", "it": "PCR"}, (1, 160), "mg/L", "< 5"),
        ({"de": "HbA1c", "fr": "HbA1c", "it": "HbA1c"}, (5.0, 9.8), "%", "< 5.7"),
        ({"de": "TSH", "fr": "TSH", "it": "TSH"}, (0.2, 8.5), "mU/L", "0.27-4.2"),
        ({"de": "Natrium", "fr": "Sodium", "it": "Sodio"}, (128, 146), "mmol/L", "135-145"),
        ({"de": "Kalium", "fr": "Potassium", "it": "Potassio"}, (3.1, 5.6), "mmol/L", "3.5-5.1"),
    ]
}

MONTHS = {
    "de": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
           "September", "Oktober", "November", "Dezember"],
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
           "septembre", "octobre", "novembre", "décembre"],
    "it": ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
           "settembre", "ottobre", "novembre", "dicembre"],
}
