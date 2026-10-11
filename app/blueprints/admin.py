from datetime import date, datetime, timedelta
from types import SimpleNamespace

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func

from .. import games
from ..crud import ENTITIES
from ..extensions import db
from ..models import (CARD_KINDS, ROLE_ADMIN, ROLE_CLIENT, ROLE_PARENT, ROLES, Announcement, EventRegistration, GameScore,
                      Lesson, LessonCard, Offer, OfferInterest, PathUnit, Post, PostComment, QAAnswer, QAQuestion, Quiz,
                      QuizAttempt, QuizChoice, QuizQuestion, User)
from ..packages import BAND_CHOICES, BANDS, CATALOG_BY_CODE, MAX_CLIENT_AGE, MIN_CLIENT_AGE
from ..lessons import parse_number
from ..onboarding import LEVELS, send_credentials
from ..path import PATH_PACKAGES, build_path
from ..utils import EMAIL, HEX_COLOR, role_required

bp = Blueprint("admin", __name__)


@bp.before_request
@role_required(ROLE_ADMIN)
def guard():
    """Toute l'interface banque est réservée aux administrateurs."""


def bank_users():
    return User.query.filter_by(bank_id=current_user.bank_id)


# ------------------------------------------------------------------ tableau de bord
@bp.route("/")
def dashboard():
    clients = bank_users().filter_by(role=ROLE_CLIENT).all()
    week_ago = datetime.now() - timedelta(days=7)
    bank_user_ids = db.session.query(User.id).filter(User.bank_id == current_user.bank_id)
    stats = {
        "minors": sum(1 for c in clients if c.is_minor),
        "adults": sum(1 for c in clients if not c.is_minor),
        "parents": bank_users().filter_by(role=ROLE_PARENT).count(),
        "active_today": sum(1 for c in clients if c.last_active_date == date.today()),
        "quiz_week": QuizAttempt.query.filter(QuizAttempt.user_id.in_(bank_user_ids),
                                              QuizAttempt.created_at >= week_ago).count(),
        "games_week": GameScore.query.filter(GameScore.user_id.in_(bank_user_ids),
                                             GameScore.created_at >= week_ago).count(),
        "open_questions": sum(1 for q in QAQuestion.query.filter_by(bank_id=current_user.bank_id)
                              if not q.has_official_answer),
        "interests": OfferInterest.query.join(Offer).filter(Offer.bank_id == current_user.bank_id).count(),
    }
    top = sorted(clients, key=lambda c: c.points, reverse=True)[:5]
    return render_template("admin/dashboard.html", stats=stats, top=top, entities=ENTITIES)


# ------------------------------------------------------------------ packages
@bp.route("/packages", methods=["GET", "POST"])
def packages():
    if request.method == "POST":
        for package in current_user.bank.packages:
            prefix = f"p{package.id}_"
            package.enabled = f"{prefix}enabled" in request.form
            package.name = request.form.get(f"{prefix}name", package.name).strip()[:80] or package.name
            package.description = request.form.get(f"{prefix}description", "").strip()[:255]
            band = request.form.get(f"{prefix}band")
            if band in dict(BAND_CHOICES):
                package.recommended_band = band
            package.position = request.form.get(f"{prefix}position", package.position, type=int)
        db.session.commit()
        flash("Packages mis à jour.", "success")
        return redirect(url_for(".packages"))
    return render_template("admin/packages.html", packages=current_user.bank.packages, band_choices=BAND_CHOICES,
                           catalog=CATALOG_BY_CODE)


# ------------------------------------------------------------------ CRUD générique
def _entity_or_404(slug):
    entity = ENTITIES.get(slug)
    if entity is None:
        abort(404)
    return entity


@bp.route("/contenu/<slug>")
def crud_list(slug):
    entity = _entity_or_404(slug)
    return render_template("admin/crud_list.html", entity=entity, items=entity.query().all())


