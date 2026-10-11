import time
from datetime import date, datetime, timedelta

from flask import (Blueprint, Response, abort, current_app, flash, jsonify, redirect, render_template, request,
                   session, url_for)
from flask_login import current_user
from sqlalchemy import func

from .. import arcade, games, lessons
from .. import onboarding as placement
from ..extensions import db
from ..game_data import TIPS
from ..models import (POST_CATEGORIES, RESOURCE_CATEGORIES, ROLE_CLIENT, Announcement, Completion, EventRegistration,
                      GameScore, Lesson,
                      NewsArticle, Offer, OfferInterest, Podcast, Post, PostComment, QAAnswer, QAQuestion, Quiz,
                      QuizAttempt, Resource, User, band_filter)
from ..packages import (BANK_OFFERS, CUSTOMER_RELATIONS, EDUCATION_ADVANCED, EDUCATION_BASIC, ENTREPRENEURSHIP,
                        PARENTAL, is_accessible, matches_band)
from ..path import (CHEST_POINTS, READ_POINTS, band_clients, build_path, client_rail, find_node, mark_complete,
                    promote_if_ready, quiz_points)
from ..utils import package_required, role_required

bp = Blueprint("client", __name__)


# ------------------------------------------------------------------ helpers
def owned_or_404(model, obj_id):
    obj = db.session.get(model, obj_id)
    if obj is None or obj.bank_id != current_user.bank_id:
        abort(404)
    return obj


def visible(model):
    """Requête sur `model` limitée à la banque et à la tranche d'âge du client."""
    return model.query.filter(model.bank_id == current_user.bank_id, band_filter(model.band, current_user.band))


def client_announcements(package_code):
    return Announcement.query.filter(
        Announcement.bank_id == current_user.bank_id,
        Announcement.package_code == package_code,
        Announcement.audience.in_(["all", "clients", current_user.band]),
        Announcement.child_id.is_(None),
    )


def published_quizzes():
    return visible(Quiz).filter(Quiz.publish_date <= date.today()).order_by(Quiz.publish_date.desc(), Quiz.id.desc())


# ------------------------------------------------------------------ arrivée d'un nouvel élève
ONBOARDING_ENDPOINTS = {"client.onboarding", "client.onboarding_test", "client.onboarding_answer",
                        "client.onboarding_finish", "client.onboarding_skip", "client.onboarding_result"}


@bp.before_request
def onboarding_guard():
    """Mot de passe provisoire à changer, puis test de niveau, avant tout le reste."""
    if not current_user.is_authenticated or current_user.role != ROLE_CLIENT:
        return None
    if current_user.must_change_password:
        if request.endpoint != "client.change_password":
            return redirect(url_for("client.change_password"))
    elif current_user.onboarded_at is None and request.endpoint not in ONBOARDING_ENDPOINTS:
        return redirect(url_for("client.onboarding"))
    return None


@bp.route("/bienvenue/mot-de-passe", methods=["GET", "POST"])
@role_required(ROLE_CLIENT)
def change_password():
    if request.method == "POST":
        password = request.form.get("password", "")
        if len(password) < 8:
            flash("Ton mot de passe doit contenir au moins 8 caractères.", "danger")
        elif password != request.form.get("confirm"):
            flash("Les deux mots de passe ne sont pas identiques.", "danger")
        elif current_user.check_password(password):
            flash("Choisis un mot de passe différent du mot de passe provisoire.", "danger")
        else:
            current_user.set_password(password)
            current_user.must_change_password = False
            db.session.commit()
            flash("Ton mot de passe est enregistré !", "success")
            return redirect(url_for(".onboarding" if current_user.onboarded_at is None else ".dashboard"))
    return render_template("client/change_password.html")


@bp.route("/bienvenue")
@role_required(ROLE_CLIENT)
def onboarding():
    return render_template("client/onboarding.html", levels=placement.LEVELS,
                           retake=current_user.onboarded_at is not None)


PLACEMENT_GAME = {"name": "Test de positionnement", "icon": "bi-compass", "color": "#2b59c3", "engine": "placement",
                  "instruction": "Réponds de ton mieux : les questions s'adaptent à tes réponses"}


