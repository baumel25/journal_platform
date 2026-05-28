#!/usr/bin/env python
"""Run migrations then start gunicorn."""
import subprocess
import sys
import os

# Run migrations
result = subprocess.run([sys.executable, 'manage.py', 'migrate', '--noinput'])
if result.returncode != 0:
    print("Migration failed, but continuing...", file=sys.stderr)

# Start gunicorn
os.execvp('gunicorn', ['gunicorn', 'journal_project.wsgi:application'])
