"""Jeux éducatifs du package « Éducation basique ».

Deux familles de jeux :
  • engine == "quiz" : manches question/réponse jouées dans l'écran « leçon »
    (les réponses attendues restent en session, corrigées ici) ;
  • autres moteurs (cartes, mots croisés, simulations…) : logique dans arcade.py.
Dans tous les cas, le score est calculé côté serveur.
"""
import random
from decimal import Decimal, InvalidOperation

from .extensions import db
from .game_data import MESSAGES, NEEDS_WANTS, PRICES
from .models import Lesson, LessonCard, PathUnit, TrueFalseQuestion, band_filter
from .packages import EDUCATION_ADVANCED, EDUCATION_BASIC

POINTS_PER_CORRECT = 10
CHRONO_SECONDS = 60
PRICE_TOLERANCE = Decimal("0.15")  # ±15 % pour « Le juste prix »

CATEGORIES = [
    ("quiz", "Questions-réponses", "bi-chat-square-dots"),
    ("cartes", "Jeux de cartes", "bi-suit-spade-fill"),
    ("lettres", "Jeux de lettres", "bi-grid-3x3-gap-fill"),
    ("calcul", "Calcul & estimation", "bi-calculator"),
    ("simulation", "Simulations", "bi-graph-up-arrow"),
]

GAMES = {
    "vrai_faux": {
        "name": "Vrai ou Faux", "icon": "bi-patch-question", "color": "#2f6fed", "category": "quiz", "engine": "quiz",
        "description": "Démêle le vrai du faux sur l'argent, la banque et le budget.",
        "instruction": "Vrai ou faux ?", "rounds": 10,
    },
    "chrono": {
        "name": "Défi chrono", "icon": "bi-stopwatch", "color": "#e8590c", "category": "quiz", "engine": "quiz",
        "description": f"Un maximum de bonnes réponses en {CHRONO_SECONDS} secondes !",
        "instruction": "Vite, la bonne réponse !", "rounds": 20, "time_limit": CHRONO_SECONDS,
    },
    "arnaque": {
        "name": "Arnaque ou pas ?", "icon": "bi-shield-exclamation", "color": "#d6336c", "category": "quiz", "engine": "quiz",
        "description": "SMS, mails, messages : repère les tentatives d'arnaque.",
        "instruction": "Arnaque ou message fiable ?", "rounds": 8,
    },
    "besoin_envie": {
        "name": "Besoin ou envie ?", "icon": "bi-cart3", "color": "#7c5cf2", "category": "quiz", "engine": "quiz",
        "description": "Apprends à distinguer les dépenses essentielles des plaisirs.",
        "instruction": "Besoin ou envie ?", "rounds": 10,
    },
    "memory": {
        "name": "Memory des notions", "icon": "bi-grid-3x2-gap-fill", "color": "#0b7285", "category": "cartes", "engine": "memory",
        "description": "Retourne les cartes et associe chaque notion à sa définition.",
        "instruction": "Trouve les paires notion ↔ définition",
    },
    "plus_moins": {
        "name": "Plus ou moins cher ?", "icon": "bi-suit-diamond-fill", "color": "#c2255c", "category": "cartes", "engine": "higherlower",
        "description": "La carte suivante coûte-t-elle plus ou moins cher ? Teste ton sens des prix.",
        "instruction": "La prochaine carte est-elle plus ou moins chère ?",
    },
    "mots_croises": {
        "name": "Mots croisés", "icon": "bi-grid-3x3", "color": "#5f3dc4", "category": "lettres", "engine": "crossword",
        "description": "Complète la grille avec le vocabulaire de l'argent.",
        "instruction": "Remplis la grille grâce aux définitions",
    },
    "mots_meles": {
        "name": "Mots mêlés", "icon": "bi-search", "color": "#1971c2", "category": "lettres", "engine": "wordsearch",
        "description": "Retrouve les mots cachés dans la grille, dans tous les sens.",
        "instruction": "Clique sur la première puis la dernière lettre d'un mot",
    },
    "mot_mystere": {
        "name": "Le mot mystère", "icon": "bi-incognito", "color": "#2b8a3e", "category": "lettres", "engine": "hangman",
        "description": "Devine le mot lettre par lettre avant d'épuiser tes pièces.",
        "instruction": "Devine le mot mystère",
    },
    "rendu_monnaie": {
        "name": "Le rendu de monnaie", "icon": "bi-coin", "color": "#e0a100", "category": "calcul", "engine": "quiz",
        "description": "Calcule la monnaie à rendre comme un vrai commerçant.",
        "instruction": "Combien faut-il rendre ?", "rounds": 8,
    },
    "juste_prix": {
        "name": "Le juste prix", "icon": "bi-tag", "color": "#f08c00", "category": "calcul", "engine": "quiz",
        "description": "Estime le prix d'objets du quotidien (à 15 % près).",
        "instruction": "À combien estimes-tu ce prix ?", "rounds": 8,
    },
    "vie_en_euros": {
        "name": "La vie en euros", "icon": "bi-signpost-split", "color": "#0ca678", "category": "simulation", "engine": "life",
        "description": "Gère ton argent mois après mois et trouve l'équilibre entre épargne et bien-être.",
        "instruction": "Fais tes choix pour bien gérer ton budget",
    },
    "bourse": {
        "name": "Bourse junior", "icon": "bi-graph-up-arrow", "color": "#364fc7", "category": "simulation", "engine": "stock",
        "description": "Répartis 1 000 € fictifs entre plusieurs placements et découvre la diversification.",
        "instruction": "Répartis ton argent avant chaque trimestre",
    },
}

