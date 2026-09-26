"""Shared lead-creation logic used by both the authenticated dashboard API
and the public, unauthenticated contact-form endpoint."""
from datetime import datetime, timedelta, timezone
from extensions import db
from models import Lead
from config import Config
from utils import is_valid_email
from errors import ValidationError


def validate_lead_input(data):
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    phone = (data.get('phone') or '').strip()
    message = (data.get('message') or '').strip()

    if not name:
        raise ValidationError('Name is required.')
    if not is_valid_email(email):
        raise ValidationError('A valid email address is required.')
    if not message:
        raise ValidationError('Message is required.')
    return {'name': name, 'email': email, 'phone': phone, 'message': message}


def find_recent_duplicate(company_id, email, message):
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=Config.DUPLICATE_LEAD_WINDOW_SECONDS)
    return (Lead.query
            .filter(Lead.company_id == company_id, Lead.email == email, Lead.message == message,
                    Lead.created_at >= cutoff, Lead.deleted_at.is_(None))
            .order_by(Lead.created_at.desc())
            .first())


def create_lead(company_id, fields, source='website', created_by=None):
    existing = find_recent_duplicate(company_id, fields['email'], fields['message'])
    if existing:
        return existing, True

    lead = Lead(
        company_id=company_id, name=fields['name'], email=fields['email'], phone=fields['phone'],
        message=fields['message'], status='new', source=source, created_by=created_by
    )
    db.session.add(lead)
    db.session.commit()
    return lead, False
