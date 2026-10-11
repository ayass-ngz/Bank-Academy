"""Parcours d'apprentissage façon Duolingo.

Chaque package éducatif accessible devient une « section » composée :
  • des unités du programme pédagogique (leçons), qui se débloquent dans l'ordre ;
  • d'une unité « activités » regroupant les contenus de la banque (jeux, quiz,
    actualités, podcasts, ressources), avec sa propre progression.
Des coffres ponctuent chaque unité. La première étape non terminée est l'étape
« en cours », les suivantes sont verrouillées.
"""
from dataclasses import dataclass
from datetime import date, datetime

from flask import url_for
from sqlalchemy import func

from . import games
from .extensions import db
from .models import (RESOURCE_CATEGORIES, ROLE_CLIENT, Completion, GameScore, NewsArticle, PathUnit, Podcast, Quiz,
                     QuizAttempt, Resource, User, band_filter)
from .onboarding import LEVELS, PLACEMENT_SECTIONS
from .packages import (BAND_MINOR, CATALOG_BY_CODE, EDUCATION_ADVANCED, EDUCATION_BASIC, ENTREPRENEURSHIP,
                       is_accessible)

READ_POINTS = 5
CHEST_POINTS = 20
CHEST_EVERY = 4
QUIZ_POINTS_PER_CORRECT = 10
QUIZ_PERFECT_BONUS = 10
PATH_PACKAGES = (EDUCATION_BASIC, EDUCATION_ADVANCED, ENTREPRENEURSHIP)
ZIGZAG = [0, 45, 70, 45, 0, -45, -70, -45]
ACTIVITY_UNITS = {
    EDUCATION_BASIC: ("Jeux & défis", "Rejoue aux jeux pour gagner des points et grimper au classement."),
    EDUCATION_ADVANCED: ("Actus, podcasts & quiz", "Les contenus publiés par ta banque, au fil de l'actualité."),
    ENTREPRENEURSHIP: ("Boîte à outils", "Les ressources pratiques de ta banque pour incuber ton projet."),
}


@dataclass
class Node:
    key: str
    kind: str  # game, quiz, news, podcast, resource, chest
    title: str
    icon: str
    url: str
    done: bool
    subtitle: str = ""
    state: str = "locked"  # done, current, locked
    offset: int = 0


@dataclass
class Unit:
    number: int
    package: object
    color: str
    nodes: list
    title: str = ""
    description: str = ""
    opened_by_test: bool = False  # niveau déjà acquis (test ou progression) : leçons libres
    level: int = None             # niveau requis de l'unité (None : unité non soumise aux niveaux)
    blocked: bool = False         # niveau supérieur à celui de l'élève : verrouillée

    @property
    def steps(self):
        return [n for n in self.nodes if n.kind != "chest"]

    @property
    def done_count(self):
        return sum(1 for n in self.steps if n.done)

    @property
    def total(self):
        return len(self.steps)

    @property
    def percent(self):
        return round(100 * self.done_count / self.total) if self.total else 0

    @property
    def current(self):
        return next((n for n in self.nodes if n.state == "current"), None)


@dataclass
class Section:
    package: object
    color: str
    icon: str
    units: list

    @property
    def done_count(self):
        return sum(u.done_count for u in self.units)

    @property
    def total(self):
        return sum(u.total for u in self.units)

    @property
    def percent(self):
        return round(100 * self.done_count / self.total) if self.total else 0

    @property
    def nodes(self):
        return [n for u in self.units for n in u.nodes]


def quiz_points(score, total):
    return score * QUIZ_POINTS_PER_CORRECT + (QUIZ_PERFECT_BONUS if score == total else 0)


def _today_start():
    return datetime.combine(date.today(), datetime.min.time())


def _completed_keys(user):
    return {f"{c.kind}:{c.ref}" for c in Completion.query.filter_by(user_id=user.id)}