@bp.route("/bienvenue/test")
@role_required(ROLE_CLIENT)
def onboarding_test():
    question, state = placement.start(current_user)
    if question is None:  # programme vide : rien à évaluer, on démarre au niveau Découverte
        if current_user.onboarded_at is None:
            current_user.level, current_user.onboarded_at = 0, datetime.now()
            db.session.commit()
        return redirect(url_for(".dashboard"))
    session["placement_test"] = state
    return render_template("client/arcade.html", game=PLACEMENT_GAME, code="placement", public=question,
                           action_url=url_for(".onboarding_answer"), finish_url=url_for(".onboarding_finish"),
                           replay_url=url_for(".onboarding_test"), home_url=url_for(".onboarding"))


@bp.route("/bienvenue/test/reponse", methods=["POST"])
@role_required(ROLE_CLIENT)
def onboarding_answer():
    state = session.get("placement_test")
    if not state:
        abort(400, "Aucun test en cours.")
    try:
        result = placement.answer(state, current_user, (request.get_json(silent=True) or {}).get("answer"))
    except ValueError as error:
        return jsonify(error=str(error)), 400
    session["placement_test"] = state
    return jsonify(result)


@bp.route("/bienvenue/test/terminer", methods=["POST"])
@role_required(ROLE_CLIENT)
def onboarding_finish():
    state = session.get("placement_test")
    if not state or not placement.finished(state):
        abort(400, "Le test n'est pas terminé.")
    session.pop("placement_test", None)
    level, confidence = placement.estimate(state["posterior"])
    correct = sum(1 for _, ok in state["history"] if ok)
    first_time = current_user.onboarded_at is None
    # Un nouveau test ne fait jamais perdre un niveau déjà acquis
    current_user.level = level if first_time else max(current_user.level, level)
    if first_time:
        current_user.onboarded_at = datetime.now()
    current_user.register_activity()
    db.session.commit()
    session["placement"] = {"level": level, "correct": correct, "total": len(state["history"]),
                            "confidence": round(confidence * 100), "tiers": [t for t, _ in state["history"]]}
    return jsonify(score=correct * 10, correct=correct, total=len(state["history"]), points=0,
                   streak=current_user.effective_streak, redirect=url_for(".onboarding_result"))


@bp.route("/bienvenue/passer", methods=["POST"])
@role_required(ROLE_CLIENT)
def onboarding_skip():
    if current_user.onboarded_at is None:
        current_user.level = 0
        current_user.onboarded_at = datetime.now()
        db.session.commit()
    flash("C'est parti ! Tu commences le parcours depuis le début.", "success")
    return redirect(url_for(".dashboard"))


@bp.route("/bienvenue/resultat")
@role_required(ROLE_CLIENT)
def onboarding_result():
    result = session.get("placement") or {"level": current_user.level, "correct": None, "total": None}
    sections = [s for s in build_path(current_user) if s.package.code in placement.PLACEMENT_SECTIONS]
    return render_template("client/onboarding_result.html", result=result, levels=placement.LEVELS,
                           level=placement.LEVELS[current_user.level], sections=sections)


def package_enabled(code):
    package = current_user.bank.package(code)
    return bool(package and package.enabled and is_accessible(code, current_user.band))


# ------------------------------------------------------------------ accueil
@bp.route("/")
@role_required(ROLE_CLIENT)
def dashboard():
    user = current_user
    sections = build_path(user)
    next_step = None
    for section in sections:
        for unit in section.units:
            node = next((n for n in unit.nodes if n.state == "current"), None)
            if node:
                next_step = {"node": node, "unit": unit, "section": section}
                break
        if next_step:
            break
    done, total = sum(s.done_count for s in sections), sum(s.total for s in sections)
    percent = round(100 * done / total) if total else 0

    today = date.today()
    monday = today - timedelta(days=today.weekday())
    active = user.active_days_since(monday)
    if user.last_active_date and user.last_active_date >= monday:
        active.add(user.last_active_date)
    week = [{"label": label, "day": monday + timedelta(days=i), "active": monday + timedelta(days=i) in active,
             "today": monday + timedelta(days=i) == today, "future": monday + timedelta(days=i) > today}
            for i, label in enumerate(["L", "M", "M", "J", "V", "S", "D"])]

    game_code = None
    if package_enabled(EDUCATION_BASIC):
        codes = list(games.GAMES)
        game_code = codes[today.toordinal() % len(codes)]
    hour = datetime.now().hour
    return render_template(
        "client/dashboard.html", sections=sections, next_step=next_step, percent=percent,
        stage=0 if done == 0 else (1 if percent < 34 else (2 if percent < 67 else 3)),
        rail=client_rail(user), week=week, game_code=game_code, game=games.GAMES.get(game_code),
        tip=TIPS[today.toordinal() % len(TIPS)],
        greeting="Bonjour" if hour < 12 else ("Bon après-midi" if hour < 18 else "Bonsoir"),
        level=placement.LEVELS[user.level],
        infos=client_announcements(CUSTOMER_RELATIONS).order_by(Announcement.created_at.desc()).limit(3).all()
        if package_enabled(CUSTOMER_RELATIONS) else [],
    )


