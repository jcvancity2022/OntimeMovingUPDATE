from flask import Blueprint, request, jsonify
from extensions import db, limiter
from models import Company, User
from auth import hash_password, verify_password, login_user, logout_user, current_user, login_required
from utils import is_valid_email, unique_slug, default_content, content_to_json, require_fields
from errors import ValidationError, ConflictError, AuthError
from config import Config
from starter_data import seed_starter_data
from datetime import datetime, timedelta, timezone

bp = Blueprint('auth', __name__, url_prefix='/api/auth')


def _company_summary(company):
    return {
        'id': company.id, 'name': company.name, 'slug': company.slug,
        'plan': company.plan, 'trial_ends_at': company.trial_ends_at.isoformat() if company.trial_ends_at else None,
        'trial_days_remaining': company.trial_days_remaining, 'is_trial_expired': company.is_trial_expired
    }


@bp.route('/register', methods=['POST'])
@limiter.limit(lambda: Config.RATE_LIMIT_AUTH)
def register():
    data = request.get_json(silent=True) or {}
    require_fields(data, 'company_name', 'owner_name', 'email', 'password')

    company_name = data['company_name'].strip()
    owner_name = data['owner_name'].strip()
    email = data['email'].strip().lower()
    password = data['password']

    if not is_valid_email(email):
        raise ValidationError('A valid email address is required.')
    if len(password) < 8:
        raise ValidationError('Password must be at least 8 characters.')
    if User.query.filter_by(email=email).first():
        raise ConflictError('An account with that email already exists.')

    company = Company(
        name=company_name, slug=unique_slug(company_name), theme='default',
        brand_name=company_name, brand_accent='', content_json=content_to_json(default_content(company_name)),
        plan='trial', trial_ends_at=datetime.now(timezone.utc) + timedelta(days=Config.TRIAL_DAYS)
    )
    db.session.add(company)
    db.session.flush()  # assigns company.id within the same transaction

    user = User(
        company_id=company.id, name=owner_name, email=email,
        password_hash=hash_password(password), role='owner'
    )
    db.session.add(user)
    db.session.flush()

    # Every new company (any pricing tier) starts with a small, clearly-labeled
    # example dataset — a lead pipeline, a customer, a service catalog, and
    # both an upcoming and a completed appointment — instead of an empty
    # dashboard. It's ordinary, editable/deletable data, not demo-only content.
    seed_starter_data(company.id)
    db.session.commit()

    login_user(user)
    return jsonify({
        'user': {'id': user.id, 'name': user.name, 'email': user.email, 'role': user.role},
        'company': _company_summary(company)
    }), 201


@bp.route('/login', methods=['POST'])
@limiter.limit(lambda: Config.RATE_LIMIT_AUTH)
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    user = User.query.filter_by(email=email, is_active=True, deleted_at=None).first()
    if not user or not verify_password(password, user.password_hash):
        raise AuthError('Invalid email or password.')

    user.last_login_at = datetime.now(timezone.utc)
    db.session.commit()
    login_user(user)
    return jsonify({'status': 'ok'})


@bp.route('/logout', methods=['POST'])
def logout():
    logout_user()
    return jsonify({'status': 'ok'})


@bp.route('/me', methods=['GET'])
@login_required
def me():
    user = current_user()
    company = None
    if user.company_id:
        c = Company.query.get(user.company_id)
        company = _company_summary(c) if c else None
    return jsonify({
        'user': {'id': user.id, 'name': user.name, 'email': user.email, 'role': user.role},
        'company': company
    })
