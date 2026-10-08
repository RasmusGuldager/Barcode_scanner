from datetime import UTC, datetime

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy import DateTime, MetaData, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, registry


class UTCDateTime(TypeDecorator):
    """Store datetimes as UTC and read them back timezone-aware.

    SQLite has no timezone support and would otherwise return naive datetimes.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                raise ValueError("Naive datetime; use datetime.now(UTC)")
            value = value.astimezone(UTC).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=UTC) if value is not None else None


class Base(DeclarativeBase):
    # Passed via an explicit registry: Flask-SQLAlchemy 3.1 rejects a
    # type_annotation_map set directly on the base with SQLAlchemy 2.1.
    registry = registry(
        type_annotation_map={datetime: UTCDateTime},
        # Named constraints, so Alembic can alter SQLite tables later.
        metadata=MetaData(
            naming_convention={
                "ix": "ix_%(column_0_label)s",
                "uq": "uq_%(table_name)s_%(column_0_name)s",
                "ck": "ck_%(table_name)s_%(constraint_name)s",
                "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
                "pk": "pk_%(table_name)s",
            }
        ),
    )


db = SQLAlchemy(model_class=Base)
# render_as_batch: SQLite can't ALTER most things, so Alembic rebuilds tables instead.
migrate = Migrate(render_as_batch=True)
csrf = CSRFProtect()