@bp.route("/contenu/<slug>/nouveau", methods=["GET", "POST"])
@bp.route("/contenu/<slug>/<int:obj_id>", methods=["GET", "POST"])
def crud_form(slug, obj_id=None):
    entity = _entity_or_404(slug)
    obj = entity.get(obj_id) if obj_id else None
    if obj_id and obj is None:
        abort(404)
    if request.method == "POST":
        target = obj or entity.model()
        errors = entity.fill(target, request.form)
        if errors:
            for error in errors:
                flash(error, "danger")
        else:
            if obj is None:
                db.session.add(target)
            db.session.commit()
            flash("Enregistré.", "success")
            return redirect(url_for(".crud_list", slug=slug))
    # Valeurs par défaut d'un nouvel élément, complétées par l'URL (ex. ?unit_id=3 depuis la page Parcours)
    defaults = {"published_at": datetime.now().replace(second=0, microsecond=0), "band": "all", "active": True,
                "position": 0}
    defaults.update({f.name: request.args[f.name] for f in entity.fields if f.name in request.args})
    source = obj or SimpleNamespace(**defaults)
    return render_template("admin/crud_form.html", entity=entity, obj=obj, source=source, form=request.form)


@bp.route("/contenu/<slug>/<int:obj_id>/supprimer", methods=["POST"])
def crud_delete(slug, obj_id):
    entity = _entity_or_404(slug)
    obj = entity.get(obj_id) or abort(404)
    db.session.delete(obj)
    db.session.commit()
    flash("Supprimé.", "info")
    return redirect(url_for(".crud_list", slug=slug))


# ------------------------------------------------------------------ quiz
def _quiz_or_404(quiz_id):
    quiz = db.session.get(Quiz, quiz_id)
    if quiz is None or quiz.bank_id != current_user.bank_id:
        abort(404)
    return quiz


def _fill_quiz(quiz, form):
    title = form.get("title", "").strip()
    try:
        publish_date = date.fromisoformat(form.get("publish_date", ""))
    except ValueError:
        publish_date = None
    if not title or not publish_date:
        flash("Titre et date de publication obligatoires.", "danger")
        return False
    quiz.title = title[:200]
    quiz.description = form.get("description", "").strip()[:500]
    quiz.publish_date = publish_date
    quiz.band = form.get("band") if form.get("band") in dict(BAND_CHOICES) else "all"
    return True


@bp.route("/quiz", methods=["GET", "POST"])
def quizzes():
    if request.method == "POST":
        quiz = Quiz(bank_id=current_user.bank_id)
        if _fill_quiz(quiz, request.form):
            db.session.add(quiz)
            db.session.commit()
            flash("Quiz créé : ajoutez maintenant ses questions.", "success")
            return redirect(url_for(".quiz_edit", quiz_id=quiz.id))
    items = Quiz.query.filter_by(bank_id=current_user.bank_id).order_by(Quiz.publish_date.desc()).all()
    return render_template("admin/quizzes.html", quizzes=items, band_choices=BAND_CHOICES, today=date.today())


@bp.route("/quiz/<int:quiz_id>", methods=["GET", "POST"])
def quiz_edit(quiz_id):
    quiz = _quiz_or_404(quiz_id)
    if request.method == "POST" and _fill_quiz(quiz, request.form):
        db.session.commit()
        flash("Quiz mis à jour.", "success")
        return redirect(url_for(".quiz_edit", quiz_id=quiz.id))
    return render_template("admin/quiz_edit.html", quiz=quiz, band_choices=BAND_CHOICES)


@bp.route("/quiz/<int:quiz_id>/questions", methods=["POST"])
def question_add(quiz_id):
    quiz = _quiz_or_404(quiz_id)
    text = request.form.get("text", "").strip()
    choices = [request.form.get(f"choice_{i}", "").strip() for i in range(1, 5)]
    correct = request.form.get("correct", type=int)
    filled = [(i, c) for i, c in enumerate(choices, start=1) if c]
    if not text or len(filled) < 2 or correct not in {i for i, _ in filled}:
        flash("Une question, au moins deux réponses et la bonne réponse cochée sont nécessaires.", "danger")
    else:
        question = QuizQuestion(quiz=quiz, text=text[:500], explanation=request.form.get("explanation", "")[:500],
                                position=len(quiz.questions))
        question.choices = [QuizChoice(text=c[:300], is_correct=(i == correct)) for i, c in filled]
        db.session.add(question)
        db.session.commit()
        flash("Question ajoutée.", "success")
    return redirect(url_for(".quiz_edit", quiz_id=quiz.id))


