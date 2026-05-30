#!/usr/bin/env python
"""Run migrations then start gunicorn."""
import subprocess
import sys
import os

# Run migrations
result = subprocess.run([sys.executable, 'manage.py', 'migrate', '--noinput'])
if result.returncode != 0:
    print("Migration failed, but continuing...", file=sys.stderr)

# Start gunicorn — use PORT env variable (Koyeb, Render, etc.)
port = os.environ.get('PORT', '8000')
os.execvp('gunicorn', ['gunicorn', '--bind', f'0.0.0.0:{port}', 'journal_project.wsgi:application'])
