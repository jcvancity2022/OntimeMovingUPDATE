from flask import Blueprint, request, jsonify, g
from extensions import db
from models import Customer
from auth import login_required, role_required, company_scope_required
from utils import is_valid_email, require_fields
from pagination import paginate
from errors import NotFoundError, ValidationError, ConflictError

bp = Blueprint('customers', __name__, url_prefix='/api/customers')

SORT_COLUMNS = {'created_at': Customer.created_at, 'name': Customer.name, 'status': Customer.status}
STATUSES = ('active', 'inactive')


def _filtered_query():
    q = Customer.query.filter(Customer.company_id == g.company_id, Customer.deleted_at.is_(None))

    search = (request.args.get('q') or '').strip()
    if search:
        like = f'%{search}%'
        q = q.filter(db.or_(Customer.name.ilike(like), Customer.email.ilike(like), Customer.phone.ilike(like)))

    status = request.args.get('status')
    if status and status in STATUSES:
        q = q.filter(Customer.status == status)

    sort = request.args.get('sort', '-created_at')
    column = SORT_COLUMNS.get(sort.lstrip('-'), Customer.created_at)
    q = q.order_by(column.desc() if sort.startswith('-') or sort == 'created_at' else column.asc())
    return q


@bp.route('', methods=['GET'])
@login_required
@company_scope_required
def list_customers():
    return jsonify(paginate(_filtered_query(), lambda c: c.to_dict()))


@bp.route('', methods=['POST'])
@login_required
@company_scope_required
def add_customer():
    data = request.get_json(silent=True) or {}
    require_fields(data, 'name', 'email')
    email = data['email'].strip().lower()
    if not is_valid_email(email):
        raise ValidationError('A valid email address is required.')

    existing = Customer.query.filter_by(company_id=g.company_id, email=email, deleted_at=None).first()
    if existing:
        raise ConflictError('A customer with that email already exists.')

    customer = Customer(
        company_id=g.company_id, name=data['name'].strip(), email=email,
        phone=(data.get('phone') or '').strip(), address=(data.get('address') or '').strip(),
        notes=(data.get('notes') or '').strip(),
        tags=','.join(t.strip() for t in data.get('tags', []) if t.strip()) if isinstance(data.get('tags'), list) else ''
    )
    db.session.add(customer)
    db.session.commit()
    return jsonify(customer.to_dict()), 201


def _get_owned_customer(customer_id):
    customer = Customer.query.filter_by(id=customer_id, company_id=g.company_id, deleted_at=None).first()
    if not customer:
        raise NotFoundError('Customer not found.')
    return customer


@bp.route('/<int:customer_id>', methods=['GET'])
@login_required
@company_scope_required
def get_customer(customer_id):
    return jsonify(_get_owned_customer(customer_id).to_dict())


@bp.route('/<int:customer_id>', methods=['PATCH'])
@login_required
@company_scope_required
def update_customer(customer_id):
    customer = _get_owned_customer(customer_id)
    data = request.get_json(silent=True) or {}

    if 'name' in data and str(data['name']).strip():
        customer.name = data['name'].strip()
    if 'email' in data:
        email = data['email'].strip().lower()
        if not is_valid_email(email):
            raise ValidationError('A valid email address is required.')
        customer.email = email
    if 'phone' in data:
        customer.phone = data['phone']
    if 'address' in data:
        customer.address = data['address']
    if 'notes' in data:
        customer.notes = data['notes']
    if 'status' in data:
        if data['status'] not in STATUSES:
            raise ValidationError(f'Status must be one of {STATUSES}.')
        customer.status = data['status']
    if isinstance(data.get('tags'), list):
        customer.tags = ','.join(t.strip() for t in data['tags'] if t.strip())

    db.session.commit()
    return jsonify(customer.to_dict())


@bp.route('/<int:customer_id>', methods=['DELETE'])
@login_required
@role_required('owner', 'platform_admin')
@company_scope_required
def delete_customer(customer_id):
    customer = _get_owned_customer(customer_id)
    customer.soft_delete()
    db.session.commit()
    return jsonify({'status': 'deleted'})