# ------------------------------------------------------------------ parcours
@bp.route("/parcours")
@role_required(ROLE_CLIENT)
def parcours():
    sections = build_path(current_user)
    code = request.args.get("section")
    section = next((s for s in sections if s.package.code == code), None)
    if section is None:  # par défaut : la première section qui a une étape en cours
        section = next((s for s in sections if any(n.state == "current" for n in s.nodes)),
                       sections[0] if sections else None)
    return render_template("client/parcours.html", sections=sections, section=section)


@bp.route("/parcours/coffre/<ref>", methods=["POST"])
@role_required(ROLE_CLIENT)
def open_chest(ref):
    key = f"chest:{ref}"
    node = find_node(build_path(current_user), key)
    if node is None:
        abort(404)
    if node.state == "current":
        mark_complete(current_user, "chest", ref, CHEST_POINTS)
        db.session.commit()
        flash(f"Palier validé : +{CHEST_POINTS} points !", "success")
    elif node.state == "locked":
        flash("Termine les étapes précédentes pour valider ce palier.", "warning")
    return redirect(request.referrer or url_for(".parcours"))


@bp.route("/profil")
@role_required(ROLE_CLIENT)
def profile():
    attempts = QuizAttempt.query.filter_by(user_id=current_user.id).order_by(QuizAttempt.created_at.desc()).limit(10)
    scores = GameScore.query.filter_by(user_id=current_user.id).order_by(GameScore.created_at.desc()).limit(10)
    sections = build_path(current_user)
    return render_template("client/profile.html", attempts=attempts.all(), scores=scores.all(), games=games.GAMES,
                           levels=placement.LEVELS,
                           sections=sections, steps_done=sum(s.done_count for s in sections))


# ------------------------------------------------------------------ 1. Éducation avancée
@bp.route("/education-avancee")
@package_required(EDUCATION_ADVANCED)
def advanced_home():
    quizzes = published_quizzes().limit(5).all()
    done = {a.quiz_id for a in QuizAttempt.query.filter_by(user_id=current_user.id)}
    return render_template(
        "client/advanced_home.html",
        podcasts=visible(Podcast).filter(Podcast.published_at <= datetime.now())
        .order_by(Podcast.published_at.desc()).limit(4).all(),
        news=visible(NewsArticle).filter(NewsArticle.published_at <= datetime.now())
        .order_by(NewsArticle.published_at.desc()).limit(4).all(),
        quizzes=quizzes, done=done,
        questions=QAQuestion.query.filter_by(bank_id=current_user.bank_id)
        .order_by(QAQuestion.created_at.desc()).limit(5).all(),
    )


@bp.route("/education-avancee/podcasts")
@package_required(EDUCATION_ADVANCED)
def podcasts():
    items = visible(Podcast).filter(Podcast.published_at <= datetime.now()).order_by(Podcast.published_at.desc())
    listened = {int(c.ref) for c in Completion.query.filter_by(user_id=current_user.id, kind="podcast")}
    return render_template("client/podcasts.html", podcasts=items.all(), listened=listened)


@bp.route("/education-avancee/podcasts/<int:podcast_id>/ecoute", methods=["POST"])
@package_required(EDUCATION_ADVANCED)
def podcast_listened(podcast_id):
    podcast = visible(Podcast).filter(Podcast.id == podcast_id).first_or_404()
    if mark_complete(current_user, "podcast", podcast.id):
        db.session.commit()
        flash(f"Podcast écouté : +{READ_POINTS} points !", "success")
    return redirect(url_for(".podcasts") + f"#podcast-{podcast.id}")


