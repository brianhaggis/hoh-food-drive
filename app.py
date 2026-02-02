import os
import csv
import io
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, make_response, Response
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

from config import Config
from models import db, Show, Volunteer, ImpactStats, SlideshowImage, EmailTemplate, SiteSettings
from werkzeug.utils import secure_filename
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


UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

    # Ensure upload folder exists
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    db.init_app(app)

    with app.app_context():
        db.create_all()

        # Run migrations for new columns (SQLAlchemy doesn't auto-add columns)
        try:
            from sqlalchemy import text, inspect
            inspector = inspect(db.engine)

            # Check shows table columns
            if 'shows' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('shows')]
                with db.engine.connect() as conn:
                    if 'excluded' not in columns:
                        conn.execute(text('ALTER TABLE shows ADD COLUMN excluded BOOLEAN DEFAULT FALSE'))
                        conn.commit()
                    if 'exclude_reason' not in columns:
                        conn.execute(text('ALTER TABLE shows ADD COLUMN exclude_reason VARCHAR(200)'))
                        conn.commit()

            # Check volunteers table columns
            if 'volunteers' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('volunteers')]
                with db.engine.connect() as conn:
                    if 'cancelled' not in columns:
                        conn.execute(text('ALTER TABLE volunteers ADD COLUMN cancelled BOOLEAN DEFAULT FALSE'))
                        conn.commit()
                    if 'cancelled_at' not in columns:
                        conn.execute(text('ALTER TABLE volunteers ADD COLUMN cancelled_at TIMESTAMP'))
                        conn.commit()

            # Check slideshow_images table columns
            if 'slideshow_images' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('slideshow_images')]
                with db.engine.connect() as conn:
                    if 'mimetype' not in columns:
                        conn.execute(text('ALTER TABLE slideshow_images ADD COLUMN mimetype VARCHAR(100)'))
                        conn.commit()
                    if 'data' not in columns:
                        conn.execute(text('ALTER TABLE slideshow_images ADD COLUMN data BYTEA'))
                        conn.commit()
            else:
                db.create_all()
        except Exception as e:
            app.logger.warning(f"Migration check failed (may be OK): {e}")

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
    """Get all upcoming shows (includes excluded shows for display)."""
    shows = Show.query.filter(
        Show.date >= datetime.utcnow()
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

    # Check if show is excluded (unavailable for volunteers)
    if show.excluded:
        return jsonify({'error': 'This show is not available for volunteers'}), 400

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
    volunteer_count = Volunteer.query.filter_by(cancelled=False).count()

    # Auto-calculate shows participated (past non-excluded shows)
    shows_participated = Show.query.filter(
        Show.date < datetime.utcnow(),
        Show.excluded == False
    ).count()

    if stats:
        return jsonify({
            'pounds_collected': stats.pounds_collected,
            'meals_provided': stats.meals_provided,
            'shows_participated': shows_participated,
            'volunteers': volunteer_count
        })
    return jsonify({
        'pounds_collected': 0,
        'meals_provided': 0,
        'shows_participated': shows_participated,
        'volunteers': 0
    })


@app.route('/api/settings')
def get_settings():
    """Get public site settings."""
    return jsonify({
        'show_impact': SiteSettings.get('show_impact', 'true') == 'true'
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
    # Only show active (non-cancelled) volunteers
    volunteers = Volunteer.query.filter_by(cancelled=False).order_by(Volunteer.signup_date.desc()).limit(10).all()
    return render_template('admin/dashboard.html', shows=shows, stats=stats, volunteers=volunteers)


@app.route('/admin/volunteers/search')
@admin_required
def search_volunteers():
    """Search all volunteers (including cancelled) by name, email, city, or venue."""
    query = request.args.get('q', '').strip().lower()
    include_cancelled = request.args.get('include_cancelled', 'true') == 'true'

    if not query:
        return jsonify({'volunteers': []})

    # Build the query with joins to search show data
    volunteer_query = Volunteer.query.join(Show)

    if not include_cancelled:
        volunteer_query = volunteer_query.filter(Volunteer.cancelled == False)

    # Search across multiple fields
    search_filter = db.or_(
        Volunteer.name.ilike(f'%{query}%'),
        Volunteer.email.ilike(f'%{query}%'),
        Show.venue.ilike(f'%{query}%'),
        Show.city.ilike(f'%{query}%')
    )

    volunteers = volunteer_query.filter(search_filter).order_by(Volunteer.signup_date.desc()).limit(50).all()

    results = []
    for v in volunteers:
        results.append({
            'id': v.id,
            'name': v.name,
            'email': v.email,
            'phone': v.phone,
            'venue': v.show.venue,
            'city': v.show.city,
            'state': v.show.state,
            'show_date': v.show.date.strftime('%b %d, %Y') if v.show.date else 'TBD',
            'signup_date': v.signup_date.strftime('%b %d, %Y') if v.signup_date else 'N/A',
            'cancelled': v.cancelled,
            'cancelled_at': v.cancelled_at.strftime('%b %d, %Y') if v.cancelled_at else None
        })

    return jsonify({'volunteers': results})


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


@app.route('/admin/volunteers/csv')
@admin_required
def download_volunteers_csv():
    """Download all volunteers as CSV."""
    volunteers = Volunteer.query.join(Show).order_by(Volunteer.signup_date.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow(['Name', 'Email', 'Phone', 'Show Date', 'Venue', 'City', 'State', 'Signup Date'])

    # Data rows
    for v in volunteers:
        writer.writerow([
            v.name,
            v.email,
            v.phone,
            v.show.date.strftime('%Y-%m-%d') if v.show else '',
            v.show.venue if v.show else '',
            v.show.city if v.show else '',
            v.show.state if v.show else '',
            v.signup_date.strftime('%Y-%m-%d %H:%M') if v.signup_date else ''
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=volunteers.csv'}
    )


@app.route('/admin/volunteers/<int:volunteer_id>', methods=['DELETE'])
@admin_required
def cancel_volunteer(volunteer_id):
    """Cancel a volunteer signup and notify both parties."""
    from datetime import datetime
    from email_service import send_volunteer_cancellation, send_admin_cancellation_notice

    volunteer = Volunteer.query.get_or_404(volunteer_id)
    show = volunteer.show

    # Mark as cancelled (don't delete - keep for future outreach)
    volunteer.cancelled = True
    volunteer.cancelled_at = datetime.utcnow()

    # Check if show has any other active volunteers, if not reset has_volunteer
    remaining = Volunteer.query.filter_by(show_id=show.id, cancelled=False).filter(Volunteer.id != volunteer_id).count()
    if remaining == 0:
        show.has_volunteer = False

    db.session.commit()

    # Send cancellation emails
    send_volunteer_cancellation(volunteer, show)
    send_admin_cancellation_notice(volunteer, show)

    return jsonify({'success': True, 'show_id': show.id, 'has_volunteer': show.has_volunteer})


@app.route('/admin/shows/<int:show_id>/pantries', methods=['GET'])
@admin_required
def get_show_pantries_admin(show_id):
    """Get pantries for a show (admin)."""
    show = Show.query.get_or_404(show_id)
    return jsonify({
        'show_id': show.id,
        'venue': show.venue,
        'city': show.city,
        'state': show.state,
        'pantries': show.get_pantries()
    })


@app.route('/admin/shows/<int:show_id>/pantries', methods=['POST'])
@admin_required
def update_show_pantries(show_id):
    """Update pantries for a show."""
    show = Show.query.get_or_404(show_id)
    data = request.get_json()

    if 'pantries' in data:
        show.set_pantries(data['pantries'])
        db.session.commit()

    return jsonify({'success': True, 'pantries': show.get_pantries()})


@app.route('/admin/shows/<int:show_id>/pantries/search', methods=['POST'])
@admin_required
def search_pantries_for_show(show_id):
    """Search for pantries near a show."""
    show = Show.query.get_or_404(show_id)

    if not show.city or not show.state:
        return jsonify({'error': 'Show has no city/state info'}), 400

    pantries = get_recommended_pantries(show.city, show.state, count=10)
    formatted = format_pantries_for_display(pantries) if pantries else []

    return jsonify({'pantries': formatted})


# ============ SLIDESHOW IMAGE ROUTES ============

@app.route('/api/slideshow')
def get_slideshow_images():
    """Get active slideshow images for frontend (random order)."""
    import random
    images = SlideshowImage.query.filter_by(is_active=True).all()
    if images:
        random.shuffle(images)  # Randomize order
    return jsonify([{
        'id': img.id,
        'url': url_for('serve_image', image_id=img.id),
        'caption': img.caption
    } for img in images])


@app.route('/admin/slideshow')
@admin_required
def admin_slideshow():
    """Get slideshow images for admin."""
    images = SlideshowImage.query.order_by(SlideshowImage.display_order).all()
    return jsonify([{
        **img.to_dict(),
        'url': url_for('serve_image', image_id=img.id)
    } for img in images])


@app.route('/admin/slideshow/upload', methods=['POST'])
@admin_required
def upload_slideshow_image():
    """Upload a new slideshow image (stored in database for persistence)."""
    if 'image' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Use PNG, JPG, GIF, or WebP'}), 400

    # Read file data
    file_data = file.read()
    mimetype = file.mimetype or 'image/jpeg'

    # Generate unique filename
    filename = secure_filename(file.filename)
    base, ext = os.path.splitext(filename)
    unique_filename = f"{base}_{int(datetime.utcnow().timestamp())}{ext}"

    # Get max display order
    max_order = db.session.query(db.func.max(SlideshowImage.display_order)).scalar() or 0

    # Create database record with image data
    image = SlideshowImage(
        filename=unique_filename,
        mimetype=mimetype,
        data=file_data,
        caption=request.form.get('caption', ''),
        display_order=max_order + 1
    )
    db.session.add(image)
    db.session.commit()

    return jsonify({'success': True, 'image': image.to_dict()})


@app.route('/images/<int:image_id>')
def serve_image(image_id):
    """Serve an image from the database."""
    image = SlideshowImage.query.get_or_404(image_id)
    if not image.data:
        return jsonify({'error': 'Image data not found'}), 404

    response = Response(image.data, mimetype=image.mimetype or 'image/jpeg')
    response.headers['Cache-Control'] = 'public, max-age=31536000'  # Cache for 1 year
    return response


@app.route('/admin/slideshow/<int:image_id>', methods=['DELETE'])
@admin_required
def delete_slideshow_image(image_id):
    """Delete a slideshow image."""
    image = SlideshowImage.query.get_or_404(image_id)
    db.session.delete(image)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/admin/slideshow/<int:image_id>', methods=['PATCH'])
@admin_required
def update_slideshow_image(image_id):
    """Update slideshow image details."""
    image = SlideshowImage.query.get_or_404(image_id)
    data = request.get_json()

    if 'caption' in data:
        image.caption = data['caption']
    if 'is_active' in data:
        image.is_active = data['is_active']
    if 'display_order' in data:
        image.display_order = data['display_order']

    db.session.commit()
    return jsonify({'success': True, 'image': image.to_dict()})


# ============ EMAIL TEMPLATE ROUTES ============

@app.route('/admin/email-template/<name>')
@admin_required
def get_email_template(name):
    """Get an email template (custom or default)."""
    from email_service import DEFAULT_VOLUNTEER_SUBJECT, DEFAULT_VOLUNTEER_BODY

    template = EmailTemplate.query.filter_by(name=name).first()
    if template:
        return jsonify({
            'subject': template.subject,
            'body_html': template.body_html,
            'is_default': False,
            'updated_at': template.updated_at.isoformat() if template.updated_at else None
        })

    # Return default template
    if name == 'volunteer_confirmation':
        return jsonify({
            'subject': DEFAULT_VOLUNTEER_SUBJECT,
            'body_html': DEFAULT_VOLUNTEER_BODY,
            'is_default': True
        })

    return jsonify({'subject': '', 'body_html': '', 'is_default': True})


@app.route('/admin/email-template/<name>', methods=['POST'])
@admin_required
def save_email_template(name):
    """Save an email template."""
    data = request.get_json()

    template = EmailTemplate.query.filter_by(name=name).first()
    if not template:
        template = EmailTemplate(name=name)
        db.session.add(template)

    template.subject = data.get('subject', '')
    template.body_html = data.get('body_html', '')
    db.session.commit()

    return jsonify({'success': True})


@app.route('/admin/email-template/<name>', methods=['DELETE'])
@admin_required
def delete_email_template(name):
    """Delete custom template (revert to default)."""
    template = EmailTemplate.query.filter_by(name=name).first()
    if template:
        db.session.delete(template)
        db.session.commit()
    return jsonify({'success': True})


@app.route('/admin/settings/<key>', methods=['POST'])
@admin_required
def update_setting(key):
    """Update a site setting."""
    allowed_keys = ['show_impact']
    if key not in allowed_keys:
        return jsonify({'error': 'Invalid setting'}), 400

    value = request.form.get('value', 'true')
    setting = SiteSettings.query.filter_by(key=key).first()
    if setting:
        setting.value = value
    else:
        setting = SiteSettings(key=key, value=value)
        db.session.add(setting)
    db.session.commit()
    return jsonify({'success': True, 'value': value})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
