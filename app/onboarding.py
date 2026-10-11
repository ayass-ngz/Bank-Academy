"""Arrivée d'un nouvel élève : identifiants provisoires et test de positionnement adaptatif.

Test adaptatif (20 questions)
-----------------------------
Les questions viennent du programme pédagogique de la banque (QCM et calculs des sections
Éducation basique et Éducation avancée). Chaque question a la difficulté du niveau de son unité.

Le niveau de l'élève est estimé par une probabilité sur les 4 niveaux (0 Découverte … 3 Expert),
mise à jour après chaque réponse (règle de Bayes) :
  • un élève de niveau L maîtrise les questions de difficulté d < L : il répond juste,
    sauf étourderie (probabilité SLIP) ;
  • pour une difficulté d ≥ L, il ne peut que deviner (1 chance sur le nombre de choix ;
    quasi nulle pour un calcul).
La question suivante est choisie dans la difficulté qui apporte le plus d'information
(plus forte baisse attendue de l'incertitude). Une bonne réponse fait donc monter la difficulté,
une erreur la fait baisser, et l'estimation converge vers le niveau réel. Le niveau retenu est
le plus probable à l'issue des 20 questions.
"""
import math
import random
import secrets

from flask import url_for

from .extensions import db
from .lessons import check_card
from .mailer import send_mail
from .models import Lesson, LessonCard, PathUnit, band_filter
from .packages import EDUCATION_ADVANCED, EDUCATION_BASIC

LEVELS = [
    {"name": "Découverte", "icon": "bi-flower3",
     "text": "Tu commences par les unités du niveau Découverte. Les niveaux suivants se débloqueront "
             "au fur et à mesure que tu les termines."},
    {"name": "Initié", "icon": "bi-flower1",
     "text": "Les bases sont acquises : les unités Découverte restent ouvertes pour réviser, "
             "et tu attaques le niveau Initié."},
    {"name": "Confirmé", "icon": "bi-flower2",
     "text": "Belles connaissances ! Les niveaux Découverte et Initié sont acquis : place au niveau Confirmé."},
    {"name": "Expert", "icon": "bi-stars",
     "text": "Impressionnant ! Tous les niveaux précédents sont acquis : tu accèdes directement au niveau Expert."},
]
PLACEMENT_SECTIONS = (EDUCATION_BASIC, EDUCATION_ADVANCED)
TEST_LENGTH = 20
SLIP = 0.1                # probabilité de se tromper sur une notion maîtrisée
TEST_TIERS = (0, 1, 2)    # une question de difficulté d indique si le niveau est > d
WORDS = ["Soleil", "Fusee", "Orange", "Comete", "Pixel", "Tigre", "Nuage", "Planete", "Cactus", "Dauphin", "Volcan",
         "Ananas", "Galaxie", "Koala", "Banane", "Pingouin"]


# ------------------------------------------------------------------ modèle probabiliste
def _p_correct(level, tier, guess):
    return 1 - SLIP if tier < level else guess


def _normalize(posterior):
    total = sum(posterior)
    return [p / total for p in posterior] if total else [1 / len(posterior)] * len(posterior)


def update(posterior, tier, correct, guess):
    """Règle de Bayes après une réponse à une question de difficulté `tier`."""
    return _normalize([p * (_p_correct(level, tier, guess) if correct else 1 - _p_correct(level, tier, guess))
                       for level, p in enumerate(posterior)])


def _entropy(posterior):
    return -sum(p * math.log2(p) for p in posterior if p > 0)


def expected_gain(posterior, tier, guess=0.3):
    """Baisse moyenne d'incertitude attendue en posant une question de difficulté `tier`."""
    p_ok = sum(p * _p_correct(level, tier, guess) for level, p in enumerate(posterior))
    after = p_ok * _entropy(update(posterior, tier, True, guess)) \
        + (1 - p_ok) * _entropy(update(posterior, tier, False, guess))
    return _entropy(posterior) - after


def estimate(posterior):
    level = max(range(len(posterior)), key=lambda lv: posterior[lv])
    return level, posterior[level]


# ------------------------------------------------------------------ banque de questions
def guess_rate(card):
    return 1 / len(card.choices) if card.kind == "choice" else 0.05


