"""Session-based auth, password hashing, and per-request authorization helpers.

Authorization model:
  - role 'owner'  / 'staff' -> permanently bound to one company (session['company_id']).
  - role 'platform_admin'   -> not bound to a company; must explicitly switch into one
                                (session['active_company_id']) before touching company data.
  get_active_company_id() is the single choke point every company-scoped route must call —
  it is never taken from request args/body, so a client can't spoof another company's id.

Session cookies (not JWT) are used deliberately: the dashboard and API are same-origin,
so a signed httponly cookie gives CSRF-resistant (SameSite=Lax), XSS-resistant (httponly)
auth without the added complexity of token refresh/storage. See README "Auth model".
"""
from functools import wraps
from flask import session, g, request
from werkzeug.security import generate_password_hash, check_password_hash
from errors import AuthError, ForbiddenError, ValidationError, TrialExpiredError

SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')

ROLES = ('owner', 'staff', 'platform_admin')


def hash_password(password):
    return generate_password_hash(password)


def verify_password(password, password_hash):
    return check_password_hash(password_hash, password)


def login_user(user):
    session.clear()
    session['user_id'] = user.id
    session['role'] = user.role
    session['company_id'] = user.company_id
    if user.role == 'platform_admin':
        session['active_company_id'] = None


def logout_user():
    session.clear()


def current_user():
    if 'user' in g:
        return g.user
    from models import User
    user_id = session.get('user_id')
    if not user_id:
        g.user = None
        return None
    user = User.query.filter_by(id=user_id, is_active=True, deleted_at=None).first()
    g.user = user
    return user


def get_active_company_id():
    """The single source of truth for 'which company does this request act on'."""
    user = current_user()
    if not user:
        return None
    if user.role == 'platform_admin':
        return session.get('active_company_id')
    return user.company_id


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            raise AuthError('Authentication required.')
        return view(*args, **kwargs)
    return wrapped


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                raise AuthError('Authentication required.')
            if user.role not in roles:
                raise ForbiddenError('You do not have permission to do that.')
            return view(*args, **kwargs)
        return wrapped
    return decorator


def company_scope_required(view):
    """For routes that read/write company-scoped data (leads, customers, etc.).

    Also enforces the free-trial write gate: once a 'trial' company's
    trial_ends_at has passed, GET requests still work (nobody loses access to
    data they already entered), but any write (POST/PATCH/DELETE) is blocked
    with 402 TRIAL_EXPIRED until the company is upgraded to 'active'.
    Platform admins are exempt — they need write access to manage/upgrade a
    company regardless of its trial state.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        company_id = get_active_company_id()
        if not company_id:
            raise ValidationError('Select a company first.')
        g.company_id = company_id

        if user.role != 'platform_admin' and request.method not in SAFE_METHODS:
            from models import Company
            company = Company.query.get(company_id)
            if company and company.is_trial_expired:
                raise TrialExpiredError(
                    'Your free trial has ended. Upgrade to keep adding and editing data — your existing data is safe and still viewable.'
                )

        return view(*args, **kwargs)
    return wrapped
