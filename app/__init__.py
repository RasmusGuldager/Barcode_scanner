from zoneinfo import ZoneInfo

from flask import Flask
from sqlalchemy import event
from sqlalchemy.engine import Engine

from . import cli
from .auth import load_current_user
from .config import Config
from .extensions import csrf, db, migrate
from .services.labels import label_text

LOCAL_TZ = ZoneInfo("Europe/Copenhagen")


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    # SQLite ignores foreign keys (and ON DELETE) unless this is turned on.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_app(config: object | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config or Config())

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    cli.register(app)

    app.before_request(load_current_user)

    @app.template_filter("localtime")
    def localtime(value, fmt="%d-%m-%Y %H:%M"):
        """Show a UTC datetime in Danish time."""
        return value.astimezone(LOCAL_TZ).strftime(fmt) if value else ""

    app.jinja_env.globals["label_text"] = label_text

    from .admin import bp as admin_bp
    from .rental import bp as rental_bp

    app.register_blueprint(rental_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    return app
