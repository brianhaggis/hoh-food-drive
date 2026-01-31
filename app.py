import os
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, make_response
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

from config import Config
from models import db, Show, Volunteer, ImpactStats
from bandsintown import sync_shows
from email_service import send_volunteer_confirmation, send_admin_notification
from pantry_service import get_recommended_pantries, format_pantries_for_display

# Site password (set to None or empty string to disable)
SITE_PASSWORD = os.environ.get('SITE_PASSWORD', 'icecream')


def check_site_password():
    """Check if site password is required and valid."""
    if not SITE_PASSWORD:
        return True  # No password required
    return request.cookies.get('site_access') == 'granted'


def site_password_required(f):
    """Decorator to require site password."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not check_site_password():
            return redirect(url_for('site_password_page'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


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


# Password protection for all routes
@app.before_request
def check_password_protection():
    """Check site password before each request."""
    if not SITE_PASSWORD:
        return None  # No password required

    # Allow these paths without password
    allowed_paths = ['/unlock', '/static/', '/admin', '/robots.txt', '/api/sync-shows', '/api/sync-pantries']
    if any(request.path.startswith(p) for p in allowed_paths):
        return None

    if not check_site_password():
        # For API routes, return 401
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Unauthorized'}), 401
        # For regular routes, redirect to unlock page
        return redirect(url_for('site_password_page'))

    return None


# Serve robots.txt from root
@app.route('/robots.txt')
def robots():
    return app.send_static_file('robots.txt')


# Routes
@app.route('/unlock', methods=['GET', 'POST'])
def site_password_page():
    """Site password page."""
    if not SITE_PASSWORD:
        return redirect(url_for('index'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == SITE_PASSWORD:
            response = make_response(redirect(url_for('index')))
            # Cookie lasts 30 days
            response.set_cookie('site_access', 'granted', max_age=30*24*60*60, httponly=True, samesite='Lax')
            return response
        else:
            return render_template('unlock.html', error='Incorrect password')

    return render_template('unlock.html')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/shows')
def get_shows():
    """Get all upcoming shows (excludes hidden shows)."""
    shows = Show.query.filter(
        Show.date >= datetime.utcnow(),
        Show.excluded == False
    ).order_by(Show.date).all()
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


# ============ ADMIN ROUTES ============

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Check credentials against env vars
        if (username == os.environ.get('ADMIN_USERNAME', 'admin') and
            password == os.environ.get('ADMIN_PASSWORD', '')):
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials', 'error')

    return render_template('admin/login.html')


@app.route('/admin/logout')
def admin_logout():
    """Admin logout."""
    session.pop('admin_logged_in', None)
    return redirect(url_for('index'))


@app.route('/admin')
@admin_required
def admin_dashboard():
    """Admin dashboard."""
    shows = Show.query.filter(Show.date >= datetime.utcnow()).order_by(Show.date).all()
    stats = ImpactStats.query.first()
    volunteers = Volunteer.query.order_by(Volunteer.signup_date.desc()).limit(10).all()
    return render_template('admin/dashboard.html', shows=shows, stats=stats, volunteers=volunteers)


@app.route('/admin/shows/<int:show_id>/toggle', methods=['POST'])
@admin_required
def toggle_show(show_id):
    """Toggle show excluded status."""
    show = Show.query.get_or_404(show_id)
    show.excluded = not show.excluded
    show.exclude_reason = request.form.get('reason', '') if show.excluded else None
    db.session.commit()
    return jsonify({'success': True, 'excluded': show.excluded})


@app.route('/admin/stats', methods=['POST'])
@admin_required
def update_stats():
    """Update impact statistics."""
    stats = ImpactStats.query.first()
    if not stats:
        stats = ImpactStats()
        db.session.add(stats)

    stats.pounds_collected = int(request.form.get('pounds_collected', 0))
    stats.meals_provided = int(request.form.get('meals_provided', 0))
    stats.shows_participated = int(request.form.get('shows_participated', 0))
    db.session.commit()

    flash('Stats updated successfully', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/sync', methods=['POST'])
@admin_required
def admin_sync():
    """Sync shows and pantries from admin."""
    action = request.form.get('action')

    if action == 'shows':
        count = sync_shows(db, Show, app.config['ARTIST_NAME'], app.config['BANDSINTOWN_API_KEY'])
        flash(f'Synced {count} new shows from BandsInTown', 'success')
    elif action == 'pantries':
        shows = Show.query.filter(Show.pantry_data.is_(None), Show.state.isnot(None)).all()
        updated = 0
        for show in shows:
            if show.city and show.state:
                pantries = get_recommended_pantries(show.city, show.state, count=3)
                if pantries:
                    show.set_pantries(format_pantries_for_display(pantries))
                    updated += 1
        db.session.commit()
        flash(f'Synced pantries for {updated} shows', 'success')

    return redirect(url_for('admin_dashboard'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)
