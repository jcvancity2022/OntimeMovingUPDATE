"""Shared extension instances, created here (not in app.py) so route/model
modules can import them without circular imports."""
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
limiter = Limiter(key_func=get_remote_address)
