import json
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Show(db.Model):
    __tablename__ = 'shows'

    id = db.Column(db.Integer, primary_key=True)
    bandsintown_id = db.Column(db.String(100), unique=True, nullable=False)
    venue = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    date = db.Column(db.DateTime, nullable=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    has_volunteer = db.Column(db.Boolean, default=False)
    excluded = db.Column(db.Boolean, default=False)  # Exclude from food drive (festivals, opening slots)
    exclude_reason = db.Column(db.String(200), nullable=True)  # Why excluded
    pounds_collected = db.Column(db.Integer, nullable=True)  # Pounds of food collected at this show
    ticket_url = db.Column(db.String(500), nullable=True)
    pantry_data = db.Column(db.Text, nullable=True)  # JSON string of nearby food pantries
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    volunteers = db.relationship('Volunteer', backref='show', lazy=True)

    def get_pantries(self):
        """Get parsed pantry data."""
        if self.pantry_data:
            try:
                return json.loads(self.pantry_data)
            except json.JSONDecodeError:
                return []
        return []

    def set_pantries(self, pantries):
        """Set pantry data from list."""
        self.pantry_data = json.dumps(pantries) if pantries else None

    def to_dict(self, include_admin=False):
        data = {
            'id': self.id,
            'bandsintown_id': self.bandsintown_id,
            'venue': self.venue,
            'city': self.city,
            'state': self.state,
            'country': self.country,
            'date': self.date.isoformat() if self.date else None,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'has_volunteer': self.has_volunteer,
            'excluded': self.excluded,  # Always include for frontend display
            'ticket_url': self.ticket_url,
            'pantries': self.get_pantries()
        }
        if include_admin:
            data['exclude_reason'] = self.exclude_reason
            data['pounds_collected'] = self.pounds_collected
        return data


class Volunteer(db.Model):
    __tablename__ = 'volunteers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    show_id = db.Column(db.Integer, db.ForeignKey('shows.id'), nullable=False)
    signup_date = db.Column(db.DateTime, default=datetime.utcnow)
    cancelled = db.Column(db.Boolean, default=False)
    cancelled_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'show_id': self.show_id,
            'signup_date': self.signup_date.isoformat() if self.signup_date else None,
            'cancelled': self.cancelled,
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None
        }


class ImpactStats(db.Model):
    __tablename__ = 'impact_stats'

    id = db.Column(db.Integer, primary_key=True)
    pounds_collected = db.Column(db.Integer, default=0)
    meals_provided = db.Column(db.Integer, default=0)
    shows_participated = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EmailTemplate(db.Model):
    __tablename__ = 'email_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)  # 'volunteer_confirmation'
    subject = db.Column(db.String(255), nullable=False)
    body_html = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SlideshowImage(db.Model):
    __tablename__ = 'slideshow_images'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    mimetype = db.Column(db.String(100), nullable=True)
    data = db.Column(db.LargeBinary, nullable=True)  # Store image in database
    caption = db.Column(db.String(255), nullable=True)
    display_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'caption': self.caption,
            'display_order': self.display_order,
            'is_active': self.is_active
        }


class SiteSettings(db.Model):
    __tablename__ = 'site_settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get(key, default=None):
        """Get a setting value by key."""
        setting = SiteSettings.query.filter_by(key=key).first()
        return setting.value if setting else default

    @staticmethod
    def set(key, value):
        """Set a setting value."""
        from app import db as app_db
        setting = SiteSettings.query.filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            setting = SiteSettings(key=key, value=value)
            app_db.session.add(setting)
        app_db.session.commit()
        return setting


class Donation(db.Model):
    __tablename__ = 'donations'

    id = db.Column(db.Integer, primary_key=True)
    pounds = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(255), nullable=True)  # e.g., "Mailed donation from fan"
    date = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'pounds': self.pounds,
            'description': self.description,
            'date': self.date.isoformat() if self.date else None
        }
