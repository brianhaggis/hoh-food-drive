import resend
from flask import current_app


def format_pantries_html(pantries):
    """Format pantry list for email."""
    if not pantries:
        return ""

    html = """
    <h3>Local Food Pantries for Donations:</h3>
    <p><em>Collected items will be delivered to one of these local organizations:</em></p>
    <ul style="margin: 10px 0; padding-left: 20px;">
    """
    for p in pantries:
        html += f"<li style='margin-bottom: 15px;'>"
        html += f"<strong>{p.get('name', 'Food Pantry')}</strong><br>"
        if p.get('address'):
            html += f"<span style='color: #666;'>{p['address']}</span><br>"
        if p.get('phone'):
            html += f"Phone: {p['phone']}<br>"
        if p.get('hours'):
            html += f"<em>Hours: {p['hours']}</em>"
        html += "</li>"
    html += "</ul>"
    return html


def send_volunteer_confirmation(volunteer_email, volunteer_name, show):
    """Send confirmation email to volunteer with expectations and details."""
    resend.api_key = current_app.config['RESEND_API_KEY']

    show_date = show.date.strftime('%B %d, %Y at %I:%M %p') if show.date else 'TBD'
    pantries = show.get_pantries() if hasattr(show, 'get_pantries') else []
    pantries_html = format_pantries_html(pantries)

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Georgia', serif; color: #2c2c2c; line-height: 1.6; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #1b5e20 0%, #2e7d32 50%, #43a047 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
            .content {{ background: #f1f8e9; padding: 30px; border-radius: 0 0 8px 8px; }}
            .highlight {{ background: #fff; padding: 20px; border-left: 4px solid #2e7d32; margin: 20px 0; }}
            h1 {{ margin: 0; font-weight: normal; }}
            .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Thank You, {volunteer_name}!</h1>
                <p>You're making a difference with House of Hamill</p>
            </div>
            <div class="content">
                <p>We're thrilled to have you join our food drive efforts! Your volunteer spirit embodies the community-focused mission that House of Hamill believes in.</p>

                <div class="highlight">
                    <strong>Show Details:</strong><br>
                    <strong>Venue:</strong> {show.venue}<br>
                    <strong>Location:</strong> {show.city}, {show.state or show.country}<br>
                    <strong>Date:</strong> {show_date}
                </div>

                <h3>What You'll Get:</h3>
                <ul>
                    <li><strong>Two free tickets</strong> to enjoy the show</li>
                    <li>The satisfaction of making a real difference in your community</li>
                </ul>

                <h3>What You'll Do:</h3>
                <ul>
                    <li><strong>Before the show (~15 min):</strong> Set up the donation boxes and sign</li>
                    <li><strong>During the show:</strong> Enjoy the concert!</li>
                    <li><strong>After the show:</strong> Collect the donated items, weigh them (we'll have a scale), and deliver to a local food bank</li>
                </ul>

                <h3>Please Bring:</h3>
                <ul>
                    <li>Boxes or bins to transport the donations (we don't have much room in our touring vehicle!)</li>
                    <li>A vehicle to deliver items to the food bank</li>
                </ul>

                <h3>Items We're Collecting:</h3>
                <ul>
                    <li>Canned goods (vegetables, fruits, proteins)</li>
                    <li>Dry goods (pasta, rice, cereal)</li>
                    <li>Peanut butter and other shelf-stable proteins</li>
                    <li>Baby food and formula</li>
                </ul>

                {pantries_html}

                <p>A member of our team will reach out closer to the show date with specific logistics and contact information.</p>

                <p>Thank you for being part of the House of Hamill family and helping us fight hunger in our communities!</p>

                <div class="footer">
                    <p>With gratitude,<br><strong>House of Hamill</strong></p>
                    <p><a href="https://www.houseofhamill.com">www.houseofhamill.com</a></p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    try:
        params = {
            "from": "House of Hamill Food Drive <onboarding@resend.dev>",
            "to": [volunteer_email],
            "subject": f"You're Confirmed! Food Drive Volunteer for {show.venue}",
            "html": html_content
        }
        resend.Emails.send(params)
        return True
    except Exception as e:
        current_app.logger.error(f"Error sending volunteer confirmation: {e}")
        return False


def send_admin_notification(volunteer, show):
    """Send notification to admin about new volunteer signup."""
    resend.api_key = current_app.config['RESEND_API_KEY']

    show_date = show.date.strftime('%B %d, %Y at %I:%M %p') if show.date else 'TBD'
    signup_date = volunteer.signup_date.strftime('%B %d, %Y at %I:%M %p') if volunteer.signup_date else 'Just now'

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Georgia', serif; color: #2c2c2c; line-height: 1.6; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #28a745; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
            .content {{ background: #f8f9fa; padding: 30px; border-radius: 0 0 8px 8px; }}
            .info-box {{ background: #fff; padding: 20px; border-radius: 8px; margin: 15px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            h1 {{ margin: 0; font-size: 24px; }}
            .label {{ color: #666; font-size: 12px; text-transform: uppercase; margin-bottom: 5px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>New Volunteer Signup!</h1>
            </div>
            <div class="content">
                <div class="info-box">
                    <div class="label">Volunteer Information</div>
                    <p><strong>Name:</strong> {volunteer.name}</p>
                    <p><strong>Email:</strong> <a href="mailto:{volunteer.email}">{volunteer.email}</a></p>
                    <p><strong>Phone:</strong> <a href="tel:{volunteer.phone}">{volunteer.phone}</a></p>
                    <p><strong>Signed up:</strong> {signup_date}</p>
                </div>

                <div class="info-box">
                    <div class="label">Show Details</div>
                    <p><strong>Venue:</strong> {show.venue}</p>
                    <p><strong>Location:</strong> {show.city}, {show.state or show.country}</p>
                    <p><strong>Date:</strong> {show_date}</p>
                </div>

                <p style="text-align: center; margin-top: 20px;">
                    <em>This show now has a confirmed volunteer!</em>
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    try:
        params = {
            "from": "Food Drive Notifications <onboarding@resend.dev>",
            "to": [current_app.config['ADMIN_EMAIL']],
            "subject": f"New Volunteer: {volunteer.name} for {show.venue}",
            "html": html_content
        }
        resend.Emails.send(params)
        return True
    except Exception as e:
        current_app.logger.error(f"Error sending admin notification: {e}")
        return False
