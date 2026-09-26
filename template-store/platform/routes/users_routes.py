import secrets
from flask import Blueprint, request, jsonify, g
from extensions import db
from models import User
from auth import login_required, role_required, company_scope_required, hash_password, current_user
from utils import is_valid_email, require_fields
from errors import ValidationError, ConflictError, NotFoundError

bp = Blueprint('users', __name__, url_prefix='/api/users')


@bp.route('', methods=['GET'])
@login_required
@company_scope_required
def list_users():
    users = User.query.filter_by(company_id=g.company_id, deleted_at=None).order_by(User.role, User.name).all()
    return jsonify([u.to_public_dict() for u in users])


@bp.route('', methods=['POST'])
@login_required
@role_required('owner', 'platform_admin')
@company_scope_required
def invite_user():
    data = request.get_json(silent=True) or {}
    require_fields(data, 'name', 'email')
    name = data['name'].strip()
    email = data['email'].strip().lower()
    role = data.get('role', 'staff')

    if not is_valid_email(email):
        raise ValidationError('A valid email address is required.')
    if role not in ('owner', 'staff'):
        raise ValidationError("Role must be 'owner' or 'staff'.")
    if User.query.filter_by(email=email).first():
        raise ConflictError('A user with that email already exists.')

    temp_password = secrets.token_urlsafe(9)
    user = User(company_id=g.company_id, name=name, email=email,
                password_hash=hash_password(temp_password), role=role)
    db.session.add(user)
    db.session.commit()

    result = user.to_public_dict()
    # Starter kit has no email delivery configured yet — surface the temp
    # password once so the owner can hand it to the new teammate directly.
    result['temp_password'] = temp_password
    return jsonify(result), 201


def _get_owned_user(user_id):
    user = User.query.filter_by(id=user_id, company_id=g.company_id, deleted_at=None).first()
    if not user:
        raise NotFoundError('User not found.')
    return user


@bp.route('/<int:user_id>', methods=['PATCH'])
@login_required
@role_required('owner', 'platform_admin')
@company_scope_required
def update_user(user_id):
    user = _get_owned_user(user_id)
    data = request.get_json(silent=True) or {}
    role = data.get('role', user.role)
    is_active = data.get('is_active', user.is_active)

    if role not in ('owner', 'staff'):
        raise ValidationError("Role must be 'owner' or 'staff'.")

    if user.role == 'owner' and (role != 'owner' or not is_active):
        owner_count = User.query.filter_by(company_id=g.company_id, role='owner', is_active=True, deleted_at=None).count()
        if owner_count <= 1:
            raise ValidationError('A company must keep at least one active owner.')

    user.role = role
    user.is_active = bool(is_active)
    db.session.commit()
    return jsonify(user.to_public_dict())


@bp.route('/<int:user_id>', methods=['DELETE'])
@login_required
@role_required('owner', 'platform_admin')
@company_scope_required
def remove_user(user_id):
    if user_id == current_user().id:
        raise ValidationError('You cannot remove your own account.')

    user = _get_owned_user(user_id)
    if user.role == 'owner':
        raise ValidationError('Owners cannot be removed. Change their role first.')

    user.soft_delete()
    user.is_active = False
    db.session.commit()
    return jsonify({'status': 'deleted'})
