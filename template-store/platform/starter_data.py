"""
Starter data seeded into every newly registered company (any pricing tier —
there's no functional difference between plans in the platform itself, they're
a storefront/billing distinction). Unlike seed.py's demo companies, this is
not gated behind ALLOW_SEED: it's normal onboarding content for real
customers, the same way a fresh Notion workspace or Trello board ships with
example cards. Every record is clearly labeled as an example and is exactly
as replaceable/editable/deletable as anything a business creates themselves —
same tables, same CRUD endpoints, no special-casing.

Deliberately generic (not "hair salon" or "moving company" specific) since
registration doesn't ask what kind of business this is — the goal is to show
the shape of the data (a lead pipeline, a customer record, a service catalog,
a scheduled + a completed appointment) so a new owner immediately understands
how to replace it with their own.
"""
from datetime import datetime, timedelta, timezone
from extensions import db
from models import Lead, Customer, Product, Appointment


def seed_starter_data(company_id):
    now = datetime.now(timezone.utc)

    leads = [
        Lead(company_id=company_id, name='Alex Morgan', email='alex.morgan@example.com', phone='555-0100',
             message="Hi! I found your site and I'm interested in learning more about your services. "
                     "Could you send over some pricing info?",
             status='new', source='website', created_at=now - timedelta(hours=6), updated_at=now - timedelta(hours=6)),
        Lead(company_id=company_id, name='Jamie Reyes', email='jamie.reyes@example.com', phone='555-0101',
             message='Do you have any availability this week? Would love to get started.',
             status='contacted', source='website', created_at=now - timedelta(days=2), updated_at=now - timedelta(days=1)),
        Lead(company_id=company_id, name='Taylor Kim', email='taylor.kim@example.com', phone='',
             message="Thanks for the quote — we're ready to move forward!",
             status='won', source='website', created_at=now - timedelta(days=6), updated_at=now - timedelta(days=5)),
    ]
    db.session.add_all(leads)

    customers = [
        Customer(company_id=company_id, name='Morgan Lee (example)', email='morgan.lee@example.com', phone='555-0200',
                  address='', notes='This is an example customer record — edit or delete it. Real customers will '
                                     'show up here as leads convert, or you can add them directly.',
                  tags='example', status='active'),
        Customer(company_id=company_id, name='Casey Diaz (example)', email='casey.diaz@example.com', phone='555-0201',
                  address='', notes='A second example record — customize freely.', tags='example', status='active'),
    ]
    db.session.add_all(customers)
    db.session.flush()  # assign customer ids before linking appointments

    products = [
        Product(company_id=company_id, name='Example Service — Starter',
                 description='Replace this with your own service or product: set a real name, price and description.',
                 price=99.00, sku='EXAMPLE-1', category='General', status='active'),
        Product(company_id=company_id, name='Example Service — Standard',
                 description='A second example, useful for showing tiered pricing to customers.',
                 price=199.00, sku='EXAMPLE-2', category='General', status='active'),
        Product(company_id=company_id, name='Example Service — Premium',
                 description='A third example. Delete any of these you don’t need, or add more.',
                 price=349.00, sku='EXAMPLE-3', category='General', status='draft'),
    ]
    db.session.add_all(products)

    appointments = [
        Appointment(company_id=company_id, customer_id=customers[0].id,
                     title='Example Appointment — Consultation', scheduled_at=now + timedelta(days=2, hours=1),
                     duration_minutes=45, status='scheduled',
                     notes='Example upcoming appointment, linked to the example customer above.'),
        Appointment(company_id=company_id, customer_id=customers[1].id,
                     title='Example Appointment — Completed Job', scheduled_at=now - timedelta(days=3),
                     duration_minutes=60, status='completed',
                     notes='Example of a past, completed appointment.'),
    ]
    db.session.add_all(appointments)