NOTES_CENTS = [500, 1000, 2000, 5000, 10000]


def is_quiz(code):
    return GAMES[code]["engine"] == "quiz"


def euros(cents):
    return f"{cents / 100:.2f} €".replace(".", ",")


def euros_value(value):
    """12.5 -> '12,50 €' ; 480 -> '480 €'."""
    value = Decimal(str(value))
    text = f"{value:,.0f}" if value == value.to_integral_value() else f"{value:,.2f}"
    return text.replace(",", " ").replace(".", ",") + " €"


def parse_euros(value):
    """'3,50' / '3.5' / '3,50 €' -> 350 (centimes) ; None si invalide."""
    text = str(value).replace("€", "").replace(" ", "").replace(" ", "").replace(",", ".")
    try:
        return int((Decimal(text) * 100).to_integral_value())
    except (InvalidOperation, ValueError):
        return None


def _chrono_cards(user):
    """Questions à choix tirées du programme pédagogique de la banque."""
    codes = [EDUCATION_BASIC] + ([EDUCATION_ADVANCED] if not user.is_minor else [])
    return LessonCard.query.join(Lesson).join(PathUnit).filter(
        PathUnit.bank_id == user.bank_id, PathUnit.package_code.in_(codes), PathUnit.active.is_(True),
        band_filter(PathUnit.band, user.band), LessonCard.kind == "choice").all()


def new_game(code, user):
    """Jeux « quiz » : retourne (manches publiques, état secret à garder en session)."""
    n = GAMES[code]["rounds"]
    if code == "vrai_faux":
        questions = TrueFalseQuestion.query.filter(
            TrueFalseQuestion.bank_id == user.bank_id, band_filter(TrueFalseQuestion.band, user.band)
        ).all()
        questions = random.sample(questions, min(n, len(questions)))
        return ([{"prompt": q.statement, "choices": ["Vrai", "Faux"]} for q in questions],
                [q.id for q in questions])
    if code == "rendu_monnaie":
        public, secret = [], []
        for _ in range(n):
            price = random.randint(10, 999) * 5  # multiple de 5 centimes, de 0,50 € à 49,95 €
            paid = next(note for note in NOTES_CENTS if note > price)
            public.append({"prompt": f"Un article coûte {euros(price)}. Tu paies avec un billet de {euros(paid)}. "
                                     "Combien doit-on te rendre ?", "input": "number"})
            secret.append([price, paid])
        return public, secret
    if code == "besoin_envie":
        items = random.sample(range(len(NEEDS_WANTS)), min(n, len(NEEDS_WANTS)))
        return ([{"prompt": NEEDS_WANTS[i][0], "choices": ["Besoin", "Envie"]} for i in items], items)
    if code == "arnaque":
        items = random.sample(range(len(MESSAGES)), min(n, len(MESSAGES)))
        return ([{"message": {"sender": MESSAGES[i][0], "text": MESSAGES[i][1]}, "prompt": "",
                  "choices": ["🚩 Arnaque", "✅ Fiable"]} for i in items], items)
    if code == "juste_prix":
        items = random.sample(range(len(PRICES)), min(n, len(PRICES)))
        return ([{"prompt": PRICES[i][0], "input": "number"} for i in items], items)
    if code == "chrono":
        pool = _chrono_cards(user)
        cards = random.sample(pool, k=min(n, len(pool)))
        return ([{"prompt": c.body, "choices": c.choices} for c in cards], [c.id for c in cards])
    raise KeyError(code)


def check_answer(code, secret_item, answer):
    """Jeux « quiz » : retourne (correct, réponse attendue, explication)."""
    if code == "rendu_monnaie":
        price, paid = secret_item
        change = paid - price
        return (parse_euros(answer) == change, euros(change),
                f"{euros(paid)} − {euros(price)} = {euros(change)}")

    if code == "juste_prix":
        label, price, explanation = PRICES[secret_item]
        given = parse_euros(answer)
        target = Decimal(str(price))
        correct = given is not None and abs(Decimal(given) / 100 - target) <= target * PRICE_TOLERANCE
        return correct, euros_value(price), explanation

    if code == "chrono":
        from .lessons import check_card
        return check_card(secret_item, answer)

    try:
        choice = int(answer)
    except (TypeError, ValueError):
        choice = -1

    if code == "vrai_faux":
        question = db.session.get(TrueFalseQuestion, secret_item)
        if question is None:  # supprimée entre-temps : on ne pénalise pas
            return True, "—", "Question retirée par la banque."
        expected = 0 if question.is_true else 1
        return choice == expected, "Vrai" if question.is_true else "Faux", question.explanation or ""

    if code == "besoin_envie":
        label, is_need, explanation = NEEDS_WANTS[secret_item]
        expected = 0 if is_need else 1
        return choice == expected, "Besoin" if is_need else "Envie", explanation

    if code == "arnaque":
        sender, text, is_scam, explanation = MESSAGES[secret_item]
        expected = 0 if is_scam else 1
        return choice == expected, "Arnaque" if is_scam else "Fiable", explanation

    raise KeyError(code)
