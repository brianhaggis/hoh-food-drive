import re
import resend
from flask import current_app
from premailer import transform
from models import EmailTemplate


def format_hours(hours_str):
    """Format hours string for better readability - split onto separate lines."""
    if not hours_str:
        return ""

    formatted = hours_str.strip()

    # Split on semicolons (used to separate different day ranges)
    formatted = re.sub(r';\s*', '<br>', formatted)

    return formatted


# CSS styles for volunteer emails - injected before inlining
VOLUNTEER_EMAIL_STYLES = """
<style>
    body { font-family: 'Georgia', serif; color: #2c2c2c; line-height: 1.6; }
    .container { max-width: 800px; margin: 0 auto; padding: 20px; }
    .header { background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 50%, #43a047 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }
    .content { background: #f1f8e9; padding: 30px; border-radius: 0 0 8px 8px; }
    .highlight { background: #fff; padding: 20px; border-left: 4px solid #2e7d32; margin: 20px 0; }
    h1 { margin: 0; font-weight: normal; }
    .footer { text-align: center; margin-top: 30px; color: #666; font-size: 14px; }
</style>
"""


def inline_css(html):
    """Convert CSS styles to inline styles for email compatibility.

    This ensures emails render correctly in clients like Gmail and Outlook
    that strip <style> blocks.
    """
    try:
        # If the HTML doesn't have a <style> block, inject our default styles
        if '<style>' not in html and '</style>' not in html:
            # Find the <head> tag and inject styles, or wrap if no proper structure
            if '<head>' in html:
                html = html.replace('<head>', '<head>' + VOLUNTEER_EMAIL_STYLES)
            elif '<html>' in html:
                html = html.replace('<html>', '<html><head>' + VOLUNTEER_EMAIL_STYLES + '</head>')
            else:
                # Wrap the whole thing in proper HTML structure with styles
                html = f'''<!DOCTYPE html>
<html>
<head>{VOLUNTEER_EMAIL_STYLES}</head>
<body>{html}</body>
</html>'''

        # Use premailer to convert CSS to inline styles
        return transform(html, remove_classes=False, strip_important=False)
    except Exception as e:
        current_app.logger.warning(f"CSS inlining failed, using original HTML: {e}")
        return html


def format_pantries_html(pantries):
    """Format pantry list for email."""
    if not pantries:
        return ""

    html = """
    <h3>Local Food Pantries for Donations:</h3>
    <p><em>Please reach out to one of these organizations in advance to coordinate your drop-off:</em></p>
    <ul style="margin: 10px 0; padding-left: 20px;">
    """
    for p in pantries:
        html += f"<li style='margin-bottom: 15px;'>"
        html += f"<strong>{p.get('name', 'Food Pantry')}</strong><br>"
        if p.get('address'):
            html += f"<span style='color: #666;'>{p['address']}</span><br>"
        if p.get('phone'):
            html += f"Phone: {p['phone']}"
        html += "</li>"
    html += "</ul>"
    return html


DEFAULT_VOLUNTEER_SUBJECT = "You're Confirmed! Food Drive Volunteer for {venue}"

