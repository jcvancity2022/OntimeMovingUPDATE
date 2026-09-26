"""
Seeds demo companies spanning 6 different small-business verticals (salon,
contracting, cafe, moving, fitness studio, real estate) — each with owners,
staff, leads, customers, products/listings and appointments, so every
resource type and every dashboard view has something real to show. Safe to
re-run — skips companies that already exist (matched by slug), and never
touches real (non-demo) companies since it only ever matches on demo slugs.

This is demo data, not production data: it refuses to run when
FLASK_ENV=production unless you explicitly set ALLOW_SEED=1, so a real
deployment can never get seeded with fake companies by accident.

Run:
    python seed.py
"""
import sys
from datetime import datetime, timedelta, timezone
from app import app
from extensions import db
from models import Company, User, Lead, Customer, Product, Appointment
from auth import hash_password
from utils import slugify, default_content, content_to_json
from config import Config

if not Config.ALLOW_SEED:
    sys.exit('Refusing to seed: FLASK_ENV=production and ALLOW_SEED is not set. '
             'Seed data must never land in a real deployment — see README "Demo vs. production data".')

DEMO_PASSWORD = 'Demo1234!'

# Nova & Co. Salon and Summit Contracting are linked directly from the
# storefront catalog (storefront/index.html "Pro Max Studio" / "Pro Max
# Trade" cards) as live previews, so — unlike the other demo companies —
# their website copy is fully polished rather than left as generic
# default_content() placeholder text.
CONTENT_OVERRIDES = {
    'nova-co-salon': {
        'hero': {
            'badge': '✨ Trusted by 2,000+ clients',
            'title': 'Look and feel your best at Nova & Co. Salon',
            'subtitle': 'Full-service hair, color and styling in a warm, welcoming space. Book online in under a minute.',
            'primaryCta': 'Book an Appointment', 'secondaryCta': 'See Services'
        },
        'about': {
            'label': 'Our Story', 'title': 'A salon built around you',
            'text': "Nova & Co. has been the neighborhood's go-to for color, cuts and styling for over a decade. "
                    "Our stylists trained in the world's top studios, brought home to give you the personal, "
                    "unhurried experience you deserve.",
            'badgeValue': '98%', 'badgeLabel': 'Client satisfaction',
            'bullets': ['Eco-friendly, ammonia-free color', 'Complimentary consultation with every visit',
                        'Walk-ins welcome, appointments preferred']
        },
        'features': {
            'label': 'Why Choose Us', 'title': 'Where craft meets care', 'subtitle': "Here's what makes every visit feel different.",
            'items': [
                {'icon': '💇', 'title': 'Expert Stylists', 'text': 'Every stylist is trained and certified in the latest techniques.'},
                {'icon': '🌿', 'title': 'Clean Beauty', 'text': 'We use ammonia-free, cruelty-free products exclusively.'},
                {'icon': '📅', 'title': 'Easy Online Booking', 'text': 'Book, reschedule or cancel anytime from your phone.'}
            ]
        },
        'testimonials': {
            'label': 'Testimonials', 'title': 'What our clients say', 'subtitle': 'Real feedback from real clients.',
            'items': [{'quote': "Best color I've ever had. The whole team is so welcoming.", 'name': 'Jordan P.', 'role': 'Regular client'}]
        },
        'cta': {'title': 'Ready for your next appointment?',
                'text': 'Book online or call us — we always make room for regulars and first-timers alike.',
                'email': 'hello@novasalon.demo'},
        'footer': {'tagline': 'Nova & Co. Salon — where you always leave feeling like yourself, only better.',
                   'copyright': '© 2026 Nova & Co. Salon'}
    },
    'summit-contracting': {
        'hero': {
            'badge': '🔧 Licensed, bonded & insured',
            'title': 'Quality construction you can trust',
            'subtitle': 'Kitchen remodels, roofing, decks and more — Summit Contracting Group has served the region for over 15 years.',
            'primaryCta': 'Get a Free Quote', 'secondaryCta': 'See Our Work'
        },
        'about': {
            'label': 'Why Summit', 'title': 'Built on craftsmanship and honesty',
            'text': 'Summit Contracting Group was founded on one idea: do the job right, communicate clearly, and '
                    'never cut corners. Every project is backed by our workmanship guarantee.',
            'badgeValue': '15+', 'badgeLabel': 'Years in business',
            'bullets': ['Licensed, bonded and fully insured', 'Free on-site estimates', 'Workmanship guaranteed for 2 years']
        },
        'features': {
            'label': 'Why Choose Us', 'title': 'Straightforward, quality work', 'subtitle': 'No surprises, just solid craftsmanship.',
            'items': [
                {'icon': '🏗️', 'title': 'Full-Service Remodeling', 'text': 'From kitchens to decks, one team handles the whole project.'},
                {'icon': '📋', 'title': 'Transparent Quotes', 'text': 'No surprise costs — you approve the price before we start.'},
                {'icon': '🛡️', 'title': 'Workmanship Guarantee', 'text': 'Every job backed by a 2-year guarantee.'}
            ]
        },
        'testimonials': {
            'label': 'Testimonials', 'title': 'What our clients say', 'subtitle': 'Real feedback from real homeowners.',
            'items': [{'quote': 'On time, on budget, and the crew was fantastic to work with.', 'name': 'Casey K.', 'role': 'Homeowner'}]
        },
        'cta': {'title': 'Ready to start your project?',
                'text': "Get a free, no-obligation estimate — we'll walk the site and give you a clear number.",
                'email': 'hello@summitcontracting.demo'},
        'footer': {'tagline': 'Summit Contracting Group — quality construction, done right.',
                   'copyright': '© 2026 Summit Contracting Group'}
    }
}

