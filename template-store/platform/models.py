"""
SQLAlchemy models — the single schema definition used against both SQLite
(local dev, zero config) and PostgreSQL (production, via DATABASE_URL).

Multi-tenancy: every business-data table has a `company_id` column and every
query that touches one MUST filter on it. See auth.get_active_company_id()
and the `@company_scope_required` decorator, which is the only place a
request's company_id is derived from — never from client input.

Soft deletes: leads/customers/products/appointments/users are never hard
DELETEd through the API. `deleted_at` is set instead, and `active()` query
helpers filter it out. This preserves history or transaction integrity for
records other tables may already reference (e.g. an appointment linked to a
"deleted" customer).
"""
from datetime import datetime, timezone
from extensions import db


def utcnow():
    return datetime.now(timezone.utc)


def as_aware_utc(dt):
    """SQLite doesn't actually store timezone info — even columns declared
    DateTime(timezone=True) come back offset-naive on read, even though every
    value was written via utcnow() as UTC. Reattach UTC before comparing
    against a fresh aware datetime, or `aware - naive` raises TypeError.
    (PostgreSQL preserves the offset natively, so this is a no-op there.)"""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class SoftDeleteMixin:
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True)

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def soft_delete(self):
        self.deleted_at = utcnow()


class Company(TimestampMixin, db.Model):
    __tablename__ = 'companies'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), nullable=False, unique=True, index=True)
    theme = db.Column(db.String(30), nullable=False, default='default')
    brand_name = db.Column(db.String(200), nullable=False)
    brand_accent = db.Column(db.String(50), nullable=False, default='')
    content_json = db.Column(db.Text, nullable=False)

    timezone = db.Column(db.String(60), nullable=False, default='UTC')
    currency = db.Column(db.String(10), nullable=False, default='USD')
    notification_email = db.Column(db.String(255), nullable=True)

    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # 'trial' or 'active'. New registrations start on 'trial' with a 14-day
    # trial_ends_at; existing companies (demo + anything created before this
    # feature shipped) are backfilled to 'active' by the migration so nobody
    # already using the platform is retroactively locked out. There's no real
    # payment webhook behind 'active' yet — see routes/company_routes.py
    # upgrade_company() and README "Free trial" for what's stubbed vs. real.
    plan = db.Column(db.String(20), nullable=False, default='active')
    trial_ends_at = db.Column(db.DateTime(timezone=True), nullable=True)

    users = db.relationship('User', backref='company', lazy='dynamic', cascade='all, delete-orphan')
    leads = db.relationship('Lead', backref='company', lazy='dynamic', cascade='all, delete-orphan')
    customers = db.relationship('Customer', backref='company', lazy='dynamic', cascade='all, delete-orphan')
    products = db.relationship('Product', backref='company', lazy='dynamic', cascade='all, delete-orphan')
    appointments = db.relationship('Appointment', backref='company', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def trial_days_remaining(self):
        if self.plan != 'trial' or not self.trial_ends_at:
            return None
        remaining = (as_aware_utc(self.trial_ends_at) - utcnow()).total_seconds() / 86400
        return max(0, int(remaining + 0.999))  # round up so "0.2 days left" reads as 1, not 0

    @property
    def is_trial_expired(self):
        return self.plan == 'trial' and bool(self.trial_ends_at) and utcnow() >= as_aware_utc(self.trial_ends_at)

    def to_public_dict(self):
        return {'id': self.id, 'name': self.name, 'slug': self.slug}


class User(TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id', ondelete='CASCADE'), nullable=True, index=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # owner | staff | platform_admin
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        db.CheckConstraint("role IN ('owner','staff','platform_admin')", name='ck_users_role'),
    )

    def to_public_dict(self):
        return {
            'id': self.id, 'name': self.name, 'email': self.email, 'role': self.role,
            'is_active': self.is_active, 'created_at': iso(self.created_at),
            'last_login_at': iso(self.last_login_at)
        }


class Lead(TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = 'leads'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    phone = db.Column(db.String(50), nullable=False, default='')
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='new')
    source = db.Column(db.String(50), nullable=False, default='website')
    notes = db.Column(db.Text, nullable=False, default='')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    __table_args__ = (
        db.CheckConstraint("status IN ('new','contacted','won','lost')", name='ck_leads_status'),
        db.Index('idx_leads_company_created', 'company_id', 'created_at'),
    )

    def to_dict(self):
        return {
            'id': self.id, 'company_id': self.company_id, 'name': self.name, 'email': self.email,
            'phone': self.phone, 'message': self.message, 'status': self.status, 'source': self.source,
            'notes': self.notes, 'created_at': iso(self.created_at), 'updated_at': iso(self.updated_at)
        }


class Customer(TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    phone = db.Column(db.String(50), nullable=False, default='')
    address = db.Column(db.String(400), nullable=False, default='')
    notes = db.Column(db.Text, nullable=False, default='')
    tags = db.Column(db.String(400), nullable=False, default='')  # comma-separated
    status = db.Column(db.String(20), nullable=False, default='active')

    appointments = db.relationship('Appointment', backref='customer', lazy='dynamic')

    __table_args__ = (
        db.CheckConstraint("status IN ('active','inactive')", name='ck_customers_status'),
        db.Index('idx_customers_company_created', 'company_id', 'created_at'),
    )

    def to_dict(self):
        return {
            'id': self.id, 'company_id': self.company_id, 'name': self.name, 'email': self.email,
            'phone': self.phone, 'address': self.address, 'notes': self.notes,
            'tags': [t for t in self.tags.split(',') if t] if self.tags else [],
            'status': self.status, 'created_at': iso(self.created_at), 'updated_at': iso(self.updated_at)
        }


class Product(TimestampMixin, SoftDeleteMixin, db.Model):
    """Generic 'products / properties / listings' catalog — the label shown
    in the dashboard is configurable per company (see Company.content_json),
    but the underlying model is intentionally generic so it fits a moving
    company's service tiers, a real-estate company's listings, or a salon's
    service menu equally well."""
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False, default='')
    price = db.Column(db.Numeric(12, 2), nullable=True)
    sku = db.Column(db.String(100), nullable=True)
    category = db.Column(db.String(100), nullable=False, default='')
    status = db.Column(db.String(20), nullable=False, default='active')
    image_url = db.Column(db.String(500), nullable=False, default='')

    __table_args__ = (
        db.CheckConstraint("status IN ('active','inactive','draft')", name='ck_products_status'),
        db.Index('idx_products_company_created', 'company_id', 'created_at'),
    )

    def to_dict(self):
        return {
            'id': self.id, 'company_id': self.company_id, 'name': self.name, 'description': self.description,
            'price': float(self.price) if self.price is not None else None, 'sku': self.sku,
            'category': self.category, 'status': self.status, 'image_url': self.image_url,
            'created_at': iso(self.created_at), 'updated_at': iso(self.updated_at)
        }


class Appointment(TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = 'appointments'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id', ondelete='SET NULL'), nullable=True, index=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id', ondelete='SET NULL'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    scheduled_at = db.Column(db.DateTime(timezone=True), nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False, default=60)
    status = db.Column(db.String(20), nullable=False, default='scheduled')
    notes = db.Column(db.Text, nullable=False, default='')

    __table_args__ = (
        db.CheckConstraint("status IN ('scheduled','completed','cancelled','no_show')", name='ck_appt_status'),
        db.Index('idx_appt_company_scheduled', 'company_id', 'scheduled_at'),
    )

    def to_dict(self):
        return {
            'id': self.id, 'company_id': self.company_id, 'customer_id': self.customer_id,
            'lead_id': self.lead_id, 'title': self.title, 'scheduled_at': iso(self.scheduled_at),
            'duration_minutes': self.duration_minutes, 'status': self.status, 'notes': self.notes,
            'customer_name': self.customer.name if self.customer_id and self.customer else None,
            'created_at': iso(self.created_at), 'updated_at': iso(self.updated_at)
        }


def iso(dt):
    return dt.isoformat() if dt else None