@bp.route("/quiz/questions/<int:question_id>/supprimer", methods=["POST"])
def question_delete(question_id):
    question = db.session.get(QuizQuestion, question_id)
    if question is None or question.quiz.bank_id != current_user.bank_id:
        abort(404)
    quiz_id = question.quiz_id
    db.session.delete(question)
    db.session.commit()
    flash("Question supprimée.", "info")
    return redirect(url_for(".quiz_edit", quiz_id=quiz_id))


@bp.route("/quiz/<int:quiz_id>/supprimer", methods=["POST"])
def quiz_delete(quiz_id):
    db.session.delete(_quiz_or_404(quiz_id))
    db.session.commit()
    flash("Quiz supprimé.", "info")
    return redirect(url_for(".quizzes"))


# ------------------------------------------------------------------ Q&A
@bp.route("/questions")
def qa_list():
    questions = QAQuestion.query.filter_by(bank_id=current_user.bank_id).order_by(QAQuestion.created_at.desc()).all()
    return render_template("admin/qa_list.html", questions=questions)


@bp.route("/questions/<int:question_id>", methods=["GET", "POST"])
def qa_detail(question_id):
    question = db.session.get(QAQuestion, question_id)
    if question is None or question.bank_id != current_user.bank_id:
        abort(404)
    if request.method == "POST":
        body = request.form.get("body", "").strip()
        if body:
            db.session.add(QAAnswer(question_id=question.id, user_id=current_user.id, body=body, is_official=True))
            db.session.commit()
            flash("Réponse officielle publiée.", "success")
        return redirect(url_for(".qa_detail", question_id=question.id))
    return render_template("admin/qa_detail.html", question=question)


@bp.route("/questions/<int:question_id>/supprimer", methods=["POST"])
def qa_delete(question_id):
    question = db.session.get(QAQuestion, question_id)
    if question is None or question.bank_id != current_user.bank_id:
        abort(404)
    db.session.delete(question)
    db.session.commit()
    flash("Question supprimée.", "info")
    return redirect(url_for(".qa_list"))


@bp.route("/reponses/<int:answer_id>/supprimer", methods=["POST"])
def answer_delete(answer_id):
    answer = db.session.get(QAAnswer, answer_id)
    if answer is None or answer.question.bank_id != current_user.bank_id:
        abort(404)
    question_id = answer.question_id
    db.session.delete(answer)
    db.session.commit()
    return redirect(url_for(".qa_detail", question_id=question_id))


# ------------------------------------------------------------------ modération communauté
@bp.route("/communaute")
def community():
    posts = Post.query.filter_by(bank_id=current_user.bank_id).order_by(Post.created_at.desc()).all()
    return render_template("admin/community.html", posts=posts)


@bp.route("/communaute/<int:post_id>/supprimer", methods=["POST"])
def post_delete(post_id):
    post = db.session.get(Post, post_id)
    if post is None or post.bank_id != current_user.bank_id:
        abort(404)
    db.session.delete(post)
    db.session.commit()
    flash("Publication supprimée.", "info")
    return redirect(url_for(".community"))


@bp.route("/communaute/commentaires/<int:comment_id>/supprimer", methods=["POST"])
def comment_delete(comment_id):
    comment = db.session.get(PostComment, comment_id)
    if comment is None or comment.post.bank_id != current_user.bank_id:
        abort(404)
    db.session.delete(comment)
    db.session.commit()
    flash("Commentaire supprimé.", "info")
    return redirect(url_for(".community"))


# ------------------------------------------------------------------ offres : prospects
@bp.route("/offres/interets")
def interests():
    items = OfferInterest.query.join(Offer).filter(Offer.bank_id == current_user.bank_id) \
        .order_by(OfferInterest.created_at.desc()).all()
    return render_template("admin/interests.html", interests=items)