DEFAULT_VOLUNTEER_BODY = """<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: 'Georgia', serif; color: #2c2c2c; line-height: 1.6; }
        .container { max-width: 800px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 50%, #43a047 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }
        .content { background: #f1f8e9; padding: 30px; border-radius: 0 0 8px 8px; }
        .highlight { background: #fff; padding: 20px; border-left: 4px solid #2e7d32; margin: 20px 0; }
        h1 { margin: 0; font-weight: normal; }
        .footer { text-align: center; margin-top: 30px; color: #666; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Thank You, {volunteer_name}!</h1>
            <p>You're making a difference with House of Hamill</p>
        </div>
        <div class="content">
            <p>We're thrilled to have you join our food drive efforts! Hunger is a terrible thing for people in our communities to face, and your efforts will make a bigger difference than you know.</p>

            <div class="highlight">
                <strong>Show Details:</strong><br>
                <strong>Venue:</strong> {venue}<br>
                <strong>Location:</strong> {location}<br>
                <strong>Date:</strong> {show_date}
            </div>

            {venue_history}

            <h3>What You'll Get:</h3>
            <ul>
                <li><strong>Two free tickets</strong> to enjoy the show (we'll have your name on the guest list at the door)</li>
                <li>The satisfaction of making a real difference in your community</li>
                <li>Our sincere gratitude for your time and effort</li>
            </ul>

            <h3>What You'll Do:</h3>
            <ul>
                <li><strong>Before the show (~15 min):</strong> Set up the donation boxes by the Food Pantry sign</li>
                <li><strong>During the show:</strong> Enjoy the concert! Sing along, dance, enjoy yourselves :)</li>
                <li><strong>After the show:</strong> Collect the donated items, weigh them (we'll have a scale), and deliver to a local food bank. Suggested locations are below, but we trust you to get the donations to any collection point that's convenient for you - preferably within a couple of days.</li>
            </ul>

            <h3>Please Bring:</h3>
            <ul>
                <li><strong>Boxes or bins to transport the donations</strong> (we don't have much room in our touring vehicle, so we'll count on you to collect the food in containers you can cart away afterwards)!</li>
                <li><strong>A vehicle</strong> to deliver items to the food bank. You might wind up with a LOT of food to transport, so it's important you arrive in a getaway car that has enough space!</li>
            </ul>

            <h3>Items We're Collecting:</h3>
            <ul>
                <li>Canned goods (vegetables, fruits, proteins)</li>
                <li>Dry goods (pasta, rice, cereal)</li>
                <li>Peanut butter and other shelf-stable proteins</li>
                <li>Baby food and formula</li>
                <li>Sealed items only - nothing that isn't full, or has been opened</li>
            </ul>

            {pantries_html}

            <p>Feel free to respond to this email with any questions - otherwise, we'll see you at the show :)</p>

            <p>Thank you for being part of something good - and helping us fight hunger in our communities!</p>

            <div class="footer">
                <p>With gratitude,<br><strong>Brian, Rose &amp; Caroline</strong></p>
                <p><a href="https://www.houseofhamill.com">www.houseofhamill.com</a></p>
            </div>
        </div>
    </div>
</body>
</html>"""


def get_volunteer_template():
    """Get volunteer email template from database or return default."""
    template = EmailTemplate.query.filter_by(name='volunteer_confirmation').first()
    if template:
        return {'subject': template.subject, 'body_html': template.body_html}
    return {'subject': DEFAULT_VOLUNTEER_SUBJECT, 'body_html': DEFAULT_VOLUNTEER_BODY}


def get_venue_history_html(venue_name, current_show_id=None):
    """Get formatted HTML for past collections at this venue."""
    from models import Show
    from datetime import datetime

    # Find past shows at this venue with recorded pounds
    query = Show.query.filter(
        Show.venue == venue_name,
        Show.date < datetime.utcnow(),
        Show.pounds_collected.isnot(None)
    )
    if current_show_id:
        query = query.filter(Show.id != current_show_id)

    past_shows = query.order_by(Show.date.desc()).all()

    if not past_shows:
        return ''

    total_pounds = sum(s.pounds_collected for s in past_shows)
    total_meals = int(total_pounds / 1.2)

    html = f"""
    <div style="background: #e8f5e9; border-left: 4px solid #2e7d32; padding: 15px; margin: 20px 0; border-radius: 0 8px 8px 0;">
        <strong style="color: #1b5e20;">Return Engagement!</strong><br>
        <p style="margin: 10px 0 0 0;">We've collected food at {past_shows[0].venue} before! In our previous {len(past_shows)} visit{'s' if len(past_shows) > 1 else ''}, we collected <strong>{total_pounds:,} lbs</strong> of food ({total_meals:,} meals).</p>
    </div>
    """
    return html