def _lesson_units(user, code, completed):
    """Unités du programme : liste de (titre, description, étapes, préfixe des coffres, niveau requis)."""
    units = PathUnit.query.filter(PathUnit.bank_id == user.bank_id, PathUnit.package_code == code,
                                  PathUnit.active.is_(True), band_filter(PathUnit.band, user.band)) \
        .order_by(PathUnit.position, PathUnit.id)
    result = []
    for path_unit in units:
        lessons = [lsn for lsn in path_unit.lessons if lsn.cards]
        steps = [Node(f"lesson:{lsn.id}", "lesson", lsn.title,
                      "bi-trophy-fill" if i == len(lessons) - 1 and len(lessons) > 1 else "bi-star-fill",
                      url_for("client.lesson_play", lesson_id=lsn.id), f"lesson:{lsn.id}" in completed,
                      f"Leçon {i + 1} / {len(lessons)} · {sum(1 for c in lsn.cards if c.is_question)} exercices")
                 for i, lsn in enumerate(lessons)]
        if steps:
            result.append((path_unit.title, path_unit.description or "", steps, f"u{path_unit.id}",
                           path_unit.level))
    return result


def _activity_steps(user, code, completed):
    if code == EDUCATION_BASIC:
        played = {c for (c,) in db.session.query(GameScore.game_code).filter_by(user_id=user.id).distinct()}
        return [Node(f"game:{c}", "game", g["name"], g["icon"], url_for("client.game_play", code=c), c in played,
                     g["description"]) for c, g in games.GAMES.items()]

    if code == EDUCATION_ADVANCED:
        now = datetime.now()
        done_quizzes = {a.quiz_id for a in QuizAttempt.query.filter_by(user_id=user.id)}
        dated = []
        quizzes = Quiz.query.filter(Quiz.bank_id == user.bank_id, band_filter(Quiz.band, user.band),
                                    Quiz.publish_date <= date.today())
        for q in quizzes:
            if q.questions:
                dated.append((datetime.combine(q.publish_date, datetime.min.time()),
                              Node(f"quiz:{q.id}", "quiz", q.title, "bi-lightning-charge-fill",
                                   url_for("client.quiz_take", quiz_id=q.id), q.id in done_quizzes, "Quiz")))
        for n in NewsArticle.query.filter(NewsArticle.bank_id == user.bank_id, band_filter(NewsArticle.band, user.band),
                                          NewsArticle.published_at <= now):
            dated.append((n.published_at, Node(f"news:{n.id}", "news", n.title, "bi-newspaper",
                                               url_for("client.news_detail", article_id=n.id),
                                               f"news:{n.id}" in completed, "Actualité")))
        for p in Podcast.query.filter(Podcast.bank_id == user.bank_id, band_filter(Podcast.band, user.band),
                                      Podcast.published_at <= now):
            dated.append((p.published_at, Node(f"podcast:{p.id}", "podcast", p.title, "bi-headphones",
                                               url_for("client.podcasts") + f"#podcast-{p.id}",
                                               f"podcast:{p.id}" in completed, "Podcast")))
        dated.sort(key=lambda item: item[0])
        return [node for _, node in dated]

    if code == ENTREPRENEURSHIP:
        order = {c: i for i, (c, _) in enumerate(RESOURCE_CATEGORIES)}
        resources = sorted(Resource.query.filter_by(bank_id=user.bank_id),
                           key=lambda r: (order.get(r.category, 99), r.position, r.id))
        labels = dict(RESOURCE_CATEGORIES)
        return [Node(f"resource:{r.id}", "resource", r.title, "bi-book-fill",
                     url_for("client.resource_detail", resource_id=r.id), f"resource:{r.id}" in completed,
                     labels.get(r.category, "")) for r in resources]
    return []


