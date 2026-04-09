# Production Deployment Guide - Django Chat Application

## 🚀 Pre-Deployment Checklist

### Security
- [ ] Set `DEBUG = False` in settings.py
- [ ] Change `SECRET_KEY` to a random value
- [ ] Set `ALLOWED_HOSTS` to your domain(s)
- [ ] Configure HTTPS with SSL certificate
- [ ] Set secure cookie flags
- [ ] Enable CSRF protection
- [ ] Add CORS headers if needed
- [ ] Set up rate limiting

### Database
- [ ] Switch from SQLite to PostgreSQL
- [ ] Set up database backups
- [ ] Configure connection pooling
- [ ] Run migrations on production
- [ ] Test database recovery

### Storage
- [ ] Set up cloud storage (S3, Azure, etc.) for uploads
- [ ] Configure media file retention policy
- [ ] Set up file cleanup scheduler
- [ ] Test file upload/retrieval

### Monitoring
- [ ] Set up error logging (Sentry, etc.)
- [ ] Configure performance monitoring
- [ ] Set up uptime monitoring
- [ ] Configure log aggregation
- [ ] Set up alerts

---

## 📋 Step-by-Step Deployment

### 1. Prepare Environment

#### a) Clone Repository
```bash
git clone <repository-url> chat-app
cd chat-app
```

#### b) Set Up Python Environment
```bash
# Create virtual environment
python -m venv venv

# Activate
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate      # Windows
```

#### c) Install Dependencies
```bash
pip install -r requirements.txt

# Add production dependencies
pip install psycopg2-binary  # PostgreSQL adapter
pip install gunicorn         # WSGI server
pip install django-cors-headers  # CORS support
pip install sentry-sdk       # Error tracking
pip install django-environ   # Environment variables
```

### 2. Configure Production Settings

#### a) Environment Variables
Create `.env` file:
```bash
DEBUG=False
SECRET_KEY=your-random-secret-key-here
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DATABASE_URL=postgresql://user:password@localhost/chatdb
STATIC_ROOT=/path/to/staticfiles
MEDIA_ROOT=/path/to/media
```

#### b) Update settings.py
```python
import os
import environ
from pathlib import Path

env = environ.Env()
environ.Env.read_env()

DEBUG = env('DEBUG', default=False)
SECRET_KEY = env('SECRET_KEY')
ALLOWED_HOSTS = env('ALLOWED_HOSTS').split(',')

# Database (PostgreSQL)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME', default='chatdb'),
        'USER': env('DB_USER', default='chatuser'),
        'PASSWORD': env('DB_PASSWORD', default=''),
        'HOST': env('DB_HOST', default='localhost'),
        'PORT': env('DB_PORT', default='5432'),
    }
}

# Security settings
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_SECURITY_POLICY = {
    'default-src': ("'self'",),
}

# Error tracking (Sentry)
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

sentry_sdk.init(
    dsn=env('SENTRY_DSN', default=''),
    integrations=[DjangoIntegration()],
    traces_sample_rate=1.0,
    send_default_pii=False
)

# Static files (WhiteNoise)
STATIC_URL = '/static/'
STATIC_ROOT = env('STATIC_ROOT', default=BASE_DIR / 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = env('MEDIA_ROOT', default=BASE_DIR / 'media')
```

### 3. Prepare Database

#### a) Create PostgreSQL Database
```bash
# As superuser
sudo -u postgres psql

# In psql
CREATE DATABASE chatdb;
CREATE USER chatuser WITH PASSWORD 'your-secure-password';
ALTER ROLE chatuser SET client_encoding TO 'utf8';
ALTER ROLE chatuser SET default_transaction_isolation TO 'read committed';
ALTER ROLE chatuser SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE chatdb TO chatuser;
\q
```

#### b) Run Migrations
```bash
python manage.py migrate
```

#### c) Create Superuser
```bash
python manage.py createsuperuser
```

### 4. Collect Static Files
```bash
python manage.py collectstatic --noinput
```

### 5. Configure Web Server

#### Option A: Heroku Deployment

Create `Procfile`:
```
web: gunicorn chatproject.wsgi:application --log-file -
release: python manage.py migrate
```

