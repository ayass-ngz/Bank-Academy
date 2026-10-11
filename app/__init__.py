import os

from flask import Flask, render_template
from flask_login import current_user
from sqlalchemy import event
from sqlalchemy.engine import Engine

from config import Config

from .extensions import csrf, db, login_manager, migrate
from .packages import BANDS, CATALOG_BY_CODE

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv est optionnel
    pass


@event.listens_for(Engine, "connect")
def _sqlite_foreign_keys(dbapi_connection, connection_record):
    # SQLite n'applique les clés étrangères que si on le lui demande
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    os.makedirs(app.instance_path, exist_ok=True)
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(app.instance_path, "bank_academy.db")

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Connecte-toi pour accéder à cette page."
    login_manager.login_message_category = "info"

    from . import models

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(models.User, int(user_id))

    from .blueprints.admin import bp as admin_bp
    from .blueprints.auth import bp as auth_bp
    from .blueprints.client import bp as client_bp
    from .blueprints.main import bp as main_bp
    from .blueprints.parent import bp as parent_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(client_bp, url_prefix="/app")
    app.register_blueprint(parent_bp, url_prefix="/parent")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    from .path import client_rail, rank_of
    from .utils import client_packages, register_template_filters

    register_template_filters(app)

    @app.context_processor
    def inject_globals():
        ctx = {"BANDS": BANDS, "CATALOG": CATALOG_BY_CODE, "bank": None, "nav_packages": []}
        if current_user.is_authenticated:
            ctx["bank"] = current_user.bank
            if current_user.role == models.ROLE_CLIENT:
                ctx["nav_packages"] = client_packages(current_user)
                ctx["rail"] = lambda: client_rail(current_user)  # calculé seulement si le gabarit l'affiche
                ctx["client_rank"] = lambda: rank_of(current_user)
        return ctx

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", code=403, message=getattr(e, "description", None)), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404), 404

    from .seed import register_commands

    register_commands(app)
    return app
