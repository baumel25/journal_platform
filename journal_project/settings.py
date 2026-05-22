import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-your-secret-key-here'

DEBUG = False

ALLOWED_HOSTS = ['journal-platform-513m.onrender.com', '.onrender.com', 'localhost', '127.0.0.1']

# Add our apps
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'articles',  # new
    'accounts',  # new
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'journal_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # new
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


# MySQL Database Configuration

# MySQL Database Configuration
DATABASES = {
   'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom user model (if needed)
AUTH_USER_MODEL = 'accounts.CustomUser'

# Login URL
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'home'


# Media files configuration
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Maximum file size for profile pictures (2MB)
DATA_UPLOAD_MAX_NUMBER_FILES = 10
DATA_UPLOAD_MAX_FILE_SIZE = 5242880  # 5MB

# Allowed image types for profile pictures
ALLOWED_PROFILE_PIC_TYPES = ['jpg', 'jpeg', 'png', 'gif', 'svg']

# Session Settings
SESSION_COOKIE_AGE = 3600  # Session expires after 1 hour (in seconds)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True  # Session ends when browser closes
SESSION_SAVE_EVERY_REQUEST = True  # Reset session expiry on each request

# Security Settings for Testing Different Users
# For development only - allows multiple user sessions
CSRF_COOKIE_HTTPONLY = False
CSRF_USE_SESSIONS = True

# Redirect to login page for unauthorized access
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'