@bp.route("/education-avancee/actualites")
@package_required(EDUCATION_ADVANCED)
def news_list():
    items = visible(NewsArticle).filter(NewsArticle.published_at <= datetime.now())
    return render_template("client/news_list.html", news=items.order_by(NewsArticle.published_at.desc()).all())


@bp.route("/education-avancee/actualites/<int:article_id>")
@package_required(EDUCATION_ADVANCED)
def news_detail(article_id):
    article = visible(NewsArticle).filter(NewsArticle.id == article_id,
                                          NewsArticle.published_at <= datetime.now()).first_or_404()
    if mark_complete(current_user, "news", article.id):
        db.session.commit()
        flash(f"Article lu : +{READ_POINTS} points !", "success")
    return render_template("client/news_detail.html", article=article)


@bp.route("/education-avancee/quiz")
@package_required(EDUCATION_ADVANCED)
def quizzes():
    attempts = {a.quiz_id: a for a in QuizAttempt.query.filter_by(user_id=current_user.id)}
    return render_template("client/quizzes.html", quizzes=published_quizzes().all(), attempts=attempts)


@bp.route("/education-avancee/quiz/<int:quiz_id>", methods=["GET", "POST"])
@package_required(EDUCATION_ADVANCED)
def quiz_take(quiz_id):
    quiz = published_quizzes().filter(Quiz.id == quiz_id).first_or_404()
    attempt = QuizAttempt.query.filter_by(user_id=current_user.id, quiz_id=quiz.id).first()
    answers = {}
    if request.method == "POST" and attempt is None and quiz.questions:
        score = 0
        for question in quiz.questions:
            choice_id = request.form.get(f"q{question.id}", type=int)
            answers[question.id] = choice_id
            if any(c.id == choice_id and c.is_correct for c in question.choices):
                score += 1
        total = len(quiz.questions)
        points = quiz_points(score, total)
        attempt = QuizAttempt(user_id=current_user.id, quiz_id=quiz.id, score=score, total=total)
        db.session.add(attempt)
        current_user.register_activity(points)
        db.session.commit()
        flash(f"Quiz terminé : {score}/{total} — +{points} points !", "success")
    return render_template("client/quiz_take.html", quiz=quiz, attempt=attempt, answers=answers)


@bp.route("/education-avancee/questions", methods=["GET", "POST"])
@package_required(EDUCATION_ADVANCED)
def qa_list():
    if request.method == "POST":
        title = request.form.get("title", "").strip()[:200]
        body = request.form.get("body", "").strip()
        if not title or not body:
            flash("Merci de renseigner un titre et ta question.", "warning")
        else:
            question = QAQuestion(bank_id=current_user.bank_id, user_id=current_user.id, title=title, body=body)
            db.session.add(question)
            db.session.commit()
            flash("Question publiée ! La banque et la communauté peuvent te répondre.", "success")
            return redirect(url_for(".qa_detail", question_id=question.id))
    questions = QAQuestion.query.filter_by(bank_id=current_user.bank_id).order_by(QAQuestion.created_at.desc())
    return render_template("client/qa_list.html", questions=questions.all())


@bp.route("/education-avancee/questions/<int:question_id>", methods=["GET", "POST"])
@package_required(EDUCATION_ADVANCED)
def qa_detail(question_id):
    question = owned_or_404(QAQuestion, question_id)
    if request.method == "POST":
        body = request.form.get("body", "").strip()
        if body:
            db.session.add(QAAnswer(question_id=question.id, user_id=current_user.id, body=body))
            db.session.commit()
            flash("Réponse publiée.", "success")
        return redirect(url_for(".qa_detail", question_id=question.id))
    return render_template("client/qa_detail.html", question=question)


