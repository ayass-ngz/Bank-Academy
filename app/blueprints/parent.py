from datetime import date, datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import or_

from .. import games
from ..extensions import db
from ..models import ROLE_CLIENT, ROLE_PARENT, Announcement, GameScore, QuizAttempt, User
from ..packages import CUSTOMER_RELATIONS, PARENTAL
from ..onboarding import LEVELS, send_credentials, temporary_password
from ..path import build_path
from ..utils import EMAIL, role_required

bp = Blueprint("parent", __name__)


def _package_enabled(code):
    pkg = current_user.bank.package(code)
    return bool(pkg and pkg.enabled)


def _my_child_or_404(child_id):
    child = next((c for c in current_user.children if c.id == child_id), None)
    if child is None:
        abort(404)
    return child


@bp.route("/")
@role_required(ROLE_PARENT)
def dashboard():
    parental_enabled = _package_enabled(PARENTAL)
    child_ids = [c.id for c in current_user.children]
    announcements, events = [], []
    if parental_enabled:
        announcements = Announcement.query.filter(
            Announcement.bank_id == current_user.bank_id,
            Announcement.package_code == PARENTAL,
            or_(
                (Announcement.child_id.is_(None) & Announcement.audience.in_(["all", "parents"])),
                Announcement.child_id.in_(child_ids or [-1]),
            ),
        ).order_by(Announcement.created_at.desc()).limit(20).all()
    if _package_enabled(CUSTOMER_RELATIONS):
        events = Announcement.query.filter(
            Announcement.bank_id == current_user.bank_id,
            Announcement.package_code == CUSTOMER_RELATIONS,
            Announcement.audience.in_(["all", "parents"]),
            Announcement.child_id.is_(None),
            or_(Announcement.event_date.is_(None), Announcement.event_date >= datetime.now()),
        ).order_by(Announcement.event_date.is_(None), Announcement.event_date, Announcement.created_at.desc()) \
            .limit(10).all()
    paths = {c.id: build_path(c) for c in current_user.children}
    return render_template("parent/dashboard.html", parental_enabled=parental_enabled,
                           announcements=announcements, events=events, paths=paths, levels=LEVELS)


@bp.route("/enfants/<int:child_id>")
@role_required(ROLE_PARENT)
def child_detail(child_id):
    child = _my_child_or_404(child_id)
    attempts = QuizAttempt.query.filter_by(user_id=child.id).order_by(QuizAttempt.created_at.desc()).limit(20).all()
    scores = GameScore.query.filter_by(user_id=child.id).order_by(GameScore.created_at.desc()).limit(20).all()
    announcements = Announcement.query.filter_by(bank_id=current_user.bank_id, package_code=PARENTAL,
                                                 child_id=child.id).order_by(Announcement.created_at.desc()).all()
    return render_template("parent/child_detail.html", child=child, attempts=attempts, scores=scores,
                           announcements=announcements, games=games.GAMES,
                           sections=build_path(child))


# ------------------------------------------------------------------ création du compte d'un enfant
@bp.route("/enfants/nouveau", methods=["GET", "POST"])
@role_required(ROLE_PARENT)
def child_new():
    form = request.form
    if request.method == "POST":
        first_name, last_name = form.get("first_name", "").strip(), form.get("last_name", "").strip()
        email = form.get("email", "").strip().lower()
        errors = []
        try:
            birth_date = date.fromisoformat(form.get("birth_date", ""))
            age = User(birth_date=birth_date).age
            if age >= 18:
                errors.append("À partir de 18 ans, le jeune crée son compte lui-même depuis la page d'inscription.")
            elif age < 10:
                errors.append("L'application est accessible à partir de 10 ans.")
        except ValueError:
            birth_date = None
            errors.append("Indiquez la date de naissance de votre enfant.")
        if not first_name or not last_name:
            errors.append("Prénom et nom obligatoires.")
        if not EMAIL.match(email):
            errors.append("Indiquez l'adresse e-mail de votre enfant : il y recevra ses identifiants.")
        elif User.query.filter_by(email=email).first():
            errors.append("Un compte existe déjà avec cette adresse e-mail.")
        if errors:
            for error in errors:
                flash(error, "danger")
        else:
            password = temporary_password()
            child = User(bank_id=current_user.bank_id, role=ROLE_CLIENT, email=email, first_name=first_name,
                         last_name=last_name, birth_date=birth_date, must_change_password=True)
            child.set_password(password)
            current_user.children.append(child)
            db.session.add(child)
            db.session.commit()
            channel = send_credentials(child, password, current_user)
            return render_template("parent/child_created.html", child=child, demo=channel == "outbox")
    return render_template("parent/child_form.html", form=form)


@bp.route("/enfants/<int:child_id>/identifiants", methods=["POST"])
@role_required(ROLE_PARENT)
def resend_credentials(child_id):
    child = _my_child_or_404(child_id)
    if not child.must_change_password:
        flash(f"{child.first_name} a déjà choisi son mot de passe : il peut le réinitialiser lui-même.", "info")
        return redirect(url_for(".dashboard"))
    password = temporary_password()
    child.set_password(password)
    db.session.commit()
    channel = send_credentials(child, password, current_user)
    return render_template("parent/child_created.html", child=child, demo=channel == "outbox", resent=True)
