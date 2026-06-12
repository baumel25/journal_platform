#!/usr/bin/env python
"""Run migrations then start gunicorn."""
import subprocess
import sys
import os

print("=== Starting Railway deployment ===", flush=True)

# Run migrations
print("Running migrations...", flush=True)
result = subprocess.run([sys.executable, 'manage.py', 'migrate', '--noinput'], capture_output=True, text=True)
if result.returncode != 0:
    print(f"Migration stdout: {result.stdout}", flush=True)
    print(f"Migration stderr: {result.stderr}", flush=True)
else:
    print("Migrations complete.", flush=True)

# Collect static files
print("Collecting static files...", flush=True)
result = subprocess.run([sys.executable, 'manage.py', 'collectstatic', '--noinput', '--clear'], capture_output=True, text=True)
if result.returncode != 0:
    print(f"Collectstatic stdout: {result.stdout}", flush=True)
    print(f"Collectstatic stderr: {result.stderr}", flush=True)
else:
    print("Static files collected.", flush=True)

# Start gunicorn — use PORT env variable (Railway, Koyeb, Render, etc.)
port = os.environ.get('PORT', '8000')
print(f"Starting gunicorn on 0.0.0.0:{port}...", flush=True)
os.execvp('gunicorn', ['gunicorn', '--bind', f'0.0.0.0:{port}', '--log-level', 'info', '--access-logfile', '-', 'journal_project.wsgi:application'])