Create `runtime.txt`:
```
python-3.9.18
```

Deploy:
```bash
heroku create your-app-name
heroku config:set DEBUG=False
heroku config:set SECRET_KEY=$(openssl rand -base64 32)
git push heroku main
heroku run python manage.py migrate
```

#### Option B: Render.com Deployment

Create `render.yaml`:
```yaml
services:
  - type: web
    name: django-chat
    env: python
    plan: standard
    buildCommand: pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput
    startCommand: gunicorn chatproject.wsgi:application --timeout 60 --workers 3 --worker-class sync
    envVars:
      - key: DEBUG
        value: false
      - key: SECRET_KEY
        value: your-secret-key
      - key: ALLOWED_HOSTS
        value: your-domain.onrender.com
      - key: DATABASE_URL
        value: your-database-url
```

#### Option C: AWS/EC2 Deployment

Install dependencies:
```bash
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip postgresql postgresql-contrib nginx supervisor
```

Create service file `/etc/systemd/system/gunicorn-chat.service`:
```ini
[Unit]
Description=Gunicorn application server for chat app
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/chat-app
ExecStart=/var/www/chat-app/venv/bin/gunicorn \
    --timeout 60 \
    --workers 3 \
    --worker-class sync \
    --bind unix:/run/gunicorn.sock \
    chatproject.wsgi:application

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl start gunicorn-chat
sudo systemctl enable gunicorn-chat
```

Configure Nginx:
```nginx
upstream django {
    server unix:/run/gunicorn.sock;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    client_max_body_size 50M;

    location /static/ {
        alias /var/www/chat-app/staticfiles/;
    }

    location /media/ {
        alias /var/www/chat-app/media/;
    }

    location / {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    # SSL (with Let's Encrypt)
    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
}
```

#### Option D: Docker Deployment

Create `Dockerfile`:
```dockerfile
FROM python:3.9

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Run gunicorn
EXPOSE 8000
CMD ["gunicorn", "chatproject.wsgi:application", "--bind", "0.0.0.0:8000"]
```

Create `docker-compose.yml`:
```yaml
version: '3.8'

services:
  db:
    image: postgres:13
    environment:
      POSTGRES_DB: chatdb
      POSTGRES_USER: chatuser
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  web:
    build: .
    command: gunicorn chatproject.wsgi:application --bind 0.0.0.0:8000
    ports:
      - "8000:8000"
    environment:
      DEBUG: "False"
      SECRET_KEY: "your-secret-key"
      DATABASE_URL: "postgresql://chatuser:password@db:5432/chatdb"
    depends_on:
      - db
    volumes:
      - ./media:/app/media

volumes:
  postgres_data:
```

Deploy:
```bash
docker-compose build
docker-compose up -d
docker-compose exec web python manage.py migrate
```

### 6. Set Up SSL Certificate

Using Let's Encrypt:
```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot certonly --nginx -d yourdomain.com -d www.yourdomain.com
sudo certbot renew --dry-run  # Test auto-renewal
```

### 7. Configure Backups

#### Database Backup
```bash
# Create backup
pg_dump chatdb > backup_$(date +%Y%m%d).sql

# Restore backup
psql chatdb < backup_20260409.sql
```

#### Media Files Backup
```bash
# Backup strategy
tar -czf media_backup_$(date +%Y%m%d).tar.gz media/

# Upload to cloud storage
aws s3 cp media_backup_*.tar.gz s3://your-backup-bucket/
```

### 8. Set Up Monitoring & Logging

#### Sentry Error Tracking
```python
# In settings.py (already configured above)
import sentry_sdk
sentry_sdk.init(dsn='your-sentry-dsn')
```

#### CloudWatch Logs (AWS)
```python
import logging
import watchtower

handler = watchtower.CloudWatchLogHandler()
logging.getLogger("django").addHandler(handler)
```

#### Uptime Monitoring
```bash
# Using UptimeRobot, Pingdom, or similar
# Configure to ping your application regularly
```

---

## 🚨 Post-Deployment Tasks

### Verify Deployment
```bash
# Test application
curl https://yourdomain.com/
echo $?  # Should be 0

# Test admin panel
curl https://yourdomain.com/admin/

# Test API
curl -X GET https://yourdomain.com/group/TEST/get-messages/
```

