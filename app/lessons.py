"""Moteur des leçons : transforme les fiches d'une leçon en manches jouables
et corrige les réponses côté serveur (même principe que les jeux)."""
from decimal import Decimal, InvalidOperation

from .extensions import db
from .models import LessonCard

TRUE_FALSE = ["Vrai", "Faux"]


def parse_number(value):
    text = str(value).replace(" ", "").replace(" ", "").replace(",", ".")
    for unit in ("€", "%"):
        text = text.replace(unit, "")
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def format_number(value, unit=None):
    number = Decimal(str(value))
    text = f"{number:.2f}" if number != number.to_integral_value() else f"{int(number)}"
    text = text.replace(".", ",")
    return f"{text} {unit}".strip() if unit else text


def build_rounds(lesson):
    """Retourne (manches publiques, secret) ; le secret contient l'id des fiches-questions."""
    rounds, secret = [], []
    for card in lesson.cards:
        if card.kind == "theory":
            rounds.append({"type": "info", "title": card.title or "Le savais-tu ?", "text": card.body})
            secret.append(None)
        elif card.kind == "choice":
            instruction = "Vrai ou faux ?" if card.choices == TRUE_FALSE else "Choisis la bonne réponse"
            rounds.append({"instruction": instruction, "prompt": card.body, "choices": card.choices})
            secret.append(card.id)
        elif card.kind == "number":
            rounds.append({"instruction": "À toi de calculer", "prompt": card.body, "input": "number",
                           "unit": card.unit_label or ""})
            secret.append(card.id)
    return rounds, secret


def check_card(card_id, answer):
    """Retourne (correct, réponse attendue, explication)."""
    card = db.session.get(LessonCard, card_id)
    if card is None:
        return True, "—", "Exercice retiré par la banque."
    if card.kind == "choice":
        expected = int(card.answer)
        try:
            correct = int(answer) == expected
        except (TypeError, ValueError):
            correct = False
        return correct, card.choices[expected], card.explanation or ""
    expected = Decimal(card.answer)
    given = parse_number(answer)
    correct = given is not None and abs(given - expected) < Decimal("0.005")
    return correct, format_number(expected, card.unit_label), card.explanation or ""