# ------------------------------------------------------------------ 2. Entrepreneuriat
@bp.route("/entrepreneuriat")
@package_required(ENTREPRENEURSHIP)
def entrepreneurship_home():
    resources = Resource.query.filter_by(bank_id=current_user.bank_id).order_by(Resource.position, Resource.id).all()
    by_category = [(code, label, [r for r in resources if r.category == code]) for code, label in RESOURCE_CATEGORIES]
    posts = Post.query.filter_by(bank_id=current_user.bank_id).order_by(Post.created_at.desc()).limit(4).all()
    return render_template("client/entrepreneurship_home.html", by_category=by_category, posts=posts,
                           post_categories=dict(POST_CATEGORIES))


@bp.route("/entrepreneuriat/ressources/<int:resource_id>")
@package_required(ENTREPRENEURSHIP)
def resource_detail(resource_id):
    resource = owned_or_404(Resource, resource_id)
    if mark_complete(current_user, "resource", resource.id):
        db.session.commit()
        flash(f"Étape lue : +{READ_POINTS} points !", "success")
    return render_template("client/resource_detail.html", resource=resource,
                           category_label=dict(RESOURCE_CATEGORIES).get(resource.category))


@bp.route("/entrepreneuriat/communaute", methods=["GET", "POST"])
@package_required(ENTREPRENEURSHIP)
def community():
    categories = dict(POST_CATEGORIES)
    if request.method == "POST":
        title = request.form.get("title", "").strip()[:200]
        body = request.form.get("body", "").strip()
        category = request.form.get("category")
        if not title or not body or category not in categories:
            flash("Merci de compléter tous les champs.", "warning")
        else:
            post = Post(bank_id=current_user.bank_id, user_id=current_user.id, title=title, body=body,
                        category=category)
            db.session.add(post)
            db.session.commit()
            flash("Publication en ligne !", "success")
            return redirect(url_for(".post_detail", post_id=post.id))
    selected = request.args.get("categorie")
    posts = Post.query.filter_by(bank_id=current_user.bank_id)
    if selected in categories:
        posts = posts.filter_by(category=selected)
    return render_template("client/community.html", posts=posts.order_by(Post.created_at.desc()).all(),
                           categories=POST_CATEGORIES, category_labels=categories, selected=selected)


@bp.route("/entrepreneuriat/communaute/<int:post_id>", methods=["GET", "POST"])
@package_required(ENTREPRENEURSHIP)
def post_detail(post_id):
    post = owned_or_404(Post, post_id)
    if request.method == "POST":
        body = request.form.get("body", "").strip()
        if body:
            db.session.add(PostComment(post_id=post.id, user_id=current_user.id, body=body))
            db.session.commit()
        return redirect(url_for(".post_detail", post_id=post.id) + "#commentaires")
    return render_template("client/post_detail.html", post=post, category_labels=dict(POST_CATEGORIES))


@bp.route("/entrepreneuriat/communaute/<int:post_id>/supprimer", methods=["POST"])
@package_required(ENTREPRENEURSHIP)
def post_delete(post_id):
    post = owned_or_404(Post, post_id)
    if post.user_id != current_user.id:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash("Publication supprimée.", "info")
    return redirect(url_for(".community"))


@bp.route("/entrepreneuriat/commentaires/<int:comment_id>/supprimer", methods=["POST"])
@package_required(ENTREPRENEURSHIP)
def comment_delete(comment_id):
    comment = db.session.get(PostComment, comment_id)
    if comment is None or comment.post.bank_id != current_user.bank_id:
        abort(404)
    if comment.user_id != current_user.id:
        abort(403)
    post_id = comment.post_id
    db.session.delete(comment)
    db.session.commit()
    return redirect(url_for(".post_detail", post_id=post_id) + "#commentaires")


# ------------------------------------------------------------------ 3. Éducation basique
@bp.route("/education-basique")
@package_required(EDUCATION_BASIC)
def basic_home():
    clients = band_clients(current_user)
    yesterday = date.today() - timedelta(days=1)
    best = dict(db.session.query(GameScore.game_code, func.max(GameScore.score))
                .filter(GameScore.user_id == current_user.id).group_by(GameScore.game_code).all())
    return render_template(
        "client/basic_home.html", games=games.GAMES, categories=games.CATEGORIES, best=best,
        points_board=clients.order_by(User.points.desc(), User.id).limit(10).all(),
        streak_board=clients.filter(User.last_active_date >= yesterday)
        .order_by(User.current_streak.desc(), User.points.desc()).limit(10).all(),
    )