# ------------------------------------------------------------------ utilisateurs
@bp.route("/utilisateurs")
def users():
    role = request.args.get("role")
    query = bank_users()
    if role in ROLES:
        query = query.filter_by(role=role)
    return render_template("admin/users.html", users=query.order_by(User.created_at.desc()).all(),
                           roles=ROLES, selected=role)


@bp.route("/utilisateurs/nouveau", methods=["GET", "POST"])
def user_new():
    form = request.form
    if request.method == "POST":
        role = form.get("role")
        email = form.get("email", "").strip().lower()
        first_name, last_name = form.get("first_name", "").strip(), form.get("last_name", "").strip()
        password = form.get("password", "")
        birth_date = None
        errors = []
        if role not in ROLES:
            errors.append("Rôle invalide.")
        if not EMAIL.match(email):
            errors.append("E-mail invalide.")
        elif User.query.filter_by(email=email).first():
            errors.append("Cet e-mail est déjà utilisé.")
        if not first_name or not last_name:
            errors.append("Prénom et nom obligatoires.")
        if len(password) < 8:
            errors.append("Mot de passe : 8 caractères minimum.")
        if role == ROLE_CLIENT:
            try:
                birth_date = date.fromisoformat(form.get("birth_date", ""))
                age = User(birth_date=birth_date).age
                if not MIN_CLIENT_AGE <= age <= MAX_CLIENT_AGE:
                    errors.append(f"Un client doit avoir entre {MIN_CLIENT_AGE} et {MAX_CLIENT_AGE} ans.")
            except ValueError:
                errors.append("Date de naissance obligatoire pour un client.")
        if errors:
            for error in errors:
                flash(error, "danger")
        else:
            user = User(bank_id=current_user.bank_id, role=role, email=email, first_name=first_name,
                        last_name=last_name, birth_date=birth_date,
                        must_change_password=role == ROLE_CLIENT)  # mot de passe provisoire, puis test de niveau
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            if role == ROLE_CLIENT and "send_credentials" in form:
                send_credentials(user, password, current_user)
            flash(f"Compte {ROLES[role].lower()} créé pour {user.full_name}.", "success")
            return redirect(url_for(".users"))
    return render_template("admin/user_form.html", roles=ROLES, form=form)


@bp.route("/utilisateurs/<int:user_id>/activation", methods=["POST"])
def user_toggle(user_id):
    user = bank_users().filter_by(id=user_id).first_or_404()
    if user.id == current_user.id:
        flash("Vous ne pouvez pas désactiver votre propre compte.", "warning")
    else:
        user.active = not user.active
        db.session.commit()
        flash(f"Compte de {user.full_name} {'activé' if user.active else 'désactivé'}.", "info")
    return redirect(request.referrer or url_for(".users"))


@bp.route("/utilisateurs/<int:user_id>")
def user_detail(user_id):
    user = bank_users().filter_by(id=user_id).first_or_404()
    attempts = QuizAttempt.query.filter_by(user_id=user.id).order_by(QuizAttempt.created_at.desc()).limit(20).all()
    scores = GameScore.query.filter_by(user_id=user.id).order_by(GameScore.created_at.desc()).limit(20).all()
    return render_template("admin/user_detail.html", user=user, attempts=attempts, scores=scores,
                           games=games.GAMES, roles=ROLES, levels=LEVELS,
                           sections=build_path(user) if user.role == ROLE_CLIENT else [])


# ------------------------------------------------------------------ paramètres de la banque
@bp.route("/parametres", methods=["GET", "POST"])
def settings():
    bank = current_user.bank
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        color = request.form.get("primary_color", "")
        if not name or not HEX_COLOR.match(color):
            flash("Nom obligatoire et couleur au format #RRGGBB.", "danger")
        else:
            bank.name = name[:120]
            bank.primary_color = color
            bank.welcome_message = request.form.get("welcome_message", "").strip()[:255] or None
            db.session.commit()
            flash("Paramètres enregistrés.", "success")
            return redirect(url_for(".settings"))
    return render_template("admin/settings.html", bank=bank, bands=BANDS)