DEMO_COMPANIES = [
    {
        'name': 'Nova & Co. Salon', 'brand_accent': '& Co.', 'theme': 'rose',
        'owner': {'name': 'Maria Chen', 'email': 'maria@novasalon.demo'},
        'staff': [{'name': 'Priya Patel', 'email': 'priya@novasalon.demo'}],
        'leads': [
            ('Sky Martinez', 'sky.m@example.com', '555-0105', "Any availability for a men's cut this week?", 'new', 0),
            ('Alex Rivera', 'alex.r@example.com', '555-0101', 'Looking to book a color appointment next week.', 'new', 1),
            ('Jamie Lee', 'jamie.lee@example.com', '555-0102', 'Do you take walk-ins on Saturdays?', 'contacted', 3),
            ('Taylor Brooks', 'taylor.b@example.com', '', 'Interested in your bridal package pricing.', 'won', 6),
            ('Morgan Diaz', 'morgan.d@example.com', '555-0104', 'Can I reschedule my appointment?', 'lost', 12),
        ],
        'customers': [
            ('Riley Summers', 'riley.s@example.com', '555-0201', '123 Main St', 'Prefers Saturday mornings', 'vip,color', 'active'),
            ('Casey Fox', 'casey.f@example.com', '555-0202', '456 Oak Ave', '', 'new', 'active'),
            ('Drew Bailey', 'drew.bailey@example.com', '555-0203', '321 Pine Rd', 'Moved out of area', '', 'inactive'),
        ],
        'products': [
            ('Signature Color', 'Full color service with gloss finish', 120.00, 'SVC-COLOR', 'Color', 'active'),
            ('Balayage', 'Hand-painted highlights', 180.00, 'SVC-BAL', 'Color', 'active'),
            ('Bridal Package', 'Trial + day-of styling', 350.00, 'SVC-BRIDAL', 'Events', 'draft'),
        ],
        'appointments': [
            ('Men\'s cut — Sky M.', 0, 30, 'scheduled'),
            ('Color touch-up', 2, 60, 'scheduled'),
            ('Balayage consult', -3, 45, 'completed'),
        ]
    },
    {
        'name': 'Summit Contracting', 'brand_accent': 'Group', 'theme': 'slate',
        'owner': {'name': 'Sam Osei', 'email': 'sam@summitcontracting.demo'},
        'staff': [{'name': 'Riley Nguyen', 'email': 'riley@summitcontracting.demo'}],
        'leads': [
            ('Casey Vance', 'casey.vance@example.com', '555-0206', 'Storm damage, need an emergency estimate.', 'new', 0),
            ('Jordan Pierce', 'jordan.p@example.com', '555-0201', 'Need a quote for a kitchen remodel.', 'new', 1),
            ('Casey Kim', 'casey.k@example.com', '555-0202', "Roof repair after last week's storm.", 'contacted', 2),
            ('Drew Adams', 'drew.a@example.com', '555-0203', 'Deck construction, roughly 400 sq ft.', 'won', 8),
        ],
        'customers': [
            ('Pat Nguyen', 'pat.n@example.com', '555-0301', '789 Elm St', 'Repeat client, referred 2 others', 'repeat', 'active'),
            ('Robin Shaw', 'robin.shaw@example.com', '555-0302', '15 Cedar Ct', 'Project on hold', '', 'inactive'),
        ],
        'products': [
            ('Kitchen Remodel — Standard', 'Cabinets, counters, flooring', 15000.00, 'JOB-KIT-STD', 'Remodel', 'active'),
            ('Roof Repair', 'Patch and shingle replacement', 2500.00, 'JOB-ROOF', 'Repair', 'active'),
            ('Deck Construction', '~400 sq ft pressure-treated deck', 8500.00, 'JOB-DECK', 'Outdoor', 'active'),
        ],
        'appointments': [
            ('Emergency roof estimate', 0, 45, 'scheduled'),
            ('Kitchen remodel site visit', 4, 90, 'scheduled'),
            ('Deck walkthrough', -5, 60, 'completed'),
        ]
    },
    {
        'name': 'Cafe Verde', 'brand_accent': '', 'theme': 'emerald',
        'owner': {'name': 'Elena Ruiz', 'email': 'elena@cafeverde.demo'},
        'staff': [{'name': 'Noah Kim', 'email': 'noah@cafeverde.demo'}],
        'leads': [
            ('Jesse Wong', 'jesse.w@example.com', '', 'Do you cater office events?', 'new', 0),
            ('Sam Patel', 'sam.p@example.com', '555-0302', 'Interested in a monthly coffee subscription.', 'contacted', 4),
            ('Rowan Diaz', 'rowan.d@example.com', '555-0303', 'Can I rent the back room for a birthday?', 'won', 6),
        ],
        'customers': [
            ('Logan Pierce', 'logan.p@example.com', '555-0401', '', 'Regular, oat milk latte every morning', 'regular', 'active'),
            ('Ari Sun', 'ari.sun@example.com', '', '', 'Subscribes to the monthly bean box', 'subscriber', 'active'),
        ],
        'products': [
            ('House Blend, 12oz', 'Our signature medium roast', 16.00, 'BEAN-HOUSE', 'Beans', 'active'),
            ('Cold Brew Concentrate', '32oz, makes 4 servings', 14.00, 'BEAN-COLDBREW', 'Beans', 'active'),
            ('Monthly Bean Subscription', 'One bag delivered monthly', 15.00, 'SUB-MONTHLY', 'Subscription', 'active'),
        ],
        'appointments': [
            ('Office catering drop-off', 3, 30, 'scheduled'),
            ('Birthday party — back room', -2, 120, 'completed'),
        ]
    },
    {
        'name': 'Coastal Moving Co.', 'brand_accent': 'Moving', 'theme': 'default',
        'owner': {'name': 'Jordan Blake', 'email': 'jordan@coastalmoving.demo'},
        'staff': [{'name': 'Casey Reyes', 'email': 'casey@coastalmoving.demo'}],
        'leads': [
            ('Morgan Ellis', 'morgan.e@example.com', '555-0401', 'Need a quote for a 2-bedroom apartment move next month.', 'new', 0),
            ('Avery Stone', 'avery.s@example.com', '555-0402', 'Do you offer packing services?', 'new', 1),
            ('Riley Chen', 'riley.c@example.com', '555-0403', 'Long distance move from Seattle to Portland.', 'contacted', 3),
            ('Jamie Cruz', 'jamie.cruz@example.com', '', 'Looking for a storage + moving bundle.', 'won', 7),
            ('Drew Park', 'drew.park@example.com', '555-0405', 'Move got cancelled, following up on a refund.', 'lost', 10),
        ],
        'customers': [
            ('Taylor Reed', 'taylor.reed@example.com', '555-0501', '12 Harbor Rd', 'Moved twice with us, very happy', 'repeat,vip', 'active'),
            ('Sam Ortiz', 'sam.ortiz@example.com', '555-0502', '88 Cedar Ln', '', '', 'active'),
            ('Chris Bell', 'chris.bell@example.com', '555-0503', '200 Birch St', 'Cancelled last booking', '', 'inactive'),
        ],
        'products': [
            ('Local Move — Studio/1BR', 'Full-service local move, up to 4 hours', 450.00, 'MOVE-LOCAL-1BR', 'Local', 'active'),
            ('Local Move — 2-3BR', 'Full-service local move, up to 7 hours', 850.00, 'MOVE-LOCAL-3BR', 'Local', 'active'),
            ('Long Distance Move', 'Cross-state moving, priced per shipment', 2200.00, 'MOVE-LONG', 'Long Distance', 'active'),
            ('Packing Service Add-on', 'Full pack/unpack service', 300.00, 'MOVE-PACK', 'Add-on', 'active'),
            ('Storage — Monthly', 'Climate-controlled storage unit', 120.00, 'STORAGE-MO', 'Storage', 'draft'),
        ],
        'appointments': [
            ('In-home moving estimate', 1, 45, 'scheduled'),
            ('2BR local move', 5, 240, 'scheduled'),
            ('Long distance pickup', -2, 180, 'completed'),
            ('Estimate — cancelled by customer', -5, 30, 'cancelled'),
        ]
    },
    {
        'name': 'Flow State Studio', 'brand_accent': 'Yoga & Fitness', 'theme': 'sunset',
        'owner': {'name': 'Nina Alvarez', 'email': 'nina@flowstatestudio.demo'},
        'staff': [{'name': 'Owen Blake', 'email': 'owen@flowstatestudio.demo'}],
        'leads': [
            ('Harper Kim', 'harper.k@example.com', '555-0601', 'Interested in a first-timer trial class.', 'new', 0),
            ('Reese Long', 'reese.l@example.com', '', 'Do you offer private sessions?', 'new', 1),
            ('Quinn Foster', 'quinn.f@example.com', '555-0603', 'Asking about monthly membership pricing.', 'contacted', 2),
            ('Skyler James', 'skyler.j@example.com', '555-0604', 'Wants to book a corporate wellness session.', 'won', 9),
        ],
        'customers': [
            ('Jordan Avery', 'jordan.avery@example.com', '555-0701', '5 Willow Ct', 'Attends 3x/week, loves hot yoga', 'vip,regular', 'active'),
            ('Casey Nolan', 'casey.nolan@example.com', '555-0702', '', 'Prefers morning classes', '', 'active'),
            ('Bailey Ross', 'bailey.ross@example.com', '555-0703', '', 'Paused membership', '', 'inactive'),
        ],
        'products': [
            ('Drop-In Class', 'Single class, any style', 25.00, 'FIT-DROPIN', 'Classes', 'active'),
            ('Monthly Unlimited', 'Unlimited classes for 30 days', 120.00, 'FIT-MONTHLY', 'Membership', 'active'),
            ('Private Session (1hr)', 'One-on-one instruction', 80.00, 'FIT-PRIVATE', 'Private', 'active'),
            ('10-Class Pack', '10 classes, no expiry', 200.00, 'FIT-10PACK', 'Classes', 'active'),
        ],
        'appointments': [
            ('Private session — Jordan A.', 0, 60, 'scheduled'),
            ('Trial class — Harper K.', 2, 30, 'scheduled'),
            ('Corporate wellness session', 6, 90, 'scheduled'),
            ('Private session — no show', -4, 60, 'no_show'),
            ('Group class demo', -7, 45, 'completed'),
        ]
    },
    {
        'name': 'Harbor View Realty', 'brand_accent': 'Realty', 'theme': 'slate',
        'owner': {'name': 'Morgan Blake', 'email': 'morgan@harborviewrealty.demo'},
        'staff': [{'name': 'Taylor Wren', 'email': 'taylor@harborviewrealty.demo'}],
        'leads': [
            ('Casey Whitfield', 'casey.w@example.com', '555-0801', 'Interested in touring the harborview condo listing.', 'new', 0),
            ('Jordan Silva', 'jordan.silva@example.com', '555-0802', 'Looking to sell our house, requesting a valuation.', 'new', 2),
            ('Avery Chen', 'avery.chen@example.com', '', 'Pre-approved buyer, looking for 3BR under 600k.', 'contacted', 4),
            ('Riley Marsh', 'riley.marsh@example.com', '555-0804', 'Offer accepted, following up on closing timeline.', 'won', 11),
        ],
        'customers': [
            ('Drew Halston', 'drew.halston@example.com', '555-0901', '44 Bay St', 'Closed on a condo last spring', 'buyer,closed', 'active'),
            ('Sasha Wren', 'sasha.wren@example.com', '555-0902', '', 'Actively house hunting', 'buyer', 'active'),
        ],
        'products': [
            ('Harborview 2BR Condo', 'Waterfront condo, 2 bed / 2 bath', 620000.00, 'LIST-HV-2BR', 'Condo', 'active'),
            ('Maple Street Family Home', '4 bed / 3 bath, updated kitchen', 845000.00, 'LIST-MAPLE', 'House', 'active'),
            ('Cedar Lot — Buildable Land', '1.2 acre buildable lot', 210000.00, 'LIST-CEDAR', 'Land', 'draft'),
            ('Downtown Loft', '1 bed / 1 bath, exposed brick', 410000.00, 'LIST-LOFT', 'Condo', 'inactive'),
        ],
        'appointments': [
            ('Showing — Harborview Condo', 1, 60, 'scheduled'),
            ('Listing consult — Jordan S.', 3, 45, 'scheduled'),
            ('Closing — Maple Street', -6, 120, 'completed'),
        ]
    },
]


