from datetime import date, datetime, timedelta

from flask_login import UserMixin
from sqlalchemy import UniqueConstraint, or_
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .packages import BAND_ALL, band_for_age

ROLE_ADMIN = "admin"
ROLE_CLIENT = "client"
ROLE_PARENT = "parent"
ROLES = {ROLE_ADMIN: "Banque (admin)", ROLE_CLIENT: "Client", ROLE_PARENT: "Parent"}


def now():
    return datetime.now().replace(microsecond=0)


def band_filter(column, band):
    """Filtre SQL : contenu destiné à tous ou à la tranche `band`."""
    return or_(column == BAND_ALL, column == band)


class Bank(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(60), unique=True, nullable=False)
    primary_color = db.Column(db.String(7), nullable=False, default="#2b59c3")
    welcome_message = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=now)

    packages = db.relationship("Package", back_populates="bank", order_by="Package.position",
                               cascade="all, delete-orphan")

    def package(self, code):
        return next((p for p in self.packages if p.code == code), None)


parent_child = db.Table(
    "parent_child",
    db.Column("parent_id", db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
    db.Column("child_id", db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bank_id = db.Column(db.Integer, db.ForeignKey("bank.id"), nullable=False, index=True)
    role = db.Column(db.String(10), nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    birth_date = db.Column(db.Date)  # obligatoire pour les clients
    points = db.Column(db.Integer, nullable=False, default=0)
    current_streak = db.Column(db.Integer, nullable=False, default=0)
    best_streak = db.Column(db.Integer, nullable=False, default=0)
    last_active_date = db.Column(db.Date)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=now)
    # Accueil du nouvel élève : mot de passe provisoire à changer, puis test de niveau
    must_change_password = db.Column(db.Boolean, nullable=False, default=False)
    onboarded_at = db.Column(db.DateTime)
    level = db.Column(db.Integer, nullable=False, default=0)  # 0 Découverte … 3 Expert

    bank = db.relationship("Bank")
    children = db.relationship(
        "User", secondary=parent_child,
        primaryjoin=id == parent_child.c.parent_id,
        secondaryjoin=id == parent_child.c.child_id,
        backref="parents",
    )

    def __init__(self, **kwargs):
        # Les default= des colonnes ne s'appliquent qu'à l'INSERT : on initialise les compteurs tout de suite
        for counter in ("points", "current_streak", "best_streak"):
            kwargs.setdefault(counter, 0)
        kwargs.setdefault("active", True)
        kwargs.setdefault("level", 0)
        kwargs.setdefault("must_change_password", False)
        super().__init__(**kwargs)

    # --- Flask-Login
    @property
    def is_active(self):
        return self.active

    # --- Identité
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def public_name(self):
        """Nom affiché aux autres utilisateurs (protection des mineurs)."""
        return f"{self.first_name} {self.last_name[:1]}."

    # --- Âge
    @property
    def age(self):
        if not self.birth_date:
            return None
        today = date.today()
        b = self.birth_date
        return today.year - b.year - ((today.month, today.day) < (b.month, b.day))

    @property
    def band(self):
        return band_for_age(self.age)

    @property
    def is_minor(self):
        return self.age is not None and self.age < 18

    # --- Gamification
    @property
    def effective_streak(self):
        """La série est perdue si l'utilisateur n'est pas venu hier ni aujourd'hui."""
        if self.last_active_date and self.last_active_date >= date.today() - timedelta(days=1):
            return self.current_streak
        return 0

    def register_activity(self, points=0):
        today = date.today()
        if self.last_active_date != today:
            if self.last_active_date == today - timedelta(days=1):
                self.current_streak += 1
            else:
                self.current_streak = 1
            self.last_active_date = today
            self.best_streak = max(self.best_streak, self.current_streak)
            self.activity_days.append(ActivityDay(day=today))  # historique pour la « semaine » de l'accueil
        self.points += points

    def active_days_since(self, start):
        return {a.day for a in self.activity_days if a.day >= start}


class ActivityDay(db.Model):
    """Un jour où l'utilisateur a été actif (connexion, leçon, jeu…)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    day = db.Column(db.Date, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "day"),)


User.activity_days = db.relationship(ActivityDay, order_by=ActivityDay.day, cascade="all, delete-orphan")


class Package(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bank_id = db.Column(db.Integer, db.ForeignKey("bank.id"), nullable=False)
    code = db.Column(db.String(40), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(255))
    icon = db.Column(db.String(40))
    recommended_band = db.Column(db.String(10), nullable=False, default=BAND_ALL)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    position = db.Column(db.Integer, nullable=False, default=0)

    bank = db.relationship("Bank", back_populates="packages")
    __table_args__ = (UniqueConstraint("bank_id", "code"),)


# ---------------------------------------------------------------- Éducation avancée
class Podcast(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bank_id = db.Column(db.Integer, db.ForeignKey("bank.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    audio_url = db.Column(db.String(500))
    external_url = db.Column(db.String(500))
    duration_min = db.Column(db.Integer)
    band = db.Column(db.String(10), nullable=False, default=BAND_ALL)
    published_at = db.Column(db.DateTime, nullable=False, default=now)


class NewsArticle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bank_id = db.Column(db.Integer, db.ForeignKey("bank.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.String(500))
    content = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    source_url = db.Column(db.String(500))
    band = db.Column(db.String(10), nullable=False, default=BAND_ALL)
    published_at = db.Column(db.DateTime, nullable=False, default=now)


class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bank_id = db.Column(db.Integer, db.ForeignKey("bank.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500))
    publish_date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    band = db.Column(db.String(10), nullable=False, default=BAND_ALL)

    questions = db.relationship("QuizQuestion", back_populates="quiz", order_by="QuizQuestion.position",
                                cascade="all, delete-orphan")
    attempts = db.relationship("QuizAttempt", back_populates="quiz", cascade="all, delete-orphan")


class QuizQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quiz.id"), nullable=False)
    text = db.Column(db.String(500), nullable=False)
    explanation = db.Column(db.String(500))
    position = db.Column(db.Integer, nullable=False, default=0)

    quiz = db.relationship("Quiz", back_populates="questions")
    choices = db.relationship("QuizChoice", back_populates="question", order_by="QuizChoice.id",
                              cascade="all, delete-orphan")


class QuizChoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("quiz_question.id"), nullable=False)
    text = db.Column(db.String(300), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False, default=False)

    question = db.relationship("QuizQuestion", back_populates="choices")


class QuizAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quiz.id"), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=now)

    user = db.relationship("User")
    quiz = db.relationship("Quiz", back_populates="attempts")
    __table_args__ = (UniqueConstraint("user_id", "quiz_id"),)


class QAQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bank_id = db.Column(db.Integer, db.ForeignKey("bank.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=now)

    author = db.relationship("User")
    answers = db.relationship("QAAnswer", back_populates="question", order_by="QAAnswer.created_at",
                              cascade="all, delete-orphan")

    @property
    def has_official_answer(self):
        return any(a.is_official for a in self.answers)


class QAAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("qa_question.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_official = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=now)

    author = db.relationship("User")
    question = db.relationship("QAQuestion", back_populates="answers")


# ---------------------------------------------------------------- Entrepreneuriat
RESOURCE_CATEGORIES = [
    ("idee", "1. Trouver et valider son idée"),
    ("marche", "2. Étudier son marché"),
    ("business_plan", "3. Business plan & modèle économique"),
    ("juridique", "4. Statut juridique"),
    ("financement", "5. Financement"),
    ("lancement", "6. Lancement & marketing"),
]
POST_CATEGORIES = [
    ("idee", "Je partage une idée"),
    ("associe", "Je cherche un associé"),
    ("conseil", "Je cherche un conseil"),
    ("financement", "Financement"),
    ("autre", "Autre"),
]


class Resource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bank_id = db.Column(db.Integer, db.ForeignKey("bank.id"), nullable=False, index=True)
    category = db.Column(db.String(30), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.String(500))
    content = db.Column(db.Text)
    external_url = db.Column(db.String(500))
    position = db.Column(db.Integer, nullable=False, default=0)


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bank_id = db.Column(db.Integer, db.ForeignKey("bank.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    category = db.Column(db.String(30), nullable=False, default="autre")
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=now)

    author = db.relationship("User")
    comments = db.relationship("PostComment", back_populates="post", order_by="PostComment.created_at",
                               cascade="all, delete-orphan")


class PostComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=now)

    author = db.relationship("User")
    post = db.relationship("Post", back_populates="comments")


# ---------------------------------------------------------------- Éducation basique
class TrueFalseQuestion(db.Model):
    """Contenu du jeu « Vrai ou Faux », administrable par la banque."""
    id = db.Column(db.Integer, primary_key=True)
    bank_id = db.Column(db.Integer, db.ForeignKey("bank.id"), nullable=False, index=True)
    statement = db.Column(db.String(300), nullable=False)
    is_true = db.Column(db.Boolean, nullable=False)
    explanation = db.Column(db.String(500))
    band = db.Column(db.String(10), nullable=False, default=BAND_ALL)


class GameScore(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    game_code = db.Column(db.String(30), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    points_awarded = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=now, index=True)

    user = db.relationship("User")


# ---------------------------------------------------------------- Parcours
class PathUnit(db.Model):
    """Unité du programme pédagogique d'un package (section)."""
    id = db.Column(db.Integer, primary_key=True)
    bank_id = db.Column(db.Integer, db.ForeignKey("bank.id"), nullable=False, index=True)
    package_code = db.Column(db.String(40), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500))
    band = db.Column(db.String(10), nullable=False, default=BAND_ALL)
    position = db.Column(db.Integer, nullable=False, default=0)
    active = db.Column(db.Boolean, nullable=False, default=True)
    # Niveau requis (0 Découverte … 3 Expert) : au-dessus du niveau de l'élève, l'unité est verrouillée
    level = db.Column(db.Integer, nullable=False, default=0)

    lessons = db.relationship("Lesson", back_populates="unit", order_by="Lesson.position, Lesson.id",
                              cascade="all, delete-orphan")


class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bank_id = db.Column(db.Integer, db.ForeignKey("bank.id"), nullable=False, index=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("path_unit.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)

    unit = db.relationship("PathUnit", back_populates="lessons")
    cards = db.relationship("LessonCard", back_populates="lesson", order_by="LessonCard.position, LessonCard.id",
                            cascade="all, delete-orphan")


CARD_KINDS = [("theory", "Fiche de cours"), ("choice", "Question à choix"), ("number", "Calcul (réponse chiffrée)")]


class LessonCard(db.Model):
    """Fiche de cours (theory) ou exercice (choice : QCM / vrai-faux, number : calcul)."""
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lesson.id"), nullable=False, index=True)
    kind = db.Column(db.String(10), nullable=False)
    title = db.Column(db.String(200))
    body = db.Column(db.Text, nullable=False)
    choices = db.Column(db.JSON)
    answer = db.Column(db.String(30))  # index de la bonne réponse, ou valeur numérique
    unit_label = db.Column(db.String(12))  # unité de la réponse chiffrée (€, %, ans…)
    explanation = db.Column(db.String(500))
    position = db.Column(db.Integer, nullable=False, default=0)

    lesson = db.relationship("Lesson", back_populates="cards")

    @property
    def is_question(self):
        return self.kind != "theory"


class Completion(db.Model):
    """Étape du parcours terminée : contenu lu/écouté (news, podcast, resource) ou coffre ouvert (chest)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    kind = db.Column(db.String(20), nullable=False)
    ref = db.Column(db.String(60), nullable=False)
    points = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=now, index=True)

    __table_args__ = (UniqueConstraint("user_id", "kind", "ref"),)


# ---------------------------------------------------------------- Annonces (suivi parental & relation client)
ANNOUNCEMENT_KINDS = [("annonce", "Annonce"), ("evenement", "Évènement"), ("intervention", "Intervention"),
                      ("plateforme", "Évolution de la plateforme"), ("enfant", "Au sujet de l'enfant")]
AUDIENCES = [("all", "Tout le monde"), ("clients", "Clients (tous âges)"), ("10-17", "Clients 10 – 17 ans"),
             ("18-24", "Clients 18 – 24 ans"), ("parents", "Parents")]


class EventRegistration(db.Model):
    """Inscription d'un utilisateur à un évènement du package Information."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    announcement_id = db.Column(db.Integer, db.ForeignKey("announcement.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=now)

    user = db.relationship("User")
    __table_args__ = (UniqueConstraint("user_id", "announcement_id"),)


class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bank_id = db.Column(db.Integer, db.ForeignKey("bank.id"), nullable=False, index=True)
    package_code = db.Column(db.String(40), nullable=False, index=True)
    kind = db.Column(db.String(20), nullable=False, default="annonce")
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    audience = db.Column(db.String(10), nullable=False, default="all")
    child_id = db.Column(db.Integer, db.ForeignKey("user.id"))  # annonce ciblant un enfant précis (parents)
    event_date = db.Column(db.DateTime)
    location = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=now)

    child = db.relationship("User", foreign_keys=[child_id])
    registrations = db.relationship("EventRegistration", cascade="all, delete-orphan")

    @property
    def is_event(self):
        return self.event_date is not None

    @property
    def is_new(self):
        return self.created_at is not None and self.created_at >= now() - timedelta(days=7)

    @property
    def kind_label(self):
        return dict(ANNOUNCEMENT_KINDS).get(self.kind, self.kind)


# ---------------------------------------------------------------- Offres de la banque
OFFER_CATEGORIES = [("compte", "Compte"), ("carte", "Carte"), ("epargne", "Épargne"), ("credit", "Crédit étudiant"),
                    ("assurance", "Assurance"), ("autre", "Autre")]


class Offer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bank_id = db.Column(db.Integer, db.ForeignKey("bank.id"), nullable=False, index=True)
    category = db.Column(db.String(20), nullable=False, default="autre")
    title = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.String(500))
    description = db.Column(db.Text)
    conditions = db.Column(db.String(500))
    cta_url = db.Column(db.String(500))
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=now)

    interests = db.relationship("OfferInterest", back_populates="offer", cascade="all, delete-orphan")


class OfferInterest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    offer_id = db.Column(db.Integer, db.ForeignKey("offer.id"), nullable=False)
    message = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=now)

    user = db.relationship("User")
    offer = db.relationship("Offer", back_populates="interests")
    __table_args__ = (UniqueConstraint("user_id", "offer_id"),)
