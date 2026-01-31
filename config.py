import os
from dotenv import load_dotenv

load_dotenv()


def get_database_url():
    """Get database URL, converting for psycopg3 compatibility."""
    url = os.environ.get('DATABASE_URL', 'sqlite:///fooddrive.db')
    # Render uses postgres:// but SQLAlchemy + psycopg3 needs postgresql+psycopg://
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql+psycopg://', 1)
    elif url.startswith('postgresql://'):
        url = url.replace('postgresql://', 'postgresql+psycopg://', 1)
    return url


class Config:
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = get_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    BANDSINTOWN_API_KEY = os.environ.get('BANDSINTOWN_API_KEY', '')
    RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'houseofhamill@gmail.com')

    # Artist name for BandsInTown API
    ARTIST_NAME = 'House of Hamill'