# ------------------------------------------------------------------ programme pédagogique (parcours)
@bp.route("/parcours")
def curriculum():
    units = PathUnit.query.filter_by(bank_id=current_user.bank_id).order_by(PathUnit.position, PathUnit.id).all()
    sections = [(CATALOG_BY_CODE[code], [u for u in units if u.package_code == code]) for code in PATH_PACKAGES]
    totals = {"units": len(units), "lessons": sum(len(u.lessons) for u in units),
              "cards": sum(len(lsn.cards) for u in units for lsn in u.lessons)}
    return render_template("admin/curriculum.html", sections=sections, totals=totals)


def _lesson_or_404(lesson_id):
    return Lesson.query.filter_by(id=lesson_id, bank_id=current_user.bank_id).first_or_404()


@bp.route("/parcours/lecons/<int:lesson_id>", methods=["GET", "POST"])
def lesson_cards(lesson_id):
    lesson = _lesson_or_404(lesson_id)
    if request.method == "POST":
        form = request.form
        kind = form.get("kind")
        body = form.get("body", "").strip()
        card = LessonCard(kind=kind, body=body, position=len(lesson.cards),
                          explanation=form.get("explanation", "").strip()[:500] or None)
        error = None
        if kind not in dict(CARD_KINDS) or not body:
            error = "Type et texte obligatoires."
        elif kind == "theory":
            card.title = form.get("title", "").strip()[:200] or None
        elif kind == "choice":
            choices = [form.get(f"choice_{i}", "").strip() for i in range(1, 5)]
            filled = [c for c in choices if c]
            correct = form.get("correct", type=int)
            if len(filled) < 2 or correct is None or correct > len(choices) or not choices[correct - 1]:
                error = "Au moins deux réponses, et la bonne réponse cochée."
            else:
                card.choices = filled
                card.answer = str(filled.index(choices[correct - 1]))
        elif kind == "number":
            value = parse_number(form.get("answer", ""))
            if value is None:
                error = "La réponse chiffrée est invalide."
            else:
                card.answer = str(value)
                card.unit_label = form.get("unit_label", "").strip()[:12] or None
        if error:
            flash(error, "danger")
        else:
            lesson.cards.append(card)
            db.session.commit()
            flash("Fiche ajoutée.", "success")
            return redirect(url_for(".lesson_cards", lesson_id=lesson.id) + "#ajout")
    return render_template("admin/lesson_cards.html", lesson=lesson, kinds=CARD_KINDS)


@bp.route("/parcours/fiches/<int:card_id>/supprimer", methods=["POST"])
def card_delete(card_id):
    card = db.session.get(LessonCard, card_id)
    if card is None or card.lesson.bank_id != current_user.bank_id:
        abort(404)
    lesson_id = card.lesson_id
    db.session.delete(card)
    db.session.commit()
    flash("Fiche supprimée.", "info")
    return redirect(url_for(".lesson_cards", lesson_id=lesson_id))


@bp.route("/parcours/fiches/<int:card_id>/deplacer/<direction>", methods=["POST"])
def card_move(card_id, direction):
    card = db.session.get(LessonCard, card_id)
    if card is None or card.lesson.bank_id != current_user.bank_id or direction not in ("haut", "bas"):
        abort(404)
    cards = list(card.lesson.cards)
    i = cards.index(card)
    j = i - 1 if direction == "haut" else i + 1
    if 0 <= j < len(cards):
        cards[i], cards[j] = cards[j], cards[i]
        for position, c in enumerate(cards):
            c.position = position
        db.session.commit()
    return redirect(url_for(".lesson_cards", lesson_id=card.lesson_id))


# ------------------------------------------------------------------ Information : inscriptions aux évènements
@bp.route("/information/<int:announcement_id>/inscrits")
def event_registrations(announcement_id):
    item = Announcement.query.filter_by(id=announcement_id, bank_id=current_user.bank_id).first_or_404()
    registrations = EventRegistration.query.filter_by(announcement_id=item.id)         .order_by(EventRegistration.created_at).all()
    return render_template("admin/event_registrations.html", item=item, registrations=registrations)
