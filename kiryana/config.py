import os
from dotenv import load_dotenv

load_dotenv()

def database_url():
    url = os.environ.get('DATABASE_URL', 'postgresql+pg8000://postgres:password@localhost/kiryana')
    if url.startswith('postgresql://'):
        return url.replace('postgresql://', 'postgresql+pg8000://', 1)
    return url

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-change-in-production')

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
