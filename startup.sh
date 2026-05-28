#!/bin/bash
# Run database migrations, then start the server
python manage.py migrate --noinput
exec gunicorn journal_project.wsgi:application
