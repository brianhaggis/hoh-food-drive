# House of Hamill Food Drive Volunteer App

A web application for coordinating food drive volunteers at House of Hamill shows.

## Features

- Interactive map showing upcoming shows with volunteer status
- Volunteer signup form with email confirmations
- BandsInTown API integration for automatic show updates
- Impact statistics dashboard
- Mobile responsive design
- Spotify embed for music discovery

## Tech Stack

- **Backend**: Flask, SQLAlchemy, APScheduler
- **Database**: SQLite (development) / PostgreSQL (production)
- **Frontend**: Vanilla HTML/CSS/JavaScript, Leaflet.js
- **Email**: Resend API
- **Shows Data**: BandsInTown API
- **Deployment**: Render

## Local Development

### Prerequisites

- Python 3.9+
- pip

### Setup

1. Clone the repository:
   ```bash
   cd food-drive-webapp
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file from the example:
   ```bash
   cp .env.example .env
   ```

5. Edit `.env` with your API keys:
   ```
   BANDSINTOWN_API_KEY=your_key_here
   RESEND_API_KEY=your_key_here
   FLASK_SECRET_KEY=generate_a_secure_key
   ```

6. Initialize the database and seed sample data:
   ```bash
   python seed_data.py
   ```

7. Run the development server:
   ```bash
   python app.py
   ```

8. Open http://localhost:5000 in your browser.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main page |
| `/api/shows` | GET | List all upcoming shows |
| `/api/shows/<id>` | GET | Get specific show |
| `/api/volunteer` | POST | Submit volunteer signup |
| `/api/stats` | GET | Get impact statistics |
| `/api/sync-shows` | POST | Manually sync shows from BandsInTown |

## Deployment to Render

### Prerequisites

- Render account (paid for cron jobs)
- BandsInTown API key
- Resend API key with verified domain

### Steps

1. Push code to GitHub repository

2. Create new Web Service on Render:
   - Connect your GitHub repo
   - Select Python environment
   - Use `render.yaml` for configuration

3. Add environment variables in Render dashboard:
   - `BANDSINTOWN_API_KEY`
   - `RESEND_API_KEY`
   - `ADMIN_EMAIL` (defaults to houseofhamill@gmail.com)

4. Render will automatically:
   - Create a PostgreSQL database
   - Set up the web service
   - Configure the daily cron job for show syncing

### Email Configuration

For Resend emails to work in production:

1. Verify your domain in Resend dashboard
2. Update the "from" addresses in `email_service.py` to use your verified domain

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `FLASK_SECRET_KEY` | Flask session secret | Yes |
| `BANDSINTOWN_API_KEY` | BandsInTown API key | Yes |
| `RESEND_API_KEY` | Resend email API key | Yes |
| `ADMIN_EMAIL` | Email for volunteer notifications | No |
| `DATABASE_URL` | Database connection string | No |

## Database Schema

### Shows Table
- `id` - Primary key
- `bandsintown_id` - Unique identifier from BandsInTown
- `venue` - Venue name
- `city` - City name
- `state` - State/region
- `country` - Country
- `date` - Show date/time
- `latitude` - Venue latitude
- `longitude` - Venue longitude
- `has_volunteer` - Boolean flag
- `ticket_url` - Link to tickets

### Volunteers Table
- `id` - Primary key
- `name` - Volunteer name
- `email` - Volunteer email
- `phone` - Volunteer phone
- `show_id` - Foreign key to shows
- `signup_date` - Registration timestamp

### Impact Stats Table
- `id` - Primary key
- `pounds_collected` - Total pounds collected
- `meals_provided` - Estimated meals provided
- `shows_participated` - Total shows with food drives

## Updating Impact Statistics

Impact stats are manually updated. Use Flask shell or create an admin endpoint:

```python
from app import app, db
from models import ImpactStats

with app.app_context():
    stats = ImpactStats.query.first()
    stats.pounds_collected = 3000
    stats.meals_provided = 2500
    stats.shows_participated = 20
    db.session.commit()
```

## License

MIT License - House of Hamill
