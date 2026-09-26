import re
import json
from errors import ValidationError

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
_SLUG_STRIP_RE = re.compile(r'[^a-z0-9]+')


def is_valid_email(email):
    return bool(email) and bool(_EMAIL_RE.match(email.strip()))


def slugify(text):
    slug = _SLUG_STRIP_RE.sub('-', text.strip().lower()).strip('-')
    return slug or 'company'


def unique_slug(base_name):
    from models import Company
    base = slugify(base_name)
    slug = base
    n = 2
    while Company.query.filter_by(slug=slug).first() is not None:
        slug = f'{base}-{n}'
        n += 1
    return slug


def require_fields(data, *fields):
    missing = [f for f in fields if not str(data.get(f) or '').strip()]
    if missing:
        raise ValidationError(f"Missing required field(s): {', '.join(missing)}.")


def parse_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def default_content(company_name):
    """Starter content.json shape for a newly registered company."""
    return {
        "hero": {
            "badge": f"✨ Welcome to {company_name}",
            "title": f"Grow {company_name} with a website that works as hard as you do.",
            "subtitle": "Everything a local business needs — services, testimonials and a contact funnel — in one fast, mobile-ready site.",
            "primaryCta": "Get a Quote",
            "secondaryCta": "See Services",
            "image": "https://images.unsplash.com/photo-1556740738-b6a63e27c4df?w=700&q=80",
            "stats": [
                {"value": "500+", "label": "Happy customers"},
                {"value": "4.9/5", "label": "Average rating"},
                {"value": "10+", "label": "Years in business"}
            ]
        },
        "logoStrip": {
            "label": "Trusted across the community",
            "items": ["Local", "Reliable", "Insured", "Family-Owned"]
        },
        "features": {
            "label": "Why Choose Us",
            "title": "Built to earn your trust",
            "subtitle": "Here's what sets us apart.",
            "items": [
                {"icon": "⚡", "title": "Fast Response", "text": "We get back to every inquiry quickly."},
                {"icon": "🎯", "title": "Reliable Service", "text": "Consistent, quality work every time."},
                {"icon": "💬", "title": "Clear Communication", "text": "You'll always know where things stand."}
            ]
        },
        "about": {
            "label": "About Us",
            "title": f"About {company_name}",
            "text": "Tell your story here — edit this from the Content & Branding page in your dashboard.",
            "image": "https://images.unsplash.com/photo-1521737604893-d14cc237f11d?w=650&q=80",
            "badgeValue": "100%",
            "badgeLabel": "Satisfaction",
            "bullets": [
                "Add your key selling points here",
                "Edit all of this from your dashboard",
                "No code required"
            ]
        },
        "testimonials": {
            "label": "Testimonials",
            "title": "What customers say",
            "subtitle": "Real feedback from real customers.",
            "items": [
                {"quote": "Great service from start to finish.", "name": "A. Customer", "role": "Verified Customer"}
            ]
        },
        "cta": {
            "title": "Ready to get started?",
            "text": "Reach out today and we'll take it from there.",
            "email": "hello@example.com"
        },
        "contactForm": {
            "title": "Get in touch",
            "text": "Send us a message and we'll get back to you shortly.",
            "successMessage": "Thanks! Your message has been received.",
            "errorMessage": "Something went wrong. Please try again."
        },
        "footer": {
            "tagline": f"{company_name} — proudly serving our community.",
            "copyright": f"© 2026 {company_name}"
        }
    }


def content_to_json(content_dict):
    return json.dumps(content_dict)


def content_from_json(content_str):
    try:
        return json.loads(content_str)
    except (TypeError, ValueError):
        return {}