def run():
    with app.app_context():
        for company in DEMO_COMPANIES:
            base_slug = slugify(company['name'])
            if Company.query.filter_by(slug=base_slug).first():
                print(f"skip (exists): {company['name']}")
                continue

            content = default_content(company['name'])
            content.update(CONTENT_OVERRIDES.get(base_slug, {}))
            c = Company(
                name=company['name'], slug=base_slug, theme=company['theme'],
                brand_name=company['name'], brand_accent=company['brand_accent'],
                content_json=content_to_json(content)
            )
            db.session.add(c)
            db.session.flush()

            db.session.add(User(company_id=c.id, name=company['owner']['name'], email=company['owner']['email'],
                                 password_hash=hash_password(DEMO_PASSWORD), role='owner'))
            for staff in company['staff']:
                db.session.add(User(company_id=c.id, name=staff['name'], email=staff['email'],
                                     password_hash=hash_password(DEMO_PASSWORD), role='staff'))

            for name, email, phone, message, status, days_ago in company['leads']:
                created = datetime.now(timezone.utc) - timedelta(days=days_ago)
                lead = Lead(company_id=c.id, name=name, email=email, phone=phone, message=message,
                            status=status, source='website', created_at=created, updated_at=created)
                db.session.add(lead)

            customer_objs = []
            for name, email, phone, address, notes, tags, status in company['customers']:
                cust = Customer(company_id=c.id, name=name, email=email, phone=phone,
                                 address=address, notes=notes, tags=tags, status=status)
                db.session.add(cust)
                customer_objs.append(cust)

            for name, desc, price, sku, category, status in company['products']:
                db.session.add(Product(company_id=c.id, name=name, description=desc, price=price,
                                        sku=sku, category=category, status=status))

            db.session.flush()
            for i, (title, days_offset, duration, status) in enumerate(company['appointments']):
                when = datetime.now(timezone.utc) + timedelta(days=days_offset)
                cust = customer_objs[i % len(customer_objs)] if customer_objs else None
                db.session.add(Appointment(
                    company_id=c.id, customer_id=cust.id if cust else None,
                    title=title, scheduled_at=when, duration_minutes=duration, status=status
                ))

            db.session.commit()
            print(f"created: {company['name']}  (slug={base_slug}, owner={company['owner']['email']}, password={DEMO_PASSWORD})")

        admin_email = 'admin@forgetemplates.demo'
        if not User.query.filter_by(email=admin_email).first():
            db.session.add(User(company_id=None, name='Platform Admin', email=admin_email,
                                 password_hash=hash_password(DEMO_PASSWORD), role='platform_admin'))
            db.session.commit()
            print(f"created: platform admin (email={admin_email}, password={DEMO_PASSWORD})")


if __name__ == '__main__':
    run()