def send_volunteer_confirmation(volunteer_email, volunteer_name, show):
    """Send confirmation email to volunteer with expectations and details."""
    try:
        resend.api_key = current_app.config['RESEND_API_KEY']

        show_date = show.date.strftime('%B %d, %Y at %I:%M %p') if show.date else 'TBD'
        location = f"{show.city}, {show.state or show.country}"
        pantries = show.get_pantries() if hasattr(show, 'get_pantries') else []
        pantries_html = format_pantries_html(pantries)

        # Get venue history for return engagements
        venue_history_html = get_venue_history_html(show.venue, show.id)

        # Get template (custom or default)
        template = get_volunteer_template()

        # Replace placeholders using simple string replacement (avoids CSS brace issues)
        subject = template['subject']
        subject = subject.replace('{volunteer_name}', volunteer_name)
        subject = subject.replace('{venue}', show.venue)
        subject = subject.replace('{location}', location)
        subject = subject.replace('{show_date}', show_date)

        body = template['body_html']
        body = body.replace('{volunteer_name}', volunteer_name)
        body = body.replace('{venue}', show.venue)
        body = body.replace('{location}', location)
        body = body.replace('{show_date}', show_date)
        body = body.replace('{pantries_html}', pantries_html)
        body = body.replace('{venue_history}', venue_history_html)

        # Convert CSS to inline styles for email client compatibility
        body = inline_css(body)

        params = {
            "from": "House of Hamill Volunteers <volunteers@houseofhamill.com>",
            "to": [volunteer_email],
            "reply_to": "volunteers@houseofhamill.com",
            "subject": subject,
            "html": body
        }
        resend.Emails.send(params)
        return True
    except Exception as e:
        import traceback
        current_app.logger.error(f"Error sending volunteer confirmation to {volunteer_email}: {e}")
        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        return False


