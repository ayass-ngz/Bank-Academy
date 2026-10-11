"""Programme pédagogique par défaut, installé pour chaque nouvelle banque.

Format compact :
    T(titre, texte)                         fiche de cours
    Q(question, [choix…], bonne, explication) question à choix
    V(affirmation, vraie?, explication)     vrai ou faux
    N(question, réponse, explication, unité) calcul
"""
from ..extensions import db
from ..models import Lesson, LessonCard, PathUnit
from ..packages import EDUCATION_ADVANCED, EDUCATION_BASIC, ENTREPRENEURSHIP


def T(title, text):
    return {"kind": "theory", "title": title, "body": text}


def Q(prompt, choices, correct, explanation=""):
    return {"kind": "choice", "body": prompt, "choices": choices, "answer": str(correct), "explanation": explanation}


def V(statement, is_true, explanation=""):
    return Q(statement, ["Vrai", "Faux"], 0 if is_true else 1, explanation)


def N(prompt, answer, explanation="", unit="€"):
    return {"kind": "number", "body": prompt, "answer": str(answer), "unit_label": unit, "explanation": explanation}


def unit(title, description, lessons, band="all"):
    return {"title": title, "description": description, "band": band, "lessons": lessons}


def lesson(title, *cards):
    return {"title": title, "cards": list(cards)}


def _catalog():
    from .advanced import UNITS as ADVANCED
    from .basic import UNITS as BASIC
    from .entrepreneurship import UNITS as ENTREPRENEURSHIP_UNITS
    return {EDUCATION_BASIC: BASIC, EDUCATION_ADVANCED: ADVANCED, ENTREPRENEURSHIP: ENTREPRENEURSHIP_UNITS}


def seed_curriculum(bank_id):
    """Installe le programme par défaut pour une banque. Retourne le nombre de leçons créées."""
    count = 0
    for package_code, units in _catalog().items():
        for u_pos, spec in enumerate(units):
            path_unit = PathUnit(bank_id=bank_id, package_code=package_code, title=spec["title"],
                                 description=spec["description"], band=spec["band"], position=u_pos,
                                 level=min(3, u_pos // 2))  # 2 unités par niveau
            for l_pos, lesson_spec in enumerate(spec["lessons"]):
                new_lesson = Lesson(bank_id=bank_id, title=lesson_spec["title"], position=l_pos)
                new_lesson.cards = [LessonCard(position=c_pos, **card) for c_pos, card in enumerate(lesson_spec["cards"])]
                path_unit.lessons.append(new_lesson)
                count += 1
            db.session.add(path_unit)
    return count