### Configure Auto-Deletion Cron Job
```bash
# Edit crontab
crontab -e

# Add (runs every 5 minutes)
*/5 * * * * cd /path/to/project && python manage.py delete_inactive_groups

# Or using systemd timer
# Create /etc/systemd/system/cleanup-groups.service
# and /etc/systemd/system/cleanup-groups.timer
```

### Monitor Performance
```bash
# Check CPU/Memory
top
ps aux | grep gunicorn

# Check database connections
psql -U postgres -d chatdb -c "SELECT count(*) FROM pg_stat_activity;"

# Check logs
tail -f /var/log/syslog
```

---

## 🔧 Troubleshooting Production Issues

### Application Not Starting
```bash
# Check logs
journalctl -u gunicorn-chat -f

# Check migrations
python manage.py showmigrations

# Check ALLOWED_HOSTS
grep ALLOWED_HOSTS chatproject/settings.py
```

### Database Connection Issues
```bash
# Check PostgreSQL service
systemctl status postgresql

# Test connection
psql -h localhost -U chatuser -d chatdb

# Check Django connection
python manage.py dbshell
```

### Static Files Not Loading
```bash
# Recollect static files
python manage.py collectstatic --noinput

# Check permissions
ls -la staticfiles/

# Check Nginx configuration
nginx -t
```

### High Memory Usage
```bash
# Check for memory leaks
free -h

# Monitor processes
watch -n 1 'ps aux | grep gunicorn'

# Increase swap if needed
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Database Performance Issues
```bash
# Check slow queries
SHOW log_min_duration_statement;
SET log_min_duration_statement = 1000;  # Log queries > 1000ms

# Create indexes
python manage.py sqlsequencereset chatapp | python manage.py shell

# Analyze query plans
EXPLAIN ANALYZE SELECT * FROM chatapp_message WHERE group_id = 1;
```

---

## 📊 Performance Optimization

### Database
```python
# Use select_related() and prefetch_related()
messages = Message.objects.select_related('group').all()

# Add database indexes
class Meta:
    indexes = [
        models.Index(fields=['group', 'timestamp']),
    ]

# Use database connection pooling
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'CONN_MAX_AGE': 600,  # Keep connections for 10 min
    }
}
```

### Caching
```python
# Cache message queries
from django.views.decorators.cache import cache_page

@cache_page(60)
def get_messages():
    ...

# Cache group info
from django.core.cache import cache
cache.set('group_info', info, 300)
```

### Frontend
```html
<!-- Lazy load images -->
<img loading="lazy" src="..." />

<!-- Compress resources -->
gzip_types text/css text/javascript application/json;
gzip_min_length 1024;

<!-- Use CDN for static files -->
STATIC_URL = 'https://cdn.example.com/static/'
```

---

## 🔐 Security Hardening

### Rate Limiting
```python
# Install django-ratelimit
pip install django-ratelimit

# Use in views
from django_ratelimit.decorators import ratelimit

@ratelimit(key='ip', rate='100/h', method='POST')
def send_message(request):
    ...
```

### CORS Configuration
```python
# Install django-cors-headers
pip install django-cors-headers

# In settings.py
INSTALLED_APPS = [
    'corsheaders',
    ...
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    ...
]

CORS_ALLOWED_ORIGINS = [
    "https://yourdomain.com",
]
```

### Content Security Policy
```python
SECURE_CONTENT_SECURITY_POLICY = {
    'default-src': ("'self'",),
    'script-src': ("'self'", "'unsafe-inline'"),
    'style-src': ("'self'", "'unsafe-inline'"),
    'img-src': ("'self'", 'data:'),
    'media-src': ("'self'", 'blob:'),
}
```

---

## 📞 Support & Maintenance

### Regular Tasks
- [ ] Monitor error logs daily
- [ ] Check disk space weekly
- [ ] Review database backups weekly
- [ ] Update dependencies monthly
- [ ] Review security updates immediately

### Emergency Contacts
- Database Admin: ...
- System Admin: ...
- Project Lead: ...

---

**Last Updated:** April 9, 2026  
**Version:** 1.0.0  
**Deployment Status:** ✅ Ready for Production
