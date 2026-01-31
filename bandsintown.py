import requests
from datetime import datetime
from flask import current_app


def fetch_shows(artist_name, app_id):
    """Fetch upcoming shows from BandsInTown API."""
    base_url = f"https://rest.bandsintown.com/artists/{artist_name}/events"
    params = {
        'app_id': app_id,
        'date': 'upcoming'
    }

    try:
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        current_app.logger.error(f"Error fetching shows from BandsInTown: {e}")
        return []


def parse_show(event):
    """Parse a BandsInTown event into our show format."""
    venue = event.get('venue', {})

    # Parse the datetime
    datetime_str = event.get('datetime', '')
    try:
        show_date = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        show_date = datetime.utcnow()

    return {
        'bandsintown_id': str(event.get('id', '')),
        'venue': venue.get('name', 'Unknown Venue'),
        'city': venue.get('city', 'Unknown City'),
        'state': venue.get('region', ''),
        'country': venue.get('country', ''),
        'date': show_date,
        'latitude': float(venue.get('latitude', 0)) if venue.get('latitude') else None,
        'longitude': float(venue.get('longitude', 0)) if venue.get('longitude') else None,
        'ticket_url': event.get('url', '')
    }


def sync_shows(db, Show, artist_name, app_id):
    """Sync shows from BandsInTown API to database."""
    events = fetch_shows(artist_name, app_id)
    synced_count = 0

    for event in events:
        show_data = parse_show(event)

        # Check if show already exists
        existing_show = Show.query.filter_by(
            bandsintown_id=show_data['bandsintown_id']
        ).first()

        if existing_show:
            # Update existing show
            for key, value in show_data.items():
                if key != 'bandsintown_id':
                    setattr(existing_show, key, value)
        else:
            # Create new show
            new_show = Show(**show_data)
            db.session.add(new_show)
            synced_count += 1

    db.session.commit()
    return synced_count