def _with_chests(prefix, steps, completed):
    nodes, chest_number = [], 0
    for i, step in enumerate(steps, start=1):
        nodes.append(step)
        if i % CHEST_EVERY == 0 or i == len(steps):
            chest_number += 1
            ref = f"{prefix}:{chest_number}"
            nodes.append(Node(f"chest:{ref}", "chest", "Palier de progression", "bi-award-fill",
                              url_for("client.open_chest", ref=ref), f"chest:{ref}" in completed,
                              f"Bonus · +{CHEST_POINTS} points"))
    return nodes


def _assign_states(nodes):
    """États linéaires sur une suite d'étapes (éventuellement répartie sur plusieurs unités)."""
    current_found = False
    for node in nodes:
        if node.done:
            node.state = "done"
        elif not current_found:
            node.state, current_found = "current", True
        else:
            node.state = "locked"


def path_packages(user):
    packages = [p for p in user.bank.packages
                if p.enabled and p.code in PATH_PACKAGES and is_accessible(p.code, user.band)]
    # Les packages recommandés pour la tranche d'âge passent en premier
    return sorted(packages, key=lambda p: (p.recommended_band not in ("all", user.band), p.position))


def _zigzag(nodes):
    for i, node in enumerate(nodes):
        node.offset = ZIGZAG[i % len(ZIGZAG)]


def _assign_open(nodes):
    """Unité ouverte par le test de niveau : leçons jouables dans n'importe quel ordre,
    le palier se valide une fois toutes les leçons de l'unité terminées."""
    for node in nodes:
        if node.done:
            node.state = "done"
        elif node.kind == "chest":
            previous = nodes[:nodes.index(node)]
            node.state = "current" if all(n.done for n in previous if n.kind != "chest") else "locked"
        else:
            node.state = "open"


def build_path(user):
    """Retourne la liste des sections (une par package éducatif accessible)."""
    completed = _completed_keys(user)
    sections = []
    for package in path_packages(user):
        spec = CATALOG_BY_CODE[package.code]
        units = []
        # Programme, par niveau (sections soumises au test de positionnement) :
        #   niveau de l'unité < niveau de l'élève  → acquis, leçons libres ;
        #   niveau de l'unité = niveau de l'élève  → parcours, les leçons se débloquent dans l'ordre ;
        #   niveau de l'unité > niveau de l'élève  → verrouillée.
        gated = package.code in PLACEMENT_SECTIONS
        user_level = user.level or 0
        for title, description, steps, prefix, level in _lesson_units(user, package.code, completed):
            nodes = _with_chests(prefix, steps, completed)
            _zigzag(nodes)
            units.append(Unit(len(units) + 1, package, spec["color"], nodes, title, description,
                              opened_by_test=gated and level < user_level,
                              level=level if gated else None, blocked=gated and level > user_level))
        for unit in units:
            if unit.opened_by_test:
                _assign_open(unit.nodes)
            elif unit.blocked:
                for node in unit.nodes:
                    node.state = "done" if node.done else "locked"
        _assign_states([n for u in units if not u.opened_by_test and not u.blocked for n in u.nodes])
        # Activités de la banque : progression indépendante
        steps = _activity_steps(user, package.code, completed)
        if steps:
            nodes = _with_chests(package.code, steps, completed)
            _zigzag(nodes)
            _assign_states(nodes)
            title, description = ACTIVITY_UNITS[package.code]
            units.append(Unit(len(units) + 1, package, spec["color"], nodes, title, description))
        if units:
            sections.append(Section(package, spec["color"], spec["icon"], units))
    return sections


def promote_if_ready(user):
    """Passage au niveau supérieur quand toutes les unités du niveau en cours sont terminées.
    Retourne le nouveau niveau, ou None."""
    promoted = None
    while (user.level or 0) < len(LEVELS) - 1:
        units = [u for s in build_path(user) if s.package.code in PLACEMENT_SECTIONS for u in s.units
                 if u.level is not None]
        if any(u.done_count < u.total for u in units if u.level == user.level):
            break  # il reste des leçons à terminer au niveau en cours
        if not any(u.level > user.level for u in units):
            break  # rien au-dessus : pas de niveau à débloquer
        user.level += 1
        promoted = user.level
    return promoted


