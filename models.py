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

    def to_dict(self):
        return {
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
            'ticket_url': self.ticket_url,
            'pantries': self.get_pantries()
        }


class Volunteer(db.Model):
    __tablename__ = 'volunteers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    show_id = db.Column(db.Integer, db.ForeignKey('shows.id'), nullable=False)
    signup_date = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'show_id': self.show_id,
            'signup_date': self.signup_date.isoformat() if self.signup_date else None
        }


class ImpactStats(db.Model):
    __tablename__ = 'impact_stats'

    id = db.Column(db.Integer, primary_key=True)
    pounds_collected = db.Column(db.Integer, default=0)
    meals_provided = db.Column(db.Integer, default=0)
    shows_participated = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