# Les jeux et les leçons partagent le même écran « leçon » et la même logique :
# les manches sont générées côté serveur, les réponses attendues restent en session.
def _start_session(key, rounds, secret):
    session["game"] = {"code": key, "secret": secret, "results": [None] * len(rounds)}


def _current_game(key):
    state = session.get("game")
    if not state or state.get("code") != key:
        abort(400, "Aucune partie en cours.")
    return state


def _check(key, checker):
    state = _current_game(key)
    data = request.get_json(silent=True) or {}
    index = data.get("index")
    if not isinstance(index, int) or not 0 <= index < len(state["secret"]) or state["secret"][index] is None:
        abort(400)
    correct, expected, explanation = checker(state["secret"][index], data.get("answer"))
    if state["results"][index] is None:  # la première réponse fait foi
        state["results"][index] = correct
        session.modified = True
    else:
        correct = state["results"][index]
    return jsonify(correct=correct, expected=expected, explanation=explanation)


def _finish(key):
    state = _current_game(key)
    session.pop("game", None)
    correct = sum(1 for r in state["results"] if r)
    total = sum(1 for item in state["secret"] if item is not None)
    return correct, total


def _game_or_404(code):
    if code not in games.GAMES:
        abort(404)
    return games.GAMES[code]


@bp.route("/education-basique/jeux/<code>")
@package_required(EDUCATION_BASIC)
def game_play(code):
    game = _game_or_404(code)
    urls = {"finish_url": url_for(".game_finish", code=code), "replay_url": url_for(".game_play", code=code),
            "home_url": url_for(".basic_home")}
    if games.is_quiz(code):
        rounds, secret = games.new_game(code, current_user)
        _start_session(code, rounds, secret)
        if game.get("time_limit"):
            session["game"]["started"] = time.time()
        return render_template("client/game.html", title=game["name"], instruction=game["instruction"], rounds=rounds,
                               check_url=url_for(".game_check", code=code), time_limit=game.get("time_limit"), **urls)
    public, state = arcade.ENGINES[game["engine"]].start(current_user)
    session["game"] = {"code": code, "state": state}
    return render_template("client/arcade.html", game=game, code=code, public=public,
                           action_url=url_for(".game_action", code=code), **urls)


@bp.route("/education-basique/jeux/<code>/verifier", methods=["POST"])
@package_required(EDUCATION_BASIC)
def game_check(code):
    game = _game_or_404(code)
    state = _current_game(code)
    limit = game.get("time_limit")
    if limit and time.time() - state.get("started", 0) > limit + 3:  # marge pour la latence réseau
        return jsonify(correct=False, expected="—", explanation="Temps écoulé !", timeout=True)
    return _check(code, lambda item, answer: games.check_answer(code, item, answer))


@bp.route("/education-basique/jeux/<code>/action", methods=["POST"])
@package_required(EDUCATION_BASIC)
def game_action(code):
    game = _game_or_404(code)
    if games.is_quiz(code):
        abort(404)
    state = _current_game(code)
    try:
        result = arcade.ENGINES[game["engine"]].action(state["state"], request.get_json(silent=True) or {})
    except arcade.GameError as error:
        return jsonify(error=str(error)), 400
    session.modified = True
    return jsonify(result)


@bp.route("/education-basique/jeux/<code>/terminer", methods=["POST"])
@package_required(EDUCATION_BASIC)
def game_finish(code):
    game = _game_or_404(code)
    summary = None
    if games.is_quiz(code):
        correct, total = _finish(code)
        score = correct * games.POINTS_PER_CORRECT
    else:
        state = _current_game(code)
        session.pop("game", None)
        result = arcade.ENGINES[game["engine"]].finish(state["state"], request.get_json(silent=True) or {})
        score, correct, total, summary = result["score"], result["correct"], result["total"], result["summary"]
    today_start = datetime.combine(date.today(), datetime.min.time())
    plays_today = GameScore.query.filter(GameScore.user_id == current_user.id, GameScore.game_code == code,
                                         GameScore.created_at >= today_start).count()
    points = score if plays_today < current_app.config["GAME_DAILY_SCORED_PLAYS"] else 0
    db.session.add(GameScore(user_id=current_user.id, game_code=code, score=score, points_awarded=points))
    current_user.register_activity(points)
    db.session.commit()
    note = None if points else "Limite de parties récompensées atteinte pour aujourd'hui : rejoue pour t'entraîner !"
    return jsonify(score=score, correct=correct, total=total, points=points, note=note, summary=summary,
                   streak=current_user.effective_streak, total_points=current_user.points)