def find_node(sections, key):
    return next((n for section in sections for n in section.nodes if n.key == key), None)


def mark_complete(user, kind, ref, points=READ_POINTS):
    """Enregistre une étape terminée ; retourne True la première fois seulement."""
    ref = str(ref)
    if Completion.query.filter_by(user_id=user.id, kind=kind, ref=ref).first():
        return False
    db.session.add(Completion(user_id=user.id, kind=kind, ref=ref, points=points))
    user.register_activity(points)
    return True


# ------------------------------------------------------------------ classements & quêtes
def band_clients(user):
    """Clients actifs de la banque de `user`, dans la même tranche d'âge."""
    today = date.today()
    try:
        cutoff = today.replace(year=today.year - 18)
    except ValueError:  # 29 février
        cutoff = today.replace(year=today.year - 18, day=28)
    q = User.query.filter_by(bank_id=user.bank_id, role=ROLE_CLIENT, active=True)
    return q.filter(User.birth_date > cutoff) if user.band == BAND_MINOR else q.filter(User.birth_date <= cutoff)


def rank_of(user):
    return band_clients(user).filter(User.points > user.points).count() + 1


def daily_quests(user):
    start = _today_start()
    game_points = db.session.query(func.coalesce(func.sum(GameScore.points_awarded), 0)) \
        .filter(GameScore.user_id == user.id, GameScore.created_at >= start).scalar()
    completions = Completion.query.filter(Completion.user_id == user.id, Completion.created_at >= start).all()
    attempts = QuizAttempt.query.filter(QuizAttempt.user_id == user.id, QuizAttempt.created_at >= start).all()
    plays = GameScore.query.filter(GameScore.user_id == user.id, GameScore.created_at >= start).count()
    games_played = db.session.query(func.count(func.distinct(GameScore.game_code))) \
        .filter(GameScore.user_id == user.id, GameScore.created_at >= start).scalar()

    xp = game_points + sum(c.points for c in completions) + sum(quiz_points(a.score, a.total) for a in attempts)
    steps = len(attempts) + games_played + sum(1 for c in completions if c.kind != "chest")

    quests = [
        {"title": "Gagne 50 points", "icon": "bi-lightning-charge-fill", "color": "#ffc800", "value": xp, "goal": 50},
        {"title": "Termine 2 étapes du parcours", "icon": "bi-signpost-2-fill", "color": "#1cb0f6", "value": steps,
         "goal": 2},
    ]
    basic = user.bank.package(EDUCATION_BASIC)
    if basic and basic.enabled:
        quests.append({"title": "Joue 3 parties", "icon": "bi-controller", "color": "#58cc02", "value": plays,
                       "goal": 3})
    for quest in quests:
        quest["value"] = min(quest["value"], quest["goal"])
        quest["done"] = quest["value"] >= quest["goal"]
    return quests


def client_rail(user):
    """Données de la colonne de droite (statistiques, quêtes, classement)."""
    quiz_of_day = None
    advanced = user.bank.package(EDUCATION_ADVANCED)
    if advanced and advanced.enabled:
        quiz_of_day = Quiz.query.filter(Quiz.bank_id == user.bank_id, band_filter(Quiz.band, user.band),
                                        Quiz.publish_date <= date.today()) \
            .order_by(Quiz.publish_date.desc(), Quiz.id.desc()).first()
    quiz_done = bool(quiz_of_day and QuizAttempt.query.filter_by(user_id=user.id, quiz_id=quiz_of_day.id).first())
    return {
        "rank": rank_of(user),
        "quests": daily_quests(user),
        "leaders": band_clients(user).order_by(User.points.desc(), User.id).limit(5).all(),
        "quiz_of_day": quiz_of_day,
        "quiz_done": quiz_done,
    }
