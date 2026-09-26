"""
Forge Templates platform — multi-tenant Flask app.

Local dev:
    pip install -r requirements.txt
    python app.py
Then open http://localhost:5050

Production: see README "Deployment". Set DATABASE_URL to a postgres:// URL,
run behind gunicorn, and run `alembic upgrade head` instead of relying on
the auto-create-tables fallback.
"""
import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

from config import Config
from extensions import limiter
import db as db_module
from errors import register_error_handlers, configure_logging
from routes import (
    auth_routes, company_routes, leads_routes, users_routes, public_routes,
    customers_routes, products_routes, appointments_routes, analytics_routes, settings_routes
)

DASHBOARD_DIR = os.path.join(BASE_DIR, 'static', 'dashboard')
PUBLIC_DIR = os.path.join(BASE_DIR, 'static', 'public')
STOREFRONT_DIR = os.path.join(BASE_DIR, '..', 'storefront')
PRODUCT_DEMO_DIR = os.path.join(BASE_DIR, '..', 'products', 'promax-business')

app = Flask(__name__)
app.config.from_object(Config)

configure_logging(app)
register_error_handlers(app)

# Public, unauthenticated endpoints may be called from a business's own
# separately-hosted site — open CORS there. Everything else is same-origin,
# cookie-authenticated, and stays locked down.
CORS(app, resources={r"/api/public/*": {"origins": "*"}}, supports_credentials=False)

limiter.init_app(app)
app.config['RATELIMIT_STORAGE_URI'] = Config.RATE_LIMIT_STORAGE_URI
limiter.default_limits = [Config.RATE_LIMIT_DEFAULT]

db_module.init_app(app)

for bp in (auth_routes.bp, company_routes.bp, leads_routes.bp, users_routes.bp, public_routes.bp,
           customers_routes.bp, products_routes.bp, appointments_routes.bp, analytics_routes.bp,
           settings_routes.bp):
    app.register_blueprint(bp)


@app.route('/healthz')
def healthz():
    return {'status': 'ok'}


# --- Storefront (public homepage — sells the template) ---
@app.route('/')
def storefront_home():
    return send_from_directory(STOREFRONT_DIR, 'index.html')


@app.route('/assets/<path:filename>')
def storefront_assets(filename):
    return send_from_directory(STOREFRONT_DIR, filename)


# --- Live product demo, linked from the storefront ---
@app.route('/demo/')
@app.route('/demo/<path:filename>')
def product_demo(filename='index.html'):
    return send_from_directory(PRODUCT_DEMO_DIR, filename)


# --- Dashboard (authenticated app shell) ---
@app.route('/login')
@app.route('/register')
@app.route('/dashboard')
@app.route('/dashboard/<path:_subpath>')
def dashboard_shell(_subpath=None):
    return send_from_directory(DASHBOARD_DIR, 'index.html')


@app.route('/dashboard/assets/<path:filename>')
def dashboard_assets(filename):
    return send_from_directory(DASHBOARD_DIR, filename)


# --- Public per-company marketing site ---
@app.route('/site/<slug>')
def public_site(slug):
    return send_from_directory(PUBLIC_DIR, 'site.html')


@app.route('/site/assets/<path:filename>')
def public_assets(filename):
    return send_from_directory(PUBLIC_DIR, filename)


if __name__ == '__main__':
    app.run(debug=not Config.IS_PRODUCTION, port=int(os.getenv('PORT', 5050)))
