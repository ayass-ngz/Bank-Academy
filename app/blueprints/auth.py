from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, PasswordField, SelectField, StringField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, ValidationError

from ..extensions import db
from ..models import ROLE_CLIENT, ROLE_PARENT, Bank, User
from ..packages import MAX_CLIENT_AGE, MIN_CLIENT_AGE
from .main import home_url

bp = Blueprint("auth", __name__)


class LoginForm(FlaskForm):
    email = StringField("E-mail", validators=[DataRequired(), Email()])
    password = PasswordField("Mot de passe", validators=[DataRequired()])
    remember = BooleanField("Se souvenir de moi")


class RegisterForm(FlaskForm):
    bank_id = SelectField("Ma banque", coerce=int)
    first_name = StringField("Prénom", validators=[DataRequired(), Length(max=80)])
    last_name = StringField("Nom", validators=[DataRequired(), Length(max=80)])
    email = StringField("E-mail", validators=[DataRequired(), Email(), Length(max=255)])
    birth_date = DateField("Date de naissance", validators=[Optional()])
    password = PasswordField("Mot de passe", validators=[DataRequired(), Length(min=8, message="8 caractères minimum.")])
    confirm = PasswordField("Confirmation", validators=[EqualTo("password", message="Les mots de passe diffèrent.")])

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.strip().lower()).first():
            raise ValidationError("Un compte existe déjà avec cet e-mail.")


def age_on(birth_date, today=None):
    today = today or date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def _safe_next(target):
    return target if target and target.startswith("/") and not target.startswith("//") else None


@bp.route("/connexion", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(home_url(current_user))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user and user.check_password(form.password.data):
            if not user.active:
                flash("Ce compte a été désactivé par la banque.", "danger")
            else:
                login_user(user, remember=form.remember.data)
                if user.role == ROLE_CLIENT:
                    user.register_activity()  # une connexion par jour entretient la série
                    db.session.commit()
                return redirect(_safe_next(request.args.get("next")) or home_url(user))
        else:
            flash("E-mail ou mot de passe incorrect.", "danger")
    return render_template("auth/login.html", form=form)


@bp.route("/inscription", methods=["GET", "POST"], defaults={"role": ROLE_CLIENT})
@bp.route("/inscription/parent", methods=["GET", "POST"], defaults={"role": ROLE_PARENT})
def register(role):
    if current_user.is_authenticated:
        return redirect(home_url(current_user))
    form = RegisterForm()
    form.bank_id.choices = [(b.id, b.name) for b in Bank.query.order_by(Bank.name)]
    if role == ROLE_PARENT:
        del form.birth_date

    if form.validate_on_submit():
        error = None
        if role == ROLE_CLIENT:
            if not form.birth_date.data:
                error = "La date de naissance est obligatoire."
            elif MIN_CLIENT_AGE <= age_on(form.birth_date.data) < 18:
                # Un mineur ne crée pas son compte seul : c'est son parent qui le fait
                error = ("Tu as moins de 18 ans : demande à ton parent de créer ton compte depuis son espace "
                         "parent. Tu recevras tes identifiants par e-mail.")
            elif not MIN_CLIENT_AGE <= age_on(form.birth_date.data) <= MAX_CLIENT_AGE:
                error = f"L'application est réservée aux {MIN_CLIENT_AGE} – {MAX_CLIENT_AGE} ans."
            if error:
                form.birth_date.errors.append(error)
        if not error:
            user = User(
                bank_id=form.bank_id.data, role=role,
                email=form.email.data.strip().lower(),
                first_name=form.first_name.data.strip(), last_name=form.last_name.data.strip(),
                birth_date=form.birth_date.data if role == ROLE_CLIENT else None,
            )
            user.set_password(form.password.data)
            if role == ROLE_CLIENT:
                user.register_activity()
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash(f"Bienvenue {user.first_name} !", "success")
            return redirect(home_url(user))
    return render_template("auth/register.html", form=form, role=role)


@bp.route("/deconnexion", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("À bientôt !", "info")
    return redirect(url_for("main.index"))
