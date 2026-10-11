import re
from functools import wraps

from flask import abort, g
from flask_login import current_user, login_required
from markupsafe import Markup, escape

from .models import ROLE_CLIENT
from .packages import is_accessible

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MONTHS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapper

    return decorator


def client_packages(user):
    """Packages activés par la banque ET accessibles à la tranche d'âge du client."""
    return [p for p in user.bank.packages if p.enabled and is_accessible(p.code, user.band)]


def package_required(code):
    """Protège une vue client : package activé par la banque et autorisé pour l'âge."""

    def decorator(view):
        @wraps(view)
        @role_required(ROLE_CLIENT)
        def wrapper(*args, **kwargs):
            package = current_user.bank.package(code)
            if package is None or not package.enabled:
                abort(404)
            if not is_accessible(code, current_user.band):
                abort(403, "Ce package n'est pas disponible pour ta tranche d'âge.")
            g.package = package
            return view(*args, **kwargs)

        return wrapper

    return decorator


def is_safe_url(value):
    """N'accepte que des liens http(s) (évite les liens javascript: dans les href)."""
    return not value or value.lower().startswith(("http://", "https://"))


def register_template_filters(app):
    @app.template_filter("nl2br")
    def nl2br(value):
        if not value:
            return ""
        return Markup("<br>".join(escape(line) for line in str(value).splitlines()))

    @app.template_filter("date_fr")
    def date_fr(value):
        if not value:
            return ""
        return f"{value.day} {MONTHS[value.month - 1]} {value.year}"

    @app.template_filter("datetime_fr")
    def datetime_fr(value):
        if not value:
            return ""
        return f"{date_fr(value)} à {value:%H:%M}"
