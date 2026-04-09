# Real-Time Django Chat Application - Complete Setup & Testing Guide

## 📋 Table of Contents
1. [Quick Start](#quick-start)
2. [Features Overview](#features-overview)
3. [Architecture](#architecture)
4. [Installation & Setup](#installation--setup)
5. [Database Setup](#database-setup)
6. [Running the Application](#running-the-application)
7. [Testing Guide](#testing-guide)
8. [Troubleshooting](#troubleshooting)
9. [Deployment](#deployment)
10. [Performance Optimization](#performance-optimization)

---

## 🚀 Quick Start

```bash
# 1. Create virtual environment
python -m venv env
source env/Scripts/activate  # On Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run migrations
python manage.py migrate

# 4. Load sample data (optional)
python manage.py shell < chatapp/fixtures.py

# 5. Create sample data (optional)
python manage.py shell
>>> from chatapp.fixtures import create_sample_data
>>> create_sample_data()

# 6. Start development server
python manage.py runserver

# 7. Open browser
# http://localhost:8000
```

---

## ✨ Features Overview

### 1. **Voice Messaging** ✅
- Record voice messages using microphone
- Support for multiple audio formats (WebM, MP3, WAV, OGG)
- Voice playback with progress bar and seek functionality
- Duration tracking and display
- Automatic MIME type detection
- **Real-time**: No page refresh needed after upload

### 2. **Group System** ✅
- Create/join groups using unique codes
- Last activity tracking
- Auto-delete inactive groups (30+ minutes no activity)
- Group member count and online status
- Per-group message history

### 3. **User Tracking** ✅
- Anonymous user tracking via session ID
- User status (online/offline)
- Last seen timestamp
- Active users display in UI
- Automatic timeout detection (30 minutes)
- Activity heartbeat (every 30 seconds)

### 4. **Real-Time Updates** ✅
- AJAX polling for new messages (adaptive interval: 1-3 seconds)
- Online user count updates
- Activity heartbeat for presence
- No WebSocket dependency (polling-based)
- Respects page visibility (stops polling when hidden)

### 5. **Message Handling** ✅
- Support for text messages (max 5000 chars)
- Support for voice messages (max 50MB)
- Message timestamp with proper ordering
- Audio MIME type storage
- Duration metadata for voice messages

### 6. **Delete Functionality** ✅
- Delete for me (individual deletion)
- Delete for everyone (admin deletion)
- Sender verification (only sender can delete for all)
- UI updates instantly without refresh
- Safe deletion from database and file system

### 7. **Performance Optimization** ✅
- Database indexes on frequently queried fields
- Efficient Django ORM queries
- Conditional polling intervals (adaptive)
- Media file cleanup on deletion
- Session-based user management
- Optimized MIME type selection

### 8. **Error Handling** ✅
- Structured JSON responses
- Graceful error messages for users
- File validation (size, format)
- Missing audio file handling
- Browser compatibility checks
- Retry logic for audio initialization

### 9. **Frontend** ✅
- Modern HTML5 with responsive design
- CSS Grid and Flexbox layouts
- Mobile-optimized (100dvh viewport handling)
- Multi-format audio player
- Context menu for message actions
- Confirmation dialogs for destructive actions

---

## 🏗️ Architecture

```
Chat Application Architecture:
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (HTML/CSS/JS)               │
├─────────────────────────────────────────────────────────────┤
│ • Voice Recording (MediaRecorder API)                       │
│ • Audio Playback (HTML5 Audio Element)                      │
│ • Real-time Polling (fetch API)                             │
│ • UI Updates (DOM manipulation)                             │
├─────────────────────────────────────────────────────────────┤
│                   Django Backend REST API                   │
├─────────────────────────────────────────────────────────────┤
│ Views:                                                      │
│ • home() - Landing page                                     │
│ • chat() - Login page                                       │
│ • group() - Chat interface                                  │
│ • upload_voice_message() - Voice upload                     │
│ • send_message_ajax() - Text message                        │
│ • delete_message() - Message deletion                       │
│ • update_user_status() - Presence tracking                  │
│ • get_new_messages() - Message polling                      │
│ • get_online_users() - User list                            │
├─────────────────────────────────────────────────────────────┤
│                    Django Models (SQLite)                   │
├─────────────────────────────────────────────────────────────┤
│ • Group (groups)                                            │
│ • Message (messages)                                        │
│ • AnonymousUser (users)                                     │
├─────────────────────────────────────────────────────────────┤
│                    Media Storage                            │
├─────────────────────────────────────────────────────────────┤
│ • media/voice_messages/ (voice files)                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 Installation & Setup

### Requirements
- Python 3.9+
- pip (Python package manager)
- Modern web browser with:
  - MediaRecorder API (Chrome, Firefox, Edge, Safari 14.1+)
  - Fetch API support
  - HTML5 Audio element

### Step 1: Clone and Setup Environment

```bash
# Navigate to project directory
cd d:\vignesh_django_project\building\ a\ chat\ web\ application\chat\ 3\chatproject

# Create virtual environment
python -m venv env

# Activate environment
# On Windows:
env\Scripts\activate
# On macOS/Linux:
source env/bin/activate
```

### Step 2: Install Dependencies

```bash
# Install from requirements.txt
pip install -r requirements.txt

# Verify installation
pip list
```

**Expected packages:**
- Django==6.0.3
- gunicorn==22.0.0
- whitenoise==6.6.0 (for static files in production)

### Step 3: Configure Settings

Edit `chatproject/settings.py`:

```python
# For development
DEBUG = True
ALLOWED_HOSTS = ['*']

# For production
DEBUG = False
ALLOWED_HOSTS = ['your-domain.com', 'www.your-domain.com']

# CSRF trusted origins
CSRF_TRUSTED_ORIGINS = [
    'https://your-domain.com',
    'https://www.your-domain.com',
]
```

---

## 🗄️ Database Setup

### Initial Migration

```bash
# Create/apply migrations
python manage.py migrate

# If custom migration needed:
python manage.py makemigrations chatapp
python manage.py migrate chatapp
```

### Database Schema

```sql
-- Group table
CREATE TABLE chatapp_group (
    id INTEGER PRIMARY KEY,
    code VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(100),
    created_at DATETIME,
    last_activity DATETIME
);
CREATE INDEX idx_last_activity ON chatapp_group(last_activity);

-- Message table
CREATE TABLE chatapp_message (
    id INTEGER PRIMARY KEY,
    group_id INTEGER,
    user_name VARCHAR(100),
    session_id VARCHAR(255),
    content TEXT,
    message_type VARCHAR(10),
    audio_file VARCHAR(200),
    audio_mime_type VARCHAR(50),
    duration FLOAT,
    is_deleted VARCHAR(20),
    timestamp DATETIME,
    FOREIGN KEY(group_id) REFERENCES chatapp_group(id)
);
CREATE INDEX idx_group_time ON chatapp_message(group_id, timestamp);

-- AnonymousUser table
CREATE TABLE chatapp_anonymoususer (
    id INTEGER PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    user_name VARCHAR(100),
    is_online BOOLEAN,
    last_seen DATETIME,
    created_at DATETIME
);
```

### Load Sample Data

```bash
# Method 1: Using fixtures.py
python manage.py shell
>>> from chatapp.fixtures import create_sample_data
>>> create_sample_data()

# Method 2: Load from JSON
python manage.py loaddata fixtures/sample_data.json
```

---

## ▶️ Running the Application

### Development Server

```bash
# Start development server
python manage.py runserver

# Start on specific port
python manage.py runserver 0.0.0.0:8000

# Output should show:
# ✓ System check identified no issues (0 silenced).
# ✓ Starting development server at http://127.0.0.1:8000/
```

### Access Application

1. Open browser: `http://localhost:8000`
2. Click "Start Chatting"
3. Enter your name and group code
4. Start messaging!

---

## 🧪 Testing Guide

### 1. **Voice Recording Test**

```javascript
// Browser Console Test
1. Click microphone button
2. Allow microphone permission
3. Speak for 5 seconds
4. Release button
5. Verify:
   - ✓ Recording indicator shows
   - ✓ File uploads without page refresh
   - ✓ Message appears in chat with play button
   - ✓ No console errors
```

### 2. **Voice Playback Test**

```javascript
// Browser Console Test
1. Click play button on voice message
2. Verify:
   - ✓ Button changes to pause (⏸️)
   - ✓ Audio plays (listen for sound)
   - ✓ Progress bar updates
   - ✓ Duration countdown shows
   - ✓ Can seek by clicking progress bar
   - ✓ Playback continues on other browser tabs
```

### 3. **Text Message Test**

```javascript
// Browser Console Test
1. Type message: "Hello World"
2. Click send button (or press Enter)
3. Verify:
   - ✓ Message appears in chat immediately
   - ✓ Sender name (your name) shown on left
   - ✓ Timestamp displayed
   - ✓ No page refresh
```

### 4. **Real-Time Updates Test**

```javascript
// Two Browser Windows Test
// Window 1: Group "DEVTEAM" as "Alice"
// Window 2: Group "DEVTEAM" as "Bob"

1. Alice sends: "Hi Bob"
2. Check Window 2: Message appears in <3 seconds
3. Bob sends: "Hi Alice"
4. Check Window 1: Message appears in <3 seconds
5. Both windows show online count: 2 Online
```

### 5. **Message Deletion Test**

```javascript
// Test Delete for Me
1. Right-click your message
2. Select "Delete"
3. Choose "Delete for me"
4. Click "Delete"
5. Verify:
   - ✓ Message shows as deleted for you
   - ✓ Other users still see message
   - ✓ Database only marks it for_me

// Test Delete for Everything (sender only)
1. Right-click your message
2. Select "Delete"
3. Choose "Delete for everyone"
4. Click "Delete"
5. Verify:
   - ✓ Message deleted for all users
   - ✓ Shows "This message was deleted"
   - ✓ Cannot see by right-clicking
```

### 6. **User Status Test**

```javascript
// Online Status Test
1. Join a group as User1
2. Open another tab, join as User2
3. Verify online count: "2 Online"
4. Close User2 tab
5. Wait 30 seconds (heartbeat interval)
6. Verify online count decreases: "1 Online"
```

### 7. **Group Auto-Delete Test**

```bash
# Terminal Test
1. Create group "INACTIVE"
2. Join and send message
3. Leave (don't send any activity)
4. Wait 30 minutes (or modify code for 5 minutes in dev)
5. Run: python manage.py delete_inactive_groups
6. Verify group is deleted:
   python manage.py shell
   >>> from chatapp.models import Group
   >>> Group.objects.filter(code="INACTIVE")
   # Should return empty queryset
```

### 8. **Audio Format Compatibility Test**

```javascript
// Test different audio formats
1. Record voice message
2. Check browser console output:
   "Supported MIME type: audio/webm;codecs=opus"
3. Verify playback works
4. Test fallback MIME types by:
   - Disabling WebM in browser
   - See system use next format in list
```

### 9. **Error Handling Test**

```javascript
// Test Various Error Scenarios:

// A. Microphone Permission Denied
1. Reject microphone access
2. Verify error: "Microphone access was denied"

// B. No Microphone Available
1. Disconnect microphone
2. Try to record
3. Verify error: "No microphone found"

// C. File Too Large
1. Modify code to upload >50MB file
2. Verify error: "Audio file is too large"

// D. Invalid Group Code
1. Try to join non-existent group "ZZZZZZ"
2. Should redirect to create group

// E. Network Error
1. Disable internet during message send
2. Verify error message appears
3. No crash or silent failure
```

### 10. **Performance Stress Test**

```javascript
// Load Testing
1. Create group with 10 simultaneous users
2. Each user sends 100 messages rapidly
3. Measure:
   - Message delivery time (should be <3s)
   - Browser responsiveness (should be smooth)
   - CPU usage (should be reasonable)
   - Memory usage (should not increase indefinitely)
```

---

## 🔧 Troubleshooting

### Issue: "Microphone access was denied"

**Solution:**
```bash
# Check browser security settings:
# 1. Chrome: Settings > Privacy > Site Settings > Microphone
# 2. Firefox: Preferences > Privacy > Permissions > Microphone
# 3. Safari: Websites > Microphone > Allow

# Or: Clear site data and re-grant permission
```

### Issue: "No audio element found" or voice doesn't play

**Solution:**
```python
# Check MIME type support in settings.py:
SUPPORTED_AUDIO_MIMES = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/mp4',
    'audio/ogg;codecs=opus',
    'audio/ogg',
    'audio/wav',
]

# Clear browser cache:
# 1. Right-click > Inspect
# 2. Application > Storage > Clear Site Data
# 3. Reload page
```

### Issue: Messages not updating in real-time

**Solution:**
```python
# Check polling is active:
1. Open Console (F12)
2. Should see: "Starting message polling..."
3. Should see: "Messages fetched" every 1-3 seconds

# If not, check:
- Page visibility (tab not hidden)
- Network tab (requests going out)
- get-messages endpoint responding with 200

# Force polling restart:
>>> location.reload()
```

### Issue: "CSRF token missing" error

**Solution:**
```html
<!-- Verify CSRF token in template -->
{% csrf_token %}

<!-- Should render as: -->
<input type="hidden" name="csrfmiddlewaretoken" value="...">

<!-- In JavaScript, ensure: -->
const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
fetch('/endpoint/', {
    headers: {'X-CSRFToken': csrfToken}
})
```

### Issue: Database locked error (SQLite)

**Solution:**
```bash
# This happens with multiple write operations
# Solutions:
# 1. Restart Django server
python manage.py runserver

# 2. Check for long-running transactions
ps aux | grep manage.py

# 3. For production, use PostgreSQL instead:
# Install: pip install psycopg2
# Update settings.py:
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'chatname',
        'USER': 'chatuser',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### Issue: Voice files not found (404 error)

**Solution:**
```python
# Check media configuration in settings.py:
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Verify URL configuration in project/urls.py:
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [...]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )

# Check file exists:
ls -la media/voice_messages/
```

---

## 🚀 Deployment

### Heroku Deployment

```bash
# 1. Create Procfile
echo "web: gunicorn chatproject.wsgi" > Procfile

# 2. Create runtime.txt
echo "python-3.9.0" > runtime.txt

# 3. Create Heroku app
heroku create your-app-name

# 4. Add environment variables
heroku config:set DEBUG=False
heroku config:set SECRET_KEY=$(openssl rand -base64 32)

# 5. Deploy
git push heroku main

# 6. Run migrations on Heroku
heroku run python manage.py migrate
```

### Render.com Deployment

```bash
# 1. Connect GitHub repository
# 2. Create render.yaml file
# 3. Configure build and start commands
# 4. Deploy

# render.yaml example:
services:
  - type: web
    name: django-chat
    buildCommand: pip install -r requirements.txt && python manage.py migrate
    startCommand: gunicorn chatproject.wsgi:application --bind 0.0.0.0:$PORT
    envVars:
      - key: DEBUG
        value: false
      - key: ALLOWED_HOSTS
        value: your-domain.render.com
```

### Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.9

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["gunicorn", "chatproject.wsgi:application", "--bind", "0.0.0.0:8000"]
```

```bash
# Build and run
docker build -t django-chat .
docker run -p 8000:8000 django-chat
```

---

## ⚡ Performance Optimization

### 1. Database Optimization

```python
# Use select_related() for foreign keys
messages = Message.objects.select_related('group').all()

# Use database indexes (already in models)
class Meta:
    indexes = [
        models.Index(fields=['group', 'timestamp']),
        models.Index(fields=['session_id', 'timestamp']),
    ]

# Limit query results
messages = Message.objects.latest('timestamp')[:100]
```

### 2. Caching

```python
# Add caching to settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-filePath',
    }
}

# Use cache in views
from django.views.decorators.cache import cache_page

@cache_page(60)  # Cache for 60 seconds
def get_online_users(request, code):
    ...
```

### 3. Polling Optimization

```javascript
// Adaptive polling interval
let pollInterval = 1000;  // Start at 1 second
const maxPollInterval = 3000;  // Max 3 seconds
let noNewMessagesCount = 0;

function adjustPollInterval(hasNewMessages) {
    if (hasNewMessages) {
        pollInterval = 1000;  // Reset to 1 second
        noNewMessagesCount = 0;
    } else {
        noNewMessagesCount++;
        if (noNewMessagesCount > 3) {
            pollInterval = Math.min(pollInterval + 500, maxPollInterval);
        }
    }
}
```

### 4. Frontend Optimization

```html
<!-- Lazy load voice messages -->
<audio loading="lazy"></audio>

<!-- Minimize JavaScript execution -->
<!-- Throttle DOM updates -->
let updateTimeout = null;
function updateUI() {
    clearTimeout(updateTimeout);
    updateTimeout = setTimeout(() => {
        // Batch DOM updates
    }, 100);
}

<!-- Use requestAnimationFrame for animations -->
function smoothScroll() {
    requestAnimationFrame(() => {
        messagesScroll.scrollTop = messagesScroll.scrollHeight;
    });
}
```

---

## 📊 Monitoring

### View Active Groups

```bash
python manage.py shell
>>> from chatapp.models import Group
>>> Group.objects.all().values('code', 'created_at', 'last_activity')
```

### View Online Users

```bash
>>> from chatapp.models import AnonymousUser
>>> AnonymousUser.objects.filter(is_online=True)
```

### Message Statistics

```bash
>>> from chatapp.models import Message
>>> Message.objects.filter(message_type='text').count()  # Text messages
>>> Message.objects.filter(message_type='voice').count()  # Voice messages
```

---

## 📝 API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Home page |
| `/chat/` | GET/POST | Login/join group |
| `/group/<code>/` | GET | Chat interface |
| `/group/<code>/send-message/` | POST | Send text message |
| `/group/<code>/upload-voice/` | POST | Upload voice message |
| `/group/<code>/delete-message/` | POST | Delete message |
| `/group/<code>/get-messages/` | GET | Fetch new messages |
| `/group/<code>/update-status/` | POST | Update user online status |
| `/group/<code>/online-users/` | GET | Get list of online users |

---

## 📞 Support & Debugging

### Enable Debug Logging

```python
# In settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
}
```

### Browser Developer Tools

```javascript
// Open Console (F12)
// Check logs:
console.log()  // View all console messages
console.error()  // View errors only

// Network tab:
// Check request/response for each API call

// Application tab:
// Check local storage, session storage, cookies
```

---

## 🎯 Next Steps

1. **Test thoroughly** - Follow testing guide above
2. **Deploy** - Use Heroku, Render, or Docker
3. **Monitor** - Track performance and errors
4. **Scale** - Add WebSocket support with Django Channels for better real-time
5. **Enhance** - Add user authentication, file sharing, encryption, etc.

---

## 📄 License

This chat application is provided as-is for educational purposes.

---

**Last Updated:** April 9, 2026
**Version:** 1.0.0
**Status:** ✅ Production Ready
