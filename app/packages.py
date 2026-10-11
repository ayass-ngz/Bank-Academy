"""Catalogue des packages et règles d'accès par tranche d'âge.

Les règles d'accès (ACCESS_RULES) sont des contraintes métier/réglementaires :
elles ne sont PAS modifiables depuis l'interface banque. La banque peut en
revanche activer/désactiver un package, le renommer et changer la tranche
d'âge pour laquelle il est *recommandé*.
"""

BAND_MINOR = "10-17"
BAND_ADULT = "18-24"
BAND_ALL = "all"

BANDS = {
    BAND_MINOR: "10 – 17 ans",
    BAND_ADULT: "18 – 24 ans",
}
BAND_CHOICES = [(BAND_ALL, "Tous"), (BAND_MINOR, BANDS[BAND_MINOR]), (BAND_ADULT, BANDS[BAND_ADULT])]

MIN_CLIENT_AGE = 10
MAX_CLIENT_AGE = 24

EDUCATION_ADVANCED = "education_advanced"
ENTREPRENEURSHIP = "entrepreneurship"
EDUCATION_BASIC = "education_basic"
PARENTAL = "parental"
CUSTOMER_RELATIONS = "customer_relations"
BANK_OFFERS = "bank_offers"

# Ordre = ordre d'affichage par défaut
PACKAGE_CATALOG = [
    {
        "code": EDUCATION_ADVANCED,
        "name": "Éducation avancée",
        "icon": "bi-mortarboard-fill",
        "color": "#2f6fed",
        "recommended_band": BAND_ADULT,
        "endpoint": "client.advanced_home",
        "description": "Podcasts, actualités financières, quiz quotidiens et questions/réponses.",
    },
    {
        "code": ENTREPRENEURSHIP,
        "name": "Entrepreneuriat",
        "icon": "bi-rocket-takeoff-fill",
        "color": "#e8890c",
        "recommended_band": BAND_ADULT,
        "endpoint": "client.entrepreneurship_home",
        "description": "Ressources pour incuber une idée de startup et communauté d'entrepreneurs.",
    },
    {
        "code": EDUCATION_BASIC,
        "name": "Éducation basique",
        "icon": "bi-controller",
        "color": "#7c5cf2",
        "recommended_band": BAND_MINOR,
        "endpoint": "client.basic_home",
        "description": "Jeux ludiques et éducatifs, classement des scores et des séries (streaks).",
    },
    {
        "code": PARENTAL,
        "name": "Suivi parental",
        "icon": "bi-people-fill",
        "color": "#d6336c",
        "recommended_band": BAND_MINOR,
        "endpoint": "client.parental_home",
        "description": "Lien avec les parents : annonces concernant l'enfant et l'évolution de la plateforme.",
    },
    {
        "code": CUSTOMER_RELATIONS,
        "name": "Information",
        "icon": "bi-info-circle-fill",
        "color": "#e03e3e",
        "recommended_band": BAND_ALL,
        "endpoint": "client.information_home",
        "description": "Les infos de ta banque : évènements, ateliers, interventions et annonces.",
    },
    {
        "code": BANK_OFFERS,
        "name": "Offres de la banque",
        "icon": "bi-bank2",
        "color": "#0b7285",
        "recommended_band": BAND_ADULT,
        "endpoint": "client.offers_home",
        "description": "Les offres de la banque adaptées aux jeunes adultes.",
    },
]

CATALOG_BY_CODE = {p["code"]: p for p in PACKAGE_CATALOG}

# Tranches d'âge autorisées dans l'interface client (absent = toutes)
ACCESS_RULES = {
    # 10-17 ans : les offres bancaires ne sont pas accessibles
    BANK_OFFERS: {BAND_ADULT},
    # 18-24 ans : le suivi parental n'est pas nécessaire, il n'est pas affiché
    PARENTAL: {BAND_MINOR},
}


def band_for_age(age):
    return BAND_MINOR if age is not None and age < 18 else BAND_ADULT


def is_accessible(code, band):
    """Le package `code` est-il accessible à un client de la tranche `band` ?"""
    allowed = ACCESS_RULES.get(code)
    return allowed is None or band in allowed


def matches_band(target_band, user_band):
    """Un contenu ciblé `target_band` est-il visible pour `user_band` ?"""
    return target_band in (None, "", BAND_ALL) or target_band == user_band
