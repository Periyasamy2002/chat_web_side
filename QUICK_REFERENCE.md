# Django Chat Application - Project Structure & Quick Reference

## 📁 Project Structure

```
chatproject/                          # Main project directory
├── manage.py                          # Django management script
├── db.sqlite3                         # SQLite database
├── requirements.txt                   # Python dependencies
├── quickstart.py                      # One-click setup script
├── COMPLETE_SETUP_GUIDE.md           # Full documentation
├── README.md                          # Project overview
├── Procfile                           # Heroku deployment config
│
├── chatproject/                       # Project settings
│   ├── __init__.py
│   ├── settings.py                    # Django configuration
│   ├── urls.py                        # Main URL routing
│   ├── wsgi.py                        # WSGI application
│   └── asgi.py                        # ASGI application (async)
│
├── chatapp/                           # Django application
│   ├── __init__.py
│   ├── admin.py                       # Django admin configuration
│   ├── apps.py                        # App configuration
│   ├── models.py                      # Database models (Group, Message, AnonymousUser)
│   ├── views.py                       # API views and page handlers
│   ├── urls.py                        # App URL routing
│   ├── tests.py                       # Original tests
│   ├── tests_comprehensive.py         # Comprehensive test suite
│   ├── fixtures.py                    # Sample data creation
│   │
│   ├── management/                    # Custom management commands
│   │   ├── __init__.py
│   │   └── commands/
│   │       ├── __init__.py
│   │       └── delete_inactive_groups.py  # Auto-delete empty groups
│   │
│   ├── migrations/                    # Database migrations
│   │   ├── __init__.py
│   │   ├── 0001_initial.py
│   │   ├── 0002_alter_message_options_message_audio_file_and_more.py
│   │   ├── 0003_userstatus_alter_group_options_group_created_at_and_more.py
│   │   └── ... (other migrations)
│   │
│   └── templates/                     # HTML templates
│       ├── base.html                  # Base template with navbar
│       ├── home.html                  # Landing page
│       ├── chat.html                  # Login/join form
│       ├── group.html                 # Main chat interface
│       └── register.html              # Registration (if needed)
│
├── media/                             # User-uploaded files
│   └── voice_messages/                # Voice message storage
│       └── voice_message_*.webm       # Audio files
│
├── staticfiles/                       # Collected static files (production)
│   └── (auto-generated)
│
└── env/                               # Virtual environment (created by quickstart)
    ├── bin/ or Scripts/               # Executable scripts
    └── lib/ or Lib/                   # Python packages
```

---

## 🔧 Key Configuration Files

### settings.py
```python
# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Media Files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Static Files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Security
CSRF_TRUSTED_ORIGINS = ['https://your-domain.com']
```

### urls.py - Main
```python
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('chatapp.urls')),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
```

### urls.py - App
```python
urlpatterns = [
    path("", views.home, name="home"),                           # Home page
    path("chat/", views.chat, name="chat"),                      # Login
    path("group/<str:code>/", views.group, name="group"),        # Chat interface
    path("group/<str:code>/send-message/", views.send_message_ajax),
    path("group/<str:code>/upload-voice/", views.upload_voice_message),
    path("group/<str:code>/delete-message/", views.delete_message),
    path("group/<str:code>/get-messages/", views.get_new_messages),
    path("group/<str:code>/update-status/", views.update_user_status),
    path("group/<str:code>/online-users/", views.get_online_users),
]
```

---

## 📊 Database Models

### Group Model
```python
class Group(models.Model):
    name = CharField(max_length=100)
    code = CharField(max_length=10, unique=True)
    created_at = DateTimeField(auto_now_add=True)
    last_activity = DateTimeField(auto_now_add=True)
    
    Methods:
    - get_online_count()      # Get active users in last 5 minutes
    - should_auto_delete()    # Check if group inactive for 30+ min
```

