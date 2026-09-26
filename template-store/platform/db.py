"""
Table creation. `init_app` covers two cases:

1. Fresh install, no Alembic run yet: `db.create_all()` builds every table
   from the current models — zero-config, works the moment you `python app.py`.
2. Ongoing project with schema history: run `alembic upgrade head` instead
   (see README "Database migrations"). `create_all()` is a no-op against
   tables that already exist, so it's always safe to leave enabled.
"""
from extensions import db
import models  # noqa: F401 — import registers all model classes on db.metadata


def init_app(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()
