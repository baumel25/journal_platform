web: gunicorn journal_project.wsgi:application --bind 0.0.0.0:${PORT:-8000} --log-level info --timeout 120
release: python manage.py migrate --noinput