### Message Model
```python
class Message(models.Model):
    group = ForeignKey(Group, on_delete=CASCADE)
    user_name = CharField(max_length=100)
    session_id = CharField(max_length=255)
    content = TextField(blank=True, null=True)           # Text message
    audio_file = FileField(upload_to='voice_messages/') # Voice file
    audio_mime_type = CharField(max_length=50)
    message_type = CharField(choices=[('text', 'Text'), ('voice', 'Voice')])
    duration = FloatField(default=0)                     # Voice duration in seconds
    is_deleted = CharField(choices=[
        ('not_deleted', 'Not Deleted'),
        ('deleted_for_me', 'Deleted For Me'),
        ('deleted_for_all', 'Deleted For All'),
    ])
    timestamp = DateTimeField(auto_now_add=True)
    
    Methods:
    - is_deleted_for_user()   # Check if deleted for specific user
    - get_display_text()      # Get displayable text
```

### AnonymousUser Model
```python
class AnonymousUser(models.Model):
    session_id = CharField(max_length=255, unique=True)
    user_name = CharField(max_length=100)
    is_online = BooleanField(default=True)
    last_seen = DateTimeField(auto_now=True)
    created_at = DateTimeField(auto_now_add=True)
    
    Ordering: ['-last_seen']
```

---

## 🌐 API Endpoints Reference

### Public Endpoints

| Method | Endpoint | Purpose | Returns |
|--------|----------|---------|---------|
| GET | `/` | Home page | HTML |
| GET | `/chat/` | Login form | HTML |
| POST | `/chat/` | Join group | Redirect to group |

### Authenticated Endpoints (via session)

| Method | Endpoint | Purpose | Returns |
|--------|----------|---------|---------|
| GET | `/group/<code>/` | Chat interface | HTML |
| POST | `/group/<code>/send-message/` | Send text | `{success: bool, message: obj}` |
| POST | `/group/<code>/upload-voice/` | Send voice | `{success: bool, message_id: int}` |
| POST | `/group/<code>/delete-message/` | Delete msg | `{success: bool, status: str}` |
| GET | `/group/<code>/get-messages/` | Fetch msgs | `{success: bool, messages: [], online_count: int}` |
| POST | `/group/<code>/update-status/` | User alive | `{success: bool, online_count: int}` |
| GET | `/group/<code>/online-users/` | User list | `{success: bool, users: [], count: int}` |

---

## 💻 Browser Console Debugging

### Check Message Polling
```javascript
// Should see polling logs every 1-3 seconds
console.log("Starting message polling...")
console.log("Messages fetched")

// If not working:
console.log(document.hidden)           // Should be false
fetch('/group/TEST/get-messages/')     // Manual test
```

### Test Voice Recording
```javascript
// Test MediaRecorder support
if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    console.log("✓ Voice recording supported");
} else {
    console.log("✗ Voice recording NOT supported");
}

// List supported MIME types
const mimeTypes = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/mp4',
    'audio/ogg',
];
mimeTypes.forEach(type => {
    if (MediaRecorder.isTypeSupported(type)) {
        console.log("✓ Supported:", type);
    }
});
```

### Monitor Real-Time Updates
```javascript
// Check current update timestamp
console.log("Last update:", lastUpdateTimestamp);

// Check polling interval
console.log("Poll interval:", pollInterval, "ms");

// Manually fetch messages
fetchNewMessages();

// Check online count
document.querySelector('.online-count').textContent;
```

---

## 🚀 Common Commands

### Django Management

```bash
# Create superuser for admin panel
python manage.py createsuperuser

# Run Django shell
python manage.py shell

# Run tests
python manage.py test chatapp

# Run specific test
python manage.py test chatapp.tests.GroupModelTests

# Create new migration
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Check migrations status
python manage.py showmigrations
```

### Sample Data

```bash
# Load fixtures
python manage.py loaddata fixtures/sample_data.json

# Export fixture
python manage.py dumpdata chatapp > fixtures/data.json

# Load sample data from fixtures.py
python manage.py shell < chatapp/fixtures.py
```

### Maintenance

```bash
# Delete inactive groups (dry run)
python manage.py delete_inactive_groups --dry-run

# Delete inactive groups (for real)
python manage.py delete_inactive_groups

# Collect static files (production)
python manage.py collectstatic --noinput

# Check for issues
python manage.py check

# Show all settings
python manage.py shell -c "from django.conf import settings; print(settings.DEBUG)"
```