def question_bank(user):
    """Identifiants des questions du programme, rangés par difficulté (niveau de l'unité)."""
    rows = db.session.query(LessonCard.id, PathUnit.level).join(Lesson, LessonCard.lesson_id == Lesson.id) \
        .join(PathUnit, Lesson.unit_id == PathUnit.id).filter(
            PathUnit.bank_id == user.bank_id, PathUnit.package_code.in_(PLACEMENT_SECTIONS),
            PathUnit.active.is_(True), band_filter(PathUnit.band, user.band),
            LessonCard.kind.in_(["choice", "number"])).all()
    bank = {tier: [] for tier in range(4)}
    for card_id, level in rows:
        bank[min(level, 3)].append(card_id)
    return bank


def _public(card, tier, index):
    question = {"prompt": card.body, "tier": tier, "tier_label": LEVELS[tier]["name"], "index": index,
                "total": TEST_LENGTH}
    if card.kind == "choice":
        question["choices"] = card.choices
    else:
        question["input"] = "number"
        question["unit"] = card.unit_label or ""
    return question


def _pick(state, user):
    """Choisit la prochaine question : difficulté la plus informative, carte jamais posée."""
    bank = question_bank(user)
    asked = set(state["asked"])
    available = {t: [c for c in bank[t] if c not in asked] for t in TEST_TIERS}
    tiers = [t for t in TEST_TIERS if available[t]]
    if not tiers:
        state["exhausted"] = True  # plus aucune question disponible : le test s'arrête
        return None
    # À information égale, on interroge au niveau estimé de l'élève (et non au hasard) :
    # un élève en difficulté reçoit des questions faciles, un élève avancé des questions difficiles.
    target = min(estimate(state["posterior"])[0], max(TEST_TIERS))
    tier = max(tiers, key=lambda t: (round(expected_gain(state["posterior"], t), 3), -abs(t - target)))
    candidates = available[tier]
    random.shuffle(candidates)
    # Mélange de QCM (3 choix et plus) et de calculs ; les vrai/faux (une chance sur deux de deviner)
    # ne sont posés qu'en dernier recours.
    cards = list(LessonCard.query.filter(LessonCard.id.in_(candidates[:12])))
    reliable = [c for c in cards if guess_rate(c) <= 0.34]
    card = random.choice(reliable or cards)
    state["current"], state["tier"] = card.id, tier
    state["asked"].append(card.id)
    return _public(card, tier, len(state["asked"]))


def start(user):
    state = {"posterior": [0.25] * 4, "asked": [], "current": None, "tier": None, "history": []}
    question = _pick(state, user)
    return question, state


def answer(state, user, given):
    """Corrige la question en cours, met à jour l'estimation et prépare la suivante."""
    if state.get("current") is None:
        raise ValueError("Aucune question en cours.")
    card = db.session.get(LessonCard, state["current"])
    correct, expected, explanation = check_card(state["current"], given)
    state["posterior"] = update(state["posterior"], state["tier"], correct, guess_rate(card) if card else 0.3)
    state["history"].append([state["tier"], bool(correct)])
    state["current"] = None
    done = len(state["history"]) >= TEST_LENGTH
    question = None if done else _pick(state, user)
    return {"correct": bool(correct), "expected": expected, "done": done or question is None, "next": question,
            "answered": len(state["history"])}


def finished(state):
    return state.get("current") is None and (len(state["history"]) >= TEST_LENGTH or state.get("exhausted", False))


# ------------------------------------------------------------------ identifiants
def temporary_password():
    return f"{secrets.choice(WORDS)}-{secrets.randbelow(9000) + 1000}"


def send_credentials(child, password, created_by):
    """Envoie à l'enfant ses identifiants de connexion."""
    bank = child.bank
    body = (
        f"Bonjour {child.first_name},\n\n"
        f"{created_by.first_name} a créé ton compte sur l'application d'éducation financière de {bank.name}.\n\n"
        f"Pour te connecter : {url_for('auth.login', _external=True)}\n"
        f"  • Identifiant : {child.email}\n"
        f"  • Mot de passe provisoire : {password}\n\n"
        "À ta première connexion, tu choisiras ton propre mot de passe, puis tu passeras un test de "
        f"positionnement ({TEST_LENGTH} questions qui s'adaptent à tes réponses) pour trouver ton niveau.\n\n"
        "Ne partage jamais ton mot de passe, même avec un ami.\n\n"
        f"À très vite !\nL'équipe {bank.name}"
    )
    return send_mail(child.email, f"Ton compte {bank.name} est prêt !", body)