def send_admin_notification(volunteer, show):
    """Send notification to band about new volunteer signup."""
    resend.api_key = current_app.config['RESEND_API_KEY']

    show_date = show.date.strftime('%A, %B %d, %Y at %I:%M %p') if show.date else 'TBD'
    signup_date = volunteer.signup_date.strftime('%B %d, %Y at %I:%M %p') if volunteer.signup_date else 'Just now'

    # Get pantry info
    pantries = show.get_pantries() if hasattr(show, 'get_pantries') else []
    pantries_html = format_pantries_html(pantries) if pantries else "<p><em>No food pantries have been added for this show yet.</em></p>"

    # Get venue history for return engagements
    venue_history_html = get_venue_history_html(show.venue, show.id)

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #2c2c2c; line-height: 1.6; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 100%); color: white; padding: 25px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f8f9fa; padding: 30px; border-radius: 0 0 8px 8px; }}
        .info-box {{ background: #fff; padding: 20px; border-radius: 8px; margin: 15px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ margin: 0; font-size: 24px; }}
        h2 {{ color: #2e7d32; font-size: 18px; margin: 0 0 15px 0; }}
        table {{ width: 100%; border-collapse: collapse; }}
        td {{ padding: 8px 0; border-bottom: 1px solid #eee; }}
        td:first-child {{ color: #666; width: 100px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>New Volunteer Signup!</h1>
            <p style="margin: 10px 0 0 0; opacity: 0.9;">{show.venue} - {show.city}, {show.state or show.country}</p>
        </div>
        <div class="content">
            <div class="info-box">
                <h2>Volunteer Contact Info</h2>
                <table>
                    <tr><td>Name</td><td><strong>{volunteer.name}</strong></td></tr>
                    <tr><td>Email</td><td><a href="mailto:{volunteer.email}">{volunteer.email}</a></td></tr>
                    <tr><td>Phone</td><td><a href="tel:{volunteer.phone}">{volunteer.phone}</a></td></tr>
                </table>
            </div>

            <div class="info-box">
                <h2>Show Details</h2>
                <table>
                    <tr><td>Venue</td><td><strong>{show.venue}</strong></td></tr>
                    <tr><td>Location</td><td>{show.city}, {show.state or show.country}</td></tr>
                    <tr><td>Date</td><td>{show_date}</td></tr>
                </table>
            </div>

            {venue_history_html}

            <div class="info-box">
                <h2>Food Pantries for This Show</h2>
                {pantries_html}
            </div>

            <p style="text-align: center; margin-top: 20px; color: #666; font-size: 14px;">
                Signed up: {signup_date}
            </p>
        </div>
    </div>
</body>
</html>"""

    try:
        params = {
            "from": "House of Hamill Volunteers <volunteers@houseofhamill.com>",
            "to": ["volunteers@houseofhamill.com"],
            "reply_to": volunteer.email,
            "subject": f"New Volunteer: {volunteer.name} for {show.venue} ({show.city})",
            "html": html_content
        }
        resend.Emails.send(params)
        return True
    except Exception as e:
        current_app.logger.error(f"Error sending admin notification: {e}")
        return False


def send_volunteer_cancellation(volunteer, show):
    """Send cancellation confirmation to volunteer."""
    resend.api_key = current_app.config['RESEND_API_KEY']

    show_date = show.date.strftime('%B %d, %Y') if show.date else 'TBD'
    location = f"{show.city}, {show.state or show.country}"

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: 'Georgia', serif; color: #2c2c2c; line-height: 1.6; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #5d4037; color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background: #fafafa; padding: 30px; border-radius: 0 0 8px 8px; }}
        h1 {{ margin: 0; font-weight: normal; }}
        .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Volunteer Signup Cancelled</h1>
        </div>
        <div class="content">
            <p>Hi {volunteer.name},</p>

            <p>This email confirms that your volunteer signup has been cancelled for:</p>

            <div style="background: #fff; padding: 20px; border-left: 4px solid #5d4037; margin: 20px 0;">
                <strong>{show.venue}</strong><br>
                {location}<br>
                {show_date}
            </div>

            <p>We're sorry you won't be able to join us for this show. If your plans change or you'd like to volunteer for a different show, you're always welcome to sign up again at our website.</p>

            <p>Thank you for your interest in helping House of Hamill fight hunger in our communities!</p>

            <div class="footer">
                <p>With gratitude,<br><strong>House of Hamill</strong></p>
                <p><a href="https://www.houseofhamill.com">www.houseofhamill.com</a></p>
            </div>
        </div>
    </div>
</body>
</html>"""

    try:
        params = {
            "from": "House of Hamill Volunteers <volunteers@houseofhamill.com>",
            "to": [volunteer.email],
            "reply_to": "volunteers@houseofhamill.com",
            "subject": f"Volunteer Signup Cancelled - {show.venue}",
            "html": html_content
        }
        resend.Emails.send(params)
        return True
    except Exception as e:
        current_app.logger.error(f"Error sending volunteer cancellation: {e}")
        return False


def send_admin_cancellation_notice(volunteer, show):
    """Notify band that a volunteer has cancelled and the slot is reopened."""
    resend.api_key = current_app.config['RESEND_API_KEY']

    show_date = show.date.strftime('%A, %B %d, %Y at %I:%M %p') if show.date else 'TBD'

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #2c2c2c; line-height: 1.6; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #c62828; color: white; padding: 25px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f8f9fa; padding: 30px; border-radius: 0 0 8px 8px; }}
        .info-box {{ background: #fff; padding: 20px; border-radius: 8px; margin: 15px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ margin: 0; font-size: 24px; }}
        h2 {{ color: #c62828; font-size: 18px; margin: 0 0 15px 0; }}
        table {{ width: 100%; border-collapse: collapse; }}
        td {{ padding: 8px 0; border-bottom: 1px solid #eee; }}
        td:first-child {{ color: #666; width: 100px; }}
        .action-needed {{ background: #fff3cd; border: 1px solid #ffc107; padding: 15px; border-radius: 8px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Volunteer Cancelled</h1>
            <p style="margin: 10px 0 0 0; opacity: 0.9;">{show.venue} - {show.city}, {show.state or show.country}</p>
        </div>
        <div class="content">
            <div class="info-box">
                <h2>Cancelled Volunteer</h2>
                <table>
                    <tr><td>Name</td><td><strong>{volunteer.name}</strong></td></tr>
                    <tr><td>Email</td><td>{volunteer.email}</td></tr>
                    <tr><td>Phone</td><td>{volunteer.phone}</td></tr>
                </table>
            </div>

            <div class="info-box">
                <h2>Show Details</h2>
                <table>
                    <tr><td>Venue</td><td><strong>{show.venue}</strong></td></tr>
                    <tr><td>Location</td><td>{show.city}, {show.state or show.country}</td></tr>
                    <tr><td>Date</td><td>{show_date}</td></tr>
                </table>
            </div>

            <div class="action-needed">
                <strong>Action Needed:</strong>
                <ul style="margin: 10px 0 0 0; padding-left: 20px;">
                    <li>Remove <strong>{volunteer.name}</strong> from the guest list</li>
                    <li>This show is now <strong>open for new volunteers</strong></li>
                </ul>
            </div>
        </div>
    </div>
</body>
</html>"""

    try:
        params = {
            "from": "House of Hamill Volunteers <volunteers@houseofhamill.com>",
            "to": ["volunteers@houseofhamill.com"],
            "subject": f"CANCELLED: {volunteer.name} for {show.venue} ({show.city}) - Slot Reopened",
            "html": html_content
        }
        resend.Emails.send(params)
        return True
    except Exception as e:
        current_app.logger.error(f"Error sending admin cancellation notice: {e}")
        return False