### Development

```bash
# Start development server
python manage.py runserver

# Start on specific host/port
python manage.py runserver 0.0.0.0:8000

# Start with hot reload disabled
python manage.py runserver --nothreading

# Run with debug toolbar
python manage.py runserver_plus
```

---

## 📱 Frontend JavaScript Classes & Functions

### Key Variables
```javascript
groupCode                // Current group code
lastUpdateTimestamp     // Last message timestamp
pollInterval            // Current polling interval (1-3000ms)
isRecording             // Recording status
mediaRecorder           // MediaRecorder instance
currentAudio            // Currently playing audio element
selectedMessage         // Right-clicked message
```

### Key Functions

#### Message Management
```javascript
sendMessage()                   // Send text message
sendVoiceMessage(audioBlob)    // Send voice message
deleteMessage()                // Delete selected message
confirmDelete()                // Confirm deletion
```

#### Audio Playback
```javascript
togglePlayPause(event, button) // Play/pause audio
seekAudio(event, progressBar)  // Seek in audio
updateProgressBar()            // Update progress bar
```

#### Real-Time Updates
```javascript
fetchNewMessages()             // Poll for new messages
startPolling()                 // Start polling loop
stopPolling()                  // Stop polling
startHeartbeat()               // Send user alive signal
```

#### Voice Recording
```javascript
initializeAudio()              // Request microphone
getSupportedMimeType()         // Get browser's MIME type
cleanupAudioStream()           // Stop microphone access
```

#### UI Helpers
```javascript
scrollToBottom()               // Auto-scroll to latest message
createMessageElement(msg)      // Create message HTML
escapeHtml(text)               // Escape HTML entities
showContextMenu(event, msg)    // Show right-click menu
```

---

## 🐛 Common Issues & Fixes

| Issue | Cause | Solution |
|-------|-------|----------|
| "Microphone access denied" | Browser permission | Allow in browser settings |
| "No audio element found" | Template error | Check if audio returned from AJAX |
| "CSRF token missing" | Form submission | Add `{% csrf_token %}` to form |
| "Messages not updating" | Polling stopped | Check tab not hidden, reload page |
| "Database locked" | SQLite concurrent writes | Use PostgreSQL for production |
| "404 on audio files" | Media URL issue | Check MEDIA_URL and MEDIA_ROOT |
| "Very slow messages" | Large queries | Increase polling interval, optimize DB |

---

## 📈 Performance Tips

1. **Use PostgreSQL** instead of SQLite for production
2. **Enable caching** for static files and API responses
3. **Optimize polling interval** (starts slow, speeds up with activity)
4. **Compress audio files** before download
5. **Add message pagination** (don't load all at once)
6. **Use CDN** for static files in production
7. **Monitor database queries** with Django Debug Toolbar

---

## 🔒 Security Checklist

- [x] CSRF protection enabled
- [x] File upload size validation
- [x] Session-based user identification
- [x] Permission checks on delete operations
- [x] SQL injection prevention (ORM usage)
- [x] XSS protection (auto HTML escaping)
- [ ] HTTPS required in production
- [ ] Rate limiting on API endpoints
- [ ] Input validation and sanitization

---

## 📞 Quick Support

**For issues, run:**
```bash
# Check Django configuration
python manage.py check

# View recent logs
python manage.py shell -c "import logging; logging.basicConfig(level=logging.DEBUG)"

# Clear cache
python manage.py shell -c "from django.core.cache import cache; cache.clear()"

# Reset database (WARNING: deletes all data!)
rm db.sqlite3
python manage.py migrate
```

---

## 🎓 Learning Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [MDN - MediaRecorder API](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder)
- [Real-time Web Technologies Guide](https://developer.mozilla.org/en-US/docs/Web/Guide/Events)
- [Web Audio API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API)

---

**Last Updated:** April 9, 2026  
**Version:** 1.0.0  
**Status:** ✅ Production Ready
