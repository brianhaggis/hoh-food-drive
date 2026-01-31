import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///fooddrive.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    BANDSINTOWN_API_KEY = os.environ.get('BANDSINTOWN_API_KEY', '')
    RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'houseofhamill@gmail.com')

    # Artist name for BandsInTown API
    ARTIST_NAME = 'House of Hamill'
