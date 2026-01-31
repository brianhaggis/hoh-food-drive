import os
from flask import Flask, render_template, request, jsonify
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

from config import Config
from models import db, Show, Volunteer, ImpactStats
from bandsintown import sync_shows
from email_service import send_volunteer_confirmation, send_admin_notification
from pantry_service import get_recommended_pantries, format_pantries_for_display


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        db.create_all()

        # Initialize impact stats if not exists
        if not ImpactStats.query.first():
            stats = ImpactStats(
                pounds_collected=2500,
                meals_provided=2000,
                shows_participated=15
            )
            db.session.add(stats)
            db.session.commit()

    return app


app = create_app()


# Background scheduler for daily show sync
def scheduled_sync():
    with app.app_context():
        sync_shows(
            db, Show,
            app.config['ARTIST_NAME'],
            app.config['BANDSINTOWN_API_KEY']
        )
        app.logger.info("Completed scheduled show sync")


scheduler = BackgroundScheduler()
scheduler.add_job(func=scheduled_sync, trigger="cron", hour=6, minute=0)
scheduler.start()


# Routes
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/shows')
def get_shows():
    """Get all upcoming shows."""
    shows = Show.query.filter(Show.date >= datetime.utcnow()).order_by(Show.date).all()
    return jsonify([show.to_dict() for show in shows])


@app.route('/api/shows/<int:show_id>')
def get_show(show_id):
    """Get a specific show."""
    show = Show.query.get_or_404(show_id)
    return jsonify(show.to_dict())


@app.route('/api/volunteer', methods=['POST'])
def volunteer_signup():
    """Handle volunteer signup."""
    data = request.get_json()

    # Validate required fields
    required_fields = ['name', 'email', 'phone', 'show_id']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400

    # Get the show
    show = Show.query.get(data['show_id'])
    if not show:
        return jsonify({'error': 'Show not found'}), 404

    # Check if show already has a volunteer
    if show.has_volunteer:
        return jsonify({'error': 'This show already has a volunteer'}), 400

    # Create volunteer record
    volunteer = Volunteer(
        name=data['name'],
        email=data['email'],
        phone=data['phone'],
        show_id=show.id
    )
    db.session.add(volunteer)

    # Update show status
    show.has_volunteer = True
    db.session.commit()

    # Send emails
    send_volunteer_confirmation(volunteer.email, volunteer.name, show)
    send_admin_notification(volunteer, show)

    return jsonify({
        'success': True,
        'message': 'Thank you for volunteering!',
        'volunteer': volunteer.to_dict()
    })


@app.route('/api/stats')
def get_stats():
    """Get impact statistics."""
    stats = ImpactStats.query.first()
    volunteer_count = Volunteer.query.count()

    if stats:
        return jsonify({
            'pounds_collected': stats.pounds_collected,
            'meals_provided': stats.meals_provided,
            'shows_participated': stats.shows_participated,
            'volunteers': volunteer_count
        })
    return jsonify({
        'pounds_collected': 0,
        'meals_provided': 0,
        'shows_participated': 0,
        'volunteers': 0
    })


@app.route('/api/sync-shows', methods=['POST'])
def manual_sync():
    """Manually trigger show sync (for admin use)."""
    count = sync_shows(
        db, Show,
        app.config['ARTIST_NAME'],
        app.config['BANDSINTOWN_API_KEY']
    )
    return jsonify({'success': True, 'new_shows': count})


@app.route('/api/sync-pantries', methods=['POST'])
def sync_pantries():
    """Fetch food pantry data for all shows without pantry info."""
    shows = Show.query.filter(
        Show.pantry_data.is_(None),
        Show.state.isnot(None)
    ).all()

    updated = 0
    for show in shows:
        if show.city and show.state:
            pantries = get_recommended_pantries(show.city, show.state, count=3)
            if pantries:
                show.set_pantries(format_pantries_for_display(pantries))
                updated += 1

    db.session.commit()
    return jsonify({'success': True, 'shows_updated': updated})


@app.route('/api/shows/<int:show_id>/pantries')
def get_show_pantries(show_id):
    """Get food pantries for a specific show."""
    show = Show.query.get_or_404(show_id)

    # If no cached pantries, fetch them
    if not show.pantry_data and show.city and show.state:
        pantries = get_recommended_pantries(show.city, show.state, count=3)
        if pantries:
            show.set_pantries(format_pantries_for_display(pantries))
            db.session.commit()

    return jsonify(show.get_pantries())


if __name__ == '__main__':
    app.run(debug=True, port=5000)
