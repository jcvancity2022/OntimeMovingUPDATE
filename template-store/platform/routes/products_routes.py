from flask import Blueprint, request, jsonify, g
from extensions import db
from models import Product
from auth import login_required, role_required, company_scope_required
from utils import require_fields
from pagination import paginate
from errors import NotFoundError, ValidationError, ConflictError

bp = Blueprint('products', __name__, url_prefix='/api/products')

SORT_COLUMNS = {'created_at': Product.created_at, 'name': Product.name, 'price': Product.price}
STATUSES = ('active', 'inactive', 'draft')


def _filtered_query():
    q = Product.query.filter(Product.company_id == g.company_id, Product.deleted_at.is_(None))

    search = (request.args.get('q') or '').strip()
    if search:
        like = f'%{search}%'
        q = q.filter(db.or_(Product.name.ilike(like), Product.description.ilike(like), Product.sku.ilike(like)))

    status = request.args.get('status')
    if status and status in STATUSES:
        q = q.filter(Product.status == status)

    category = (request.args.get('category') or '').strip()
    if category:
        q = q.filter(Product.category == category)

    sort = request.args.get('sort', '-created_at')
    column = SORT_COLUMNS.get(sort.lstrip('-'), Product.created_at)
    q = q.order_by(column.desc() if sort.startswith('-') or sort == 'created_at' else column.asc())
    return q


@bp.route('', methods=['GET'])
@login_required
@company_scope_required
def list_products():
    return jsonify(paginate(_filtered_query(), lambda p: p.to_dict()))


@bp.route('', methods=['POST'])
@login_required
@company_scope_required
def add_product():
    data = request.get_json(silent=True) or {}
    require_fields(data, 'name')

    sku = (data.get('sku') or '').strip() or None
    if sku and Product.query.filter_by(company_id=g.company_id, sku=sku, deleted_at=None).first():
        raise ConflictError('A product with that SKU already exists.')

    price = data.get('price')
    if price is not None:
        try:
            price = float(price)
        except (TypeError, ValueError):
            raise ValidationError('Price must be a number.')

    product = Product(
        company_id=g.company_id, name=data['name'].strip(), description=(data.get('description') or '').strip(),
        price=price, sku=sku, category=(data.get('category') or '').strip(),
        status=data.get('status', 'active'), image_url=(data.get('image_url') or '').strip()
    )
    if product.status not in STATUSES:
        raise ValidationError(f'Status must be one of {STATUSES}.')

    db.session.add(product)
    db.session.commit()
    return jsonify(product.to_dict()), 201


def _get_owned_product(product_id):
    product = Product.query.filter_by(id=product_id, company_id=g.company_id, deleted_at=None).first()
    if not product:
        raise NotFoundError('Product not found.')
    return product


@bp.route('/<int:product_id>', methods=['GET'])
@login_required
@company_scope_required
def get_product(product_id):
    return jsonify(_get_owned_product(product_id).to_dict())


@bp.route('/<int:product_id>', methods=['PATCH'])
@login_required
@company_scope_required
def update_product(product_id):
    product = _get_owned_product(product_id)
    data = request.get_json(silent=True) or {}

    if 'name' in data and str(data['name']).strip():
        product.name = data['name'].strip()
    if 'description' in data:
        product.description = data['description']
    if 'price' in data:
        try:
            product.price = float(data['price']) if data['price'] is not None else None
        except (TypeError, ValueError):
            raise ValidationError('Price must be a number.')
    if 'sku' in data:
        sku = (data['sku'] or '').strip() or None
        if sku and sku != product.sku:
            clash = Product.query.filter_by(company_id=g.company_id, sku=sku, deleted_at=None).first()
            if clash and clash.id != product.id:
                raise ConflictError('A product with that SKU already exists.')
        product.sku = sku
    if 'category' in data:
        product.category = data['category']
    if 'image_url' in data:
        product.image_url = data['image_url']
    if 'status' in data:
        if data['status'] not in STATUSES:
            raise ValidationError(f'Status must be one of {STATUSES}.')
        product.status = data['status']

    db.session.commit()
    return jsonify(product.to_dict())


@bp.route('/<int:product_id>', methods=['DELETE'])
@login_required
@role_required('owner', 'platform_admin')
@company_scope_required
def delete_product(product_id):
    product = _get_owned_product(product_id)
    product.soft_delete()
    db.session.commit()
    return jsonify({'status': 'deleted'})