# ------------------------------------------------------------------ Leçons du programme pédagogique
def _lesson_or_404(lesson_id):
    lesson = Lesson.query.filter_by(id=lesson_id, bank_id=current_user.bank_id).first_or_404()
    path_unit = lesson.unit
    package = current_user.bank.package(path_unit.package_code)
    if (not path_unit.active or package is None or not package.enabled
            or not is_accessible(path_unit.package_code, current_user.band)
            or not matches_band(path_unit.band, current_user.band)):
        abort(404)
    return lesson


@bp.route("/lecons/<int:lesson_id>")
@role_required(ROLE_CLIENT)
def lesson_play(lesson_id):
    lesson = _lesson_or_404(lesson_id)
    if lesson.unit.package_code in placement.PLACEMENT_SECTIONS and lesson.unit.level > current_user.level:
        flash(f"Cette leçon est réservée au niveau {placement.LEVELS[lesson.unit.level]['name']}. "
              f"Termine d'abord ton niveau actuel ({placement.LEVELS[current_user.level]['name']}).", "warning")
        return redirect(url_for(".parcours", section=lesson.unit.package_code))
    node = find_node(build_path(current_user), f"lesson:{lesson.id}")
    if node is not None and node.state == "locked":
        flash("Termine d'abord les leçons précédentes pour débloquer celle-ci.", "warning")
        return redirect(url_for(".parcours", section=lesson.unit.package_code))
    rounds, secret = lessons.build_rounds(lesson)
    _start_session(f"lesson:{lesson.id}", rounds, secret)
    return render_template("client/game.html", title=lesson.title, instruction=lesson.title, rounds=rounds,
                           check_url=url_for(".lesson_check", lesson_id=lesson.id),
                           finish_url=url_for(".lesson_finish", lesson_id=lesson.id),
                           replay_url=url_for(".lesson_play", lesson_id=lesson.id),
                           home_url=url_for(".parcours", section=lesson.unit.package_code))


@bp.route("/lecons/<int:lesson_id>/verifier", methods=["POST"])
@role_required(ROLE_CLIENT)
def lesson_check(lesson_id):
    _lesson_or_404(lesson_id)
    return _check(f"lesson:{lesson_id}", lessons.check_card)


@bp.route("/lecons/<int:lesson_id>/terminer", methods=["POST"])
@role_required(ROLE_CLIENT)
def lesson_finish(lesson_id):
    lesson = _lesson_or_404(lesson_id)
    correct, total = _finish(f"lesson:{lesson.id}")
    score = correct * games.POINTS_PER_CORRECT
    first_time = mark_complete(current_user, "lesson", lesson.id, score)
    if not first_time:
        current_user.register_activity()  # une révision entretient la série
    db.session.flush()
    promoted = promote_if_ready(current_user) if first_time else None
    db.session.commit()
    note = None if first_time else ("Leçon déjà terminée : cette révision ne rapporte pas de points, "
                                    "mais entretient ta série !")
    if promoted is not None:
        note = (f"🎉 Bravo, tu passes au niveau {placement.LEVELS[promoted]['name']} : "
                "de nouvelles unités sont débloquées dans ton parcours !")
    return jsonify(score=score, correct=correct, total=total, points=score if first_time else 0, note=note,
                   streak=current_user.effective_streak, total_points=current_user.points)


# ------------------------------------------------------------------ 4. Suivi parental (10-17 ans)
@bp.route("/suivi-parental")
@package_required(PARENTAL)
def parental_home():
    announcements = client_announcements(PARENTAL).order_by(Announcement.created_at.desc()).all()
    return render_template("client/parental_home.html", announcements=announcements)


# ------------------------------------------------------------------ 5. Information
INFO_FILTERS = [("", "Tout", None), ("evenements", "Évènements", "evenement"),
                ("interventions", "Interventions", "intervention"), ("annonces", "Annonces", "annonce")]


