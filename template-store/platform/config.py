import os
import secrets

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_SECRET_PATH = os.path.join(BASE_DIR, '.secret_key')


def _load_or_create_secret():
    env_secret = os.getenv('SECRET_KEY', '').strip()
    if env_secret:
        return env_secret
    if os.path.exists(_SECRET_PATH):
        with open(_SECRET_PATH, 'r') as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(_SECRET_PATH, 'w') as f:
        f.write(key)
    return key


def _database_url():
    """
    DATABASE_URL drives everything: unset -> local SQLite file (zero-config dev).
    Set it to a postgres:// / postgresql:// URL in production (Render, Railway,
    DigitalOcean App Platform, etc. all inject this automatically or via one env var).
    """
    url = os.getenv('DATABASE_URL', '').strip()
    if not url:
        return 'sqlite:///' + os.path.join(BASE_DIR, 'platform.db')
    # Some hosts (Render, Heroku-style) still hand out the legacy "postgres://"
    # scheme, which SQLAlchemy 1.4+/2.x no longer accepts.
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url


class Config:
    ENV = os.getenv('FLASK_ENV', 'development')
    IS_PRODUCTION = ENV == 'production'

    SECRET_KEY = _load_or_create_secret()
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = IS_PRODUCTION

    # Duplicate public lead submissions from the same company+email+message
    # within this window are treated as a re-submit, not a new lead.
    DUPLICATE_LEAD_WINDOW_SECONDS = int(os.getenv('DUPLICATE_LEAD_WINDOW_SECONDS', '300'))

    # New registrations start on a free trial this many days long. See
    # models.Company.is_trial_expired / auth.company_scope_required.
    TRIAL_DAYS = int(os.getenv('TRIAL_DAYS', '14'))

    DEFAULT_PAGE_SIZE = 25
    MAX_PAGE_SIZE = 100

    RATE_LIMIT_STORAGE_URI = os.getenv('RATE_LIMIT_STORAGE_URI', 'memory://')
    RATE_LIMIT_DEFAULT = os.getenv('RATE_LIMIT_DEFAULT', '200 per minute')
    RATE_LIMIT_AUTH = os.getenv('RATE_LIMIT_AUTH', '10 per minute')

    LOG_DIR = os.path.join(BASE_DIR, 'logs')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

    ALLOW_SEED = os.getenv('ALLOW_SEED', '' if IS_PRODUCTION else '1') == '1'
