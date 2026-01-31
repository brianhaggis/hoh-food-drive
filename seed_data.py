"""
Seed data script for local development and testing.
Run with: python seed_data.py
"""

from datetime import datetime, timedelta
from app import app, db
from models import Show, ImpactStats


def seed_shows():
    """Add sample show data for testing."""
    sample_shows = [
        {
            'bandsintown_id': 'demo_1',
            'venue': 'The Tin Pan',
            'city': 'Richmond',
            'state': 'VA',
            'country': 'USA',
            'date': datetime.now() + timedelta(days=14),
            'latitude': 37.5407,
            'longitude': -77.4360,
            'has_volunteer': False,
            'ticket_url': 'https://www.houseofhamill.com/tour'
        },
        {
            'bandsintown_id': 'demo_2',
            'venue': 'Club Passim',
            'city': 'Cambridge',
            'state': 'MA',
            'country': 'USA',
            'date': datetime.now() + timedelta(days=21),
            'latitude': 42.3736,
            'longitude': -71.1097,
            'has_volunteer': True,
            'ticket_url': 'https://www.houseofhamill.com/tour'
        },
        {
            'bandsintown_id': 'demo_3',
            'venue': 'Eddie\'s Attic',
            'city': 'Decatur',
            'state': 'GA',
            'country': 'USA',
            'date': datetime.now() + timedelta(days=28),
            'latitude': 33.7756,
            'longitude': -84.2963,
            'has_volunteer': False,
            'ticket_url': 'https://www.houseofhamill.com/tour'
        },
        {
            'bandsintown_id': 'demo_4',
            'venue': 'The Birchmere',
            'city': 'Alexandria',
            'state': 'VA',
            'country': 'USA',
            'date': datetime.now() + timedelta(days=35),
            'latitude': 38.8185,
            'longitude': -77.0861,
            'has_volunteer': False,
            'ticket_url': 'https://www.houseofhamill.com/tour'
        },
        {
            'bandsintown_id': 'demo_5',
            'venue': 'Jammin\' Java',
            'city': 'Vienna',
            'state': 'VA',
            'country': 'USA',
            'date': datetime.now() + timedelta(days=42),
            'latitude': 38.9012,
            'longitude': -77.2653,
            'has_volunteer': True,
            'ticket_url': 'https://www.houseofhamill.com/tour'
        },
        {
            'bandsintown_id': 'demo_6',
            'venue': 'City Winery',
            'city': 'Nashville',
            'state': 'TN',
            'country': 'USA',
            'date': datetime.now() + timedelta(days=49),
            'latitude': 36.1627,
            'longitude': -86.7816,
            'has_volunteer': False,
            'ticket_url': 'https://www.houseofhamill.com/tour'
        },
        {
            'bandsintown_id': 'demo_7',
            'venue': 'Old Town School of Folk Music',
            'city': 'Chicago',
            'state': 'IL',
            'country': 'USA',
            'date': datetime.now() + timedelta(days=56),
            'latitude': 41.9394,
            'longitude': -87.6708,
            'has_volunteer': False,
            'ticket_url': 'https://www.houseofhamill.com/tour'
        },
        {
            'bandsintown_id': 'demo_8',
            'venue': 'The Dakota',
            'city': 'Minneapolis',
            'state': 'MN',
            'country': 'USA',
            'date': datetime.now() + timedelta(days=63),
            'latitude': 44.9778,
            'longitude': -93.2650,
            'has_volunteer': False,
            'ticket_url': 'https://www.houseofhamill.com/tour'
        }
    ]

    with app.app_context():
        # Clear existing demo shows
        Show.query.filter(Show.bandsintown_id.like('demo_%')).delete()

        # Add new shows
        for show_data in sample_shows:
            show = Show(**show_data)
            db.session.add(show)

        # Update impact stats
        stats = ImpactStats.query.first()
        if stats:
            stats.pounds_collected = 2500
            stats.meals_provided = 2000
            stats.shows_participated = 15
        else:
            stats = ImpactStats(
                pounds_collected=2500,
                meals_provided=2000,
                shows_participated=15
            )
            db.session.add(stats)

        db.session.commit()
        print(f"Seeded {len(sample_shows)} sample shows!")
        print("Impact stats updated!")


if __name__ == '__main__':
    seed_shows()