def _information_item(item_id):
    return client_announcements(CUSTOMER_RELATIONS).filter(Announcement.id == item_id).first_or_404()


@bp.route("/information")
@package_required(CUSTOMER_RELATIONS)
def information_home():
    selected = request.args.get("type", "")
    kind = next((k for code, _, k in INFO_FILTERS if code == selected), None)
    items = client_announcements(CUSTOMER_RELATIONS).all()
    if kind:
        items = [a for a in items if a.kind == kind]
    now = datetime.now()
    upcoming = sorted((a for a in items if a.event_date and a.event_date >= now), key=lambda a: a.event_date)
    others = sorted((a for a in items if not a.event_date or a.event_date < now),
                    key=lambda a: a.created_at, reverse=True)
    registered = {r.announcement_id for r in EventRegistration.query.filter_by(user_id=current_user.id)}
    counts = dict(db.session.query(EventRegistration.announcement_id, func.count(EventRegistration.id))
                  .filter(EventRegistration.announcement_id.in_([a.id for a in upcoming] or [-1]))
                  .group_by(EventRegistration.announcement_id).all())
    return render_template("client/information_home.html", upcoming=upcoming, announcements=others,
                           featured=upcoming[0] if upcoming else None, registered=registered, counts=counts,
                           filters=INFO_FILTERS, selected=selected)


@bp.route("/information/<int:item_id>/participer", methods=["POST"])
@package_required(CUSTOMER_RELATIONS)
def information_rsvp(item_id):
    item = _information_item(item_id)
    if not item.event_date or item.event_date < datetime.now():
        abort(404)
    registration = EventRegistration.query.filter_by(user_id=current_user.id, announcement_id=item.id).first()
    if registration:
        db.session.delete(registration)
        flash("Ta participation est annulée.", "info")
    else:
        db.session.add(EventRegistration(user_id=current_user.id, announcement_id=item.id))
        flash(f"C'est noté, tu participes à « {item.title} » !", "success")
    db.session.commit()
    return redirect(url_for(".information_home") + f"#info-{item.id}")


def _ics_escape(text):
    return (text or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


@bp.route("/information/<int:item_id>/agenda.ics")
@package_required(CUSTOMER_RELATIONS)
def information_ics(item_id):
    item = _information_item(item_id)
    if not item.event_date:
        abort(404)
    end = item.event_date + timedelta(hours=2)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Bank Academy//FR", "BEGIN:VEVENT",
             f"UID:annonce-{item.id}@bank-academy", f"DTSTAMP:{datetime.utcnow():%Y%m%dT%H%M%SZ}",
             f"DTSTART:{item.event_date:%Y%m%dT%H%M%S}", f"DTEND:{end:%Y%m%dT%H%M%S}",
             f"SUMMARY:{_ics_escape(item.title)}", f"DESCRIPTION:{_ics_escape(item.body)}",
             f"LOCATION:{_ics_escape(item.location)}", "END:VEVENT", "END:VCALENDAR"]
    return Response("\r\n".join(lines) + "\r\n", mimetype="text/calendar",
                    headers={"Content-Disposition": f"attachment; filename=evenement-{item.id}.ics"})


# ------------------------------------------------------------------ 6. Offres de la banque (18-24 ans)
@bp.route("/offres")
@package_required(BANK_OFFERS)
def offers_home():
    offers = Offer.query.filter_by(bank_id=current_user.bank_id, active=True).order_by(Offer.created_at.desc()).all()
    interested = {i.offer_id for i in OfferInterest.query.filter_by(user_id=current_user.id)}
    return render_template("client/offers_home.html", offers=offers, interested=interested)


@bp.route("/offres/<int:offer_id>/interet", methods=["POST"])
@package_required(BANK_OFFERS)
def offer_interest(offer_id):
    offer = owned_or_404(Offer, offer_id)
    if not offer.active:
        abort(404)
    if not OfferInterest.query.filter_by(user_id=current_user.id, offer_id=offer.id).first():
        message = request.form.get("message", "").strip()[:500] or None
        db.session.add(OfferInterest(user_id=current_user.id, offer_id=offer.id, message=message))
        db.session.commit()
    flash("Merci ! Un conseiller de la banque va te recontacter.", "success")
    return redirect(url_for(".offers_home"))
