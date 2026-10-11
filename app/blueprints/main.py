from flask import Blueprint, abort, current_app, redirect, render_template, url_for
from flask_login import current_user

from ..models import ROLE_ADMIN, ROLE_PARENT
from ..packages import PACKAGE_CATALOG

bp = Blueprint("main", __name__)


def home_url(user):
    if user.role == ROLE_ADMIN:
        return url_for("admin.dashboard")
    if user.role == ROLE_PARENT:
        return url_for("parent.dashboard")
    return url_for("client.dashboard")


@bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(home_url(current_user))
    return render_template("index.html", catalog=PACKAGE_CATALOG)


@bp.route("/dev/emails")
def dev_emails():
    """Boîte d'envoi de démonstration (uniquement en mode debug, sans serveur SMTP)."""
    if not (current_app.debug or current_app.testing) or current_app.config.get("MAIL_SERVER"):
        abort(404)
    from ..mailer import read_outbox
    return render_template("dev_emails.html", messages=read_outbox())
