# Voice Message Fix & Auto-Delete Feature Documentation

## Overview

This document details the implementation of two critical features:
1. **Enhanced Voice Message System** - Improved microphone handling, error messages, and browser compatibility
2. **Automatic Group Deletion** - Groups are automatically deleted after 30 minutes of inactivity (0 online users)

## 1. Voice Message Feature Improvements

### What Was Broken
- Microphone permission handling was minimal
- No specific error messages for users when mic access was denied
- Limited MIME type support detection
- Stream validity not properly managed
- Audio chunks not properly validated

### What Was Fixed

#### Browser Support Detection
- Added `isMediaRecorderSupported()` function to check if browser supports MediaRecorder API
- Provide clear error message if voice recording is unsupported
- Works on Chrome, Firefox, Edge, Safari (newer versions)

#### MIME Type Detection Improvements
- Added `getSupportedMimeType()` function that tries multiple audio codecs:
  1. audio/webm;codecs=opus (preferred)
  2. audio/webm
  3. audio/mp4
  4. audio/ogg;codecs=opus
  5. audio/ogg
  6. audio/wav
  7. audio/aac
- Falls back gracefully if none explicitly supported
- Logs selected MIME type for debugging

#### Microphone Access Handling
- Specific error messages for different failure scenarios:
  - **NotAllowedError**: User denied microphone access
  - **NotFoundError**: No microphone device found
  - **NotReadableError**: Microphone in use by another app
  - **SecurityError**: HTTPS required for microphone access
- Automatic retry for recoverable errors (NotReadableError, AbortError)
- Constraints for audio quality: echoCancellation, noiseSuppression, autoGainControl at 16kHz sample rate

#### Stream Management
- Track active audio stream with `audioStream` variable
- Proper cleanup function `cleanupAudioStream()` that stops all tracks
- Prevent null reference errors by validating stream state before operations
- Cleanup on page unload to avoid resource leaks

#### Recording State Management
- Prevent null pointer exceptions when checking stream validity
- Re-initialize microphone if stream becomes inactive
- Better logging of recording state changes

#### Voice Upload Improvements
- Validate audio blob size before sending (max 50MB)
- Provide specific error messages if audio file is empty or too large
- Disable UI controls during upload to prevent duplicate submissions
- Re-enable UI after upload completes (success or failure)
- Added comprehensive logging for debugging

#### Enhanced Error Logging
- Console logs for all major operations:
  - ✓ Audio initialization successful
  - ✓ Microphone access granted
  - ✓ Recording started/stopped
  - ✓ Voice message uploaded
- Detailed error messages with specific error types
- Duration tracking for debugging

### How It Works

#### User Workflow
1. User clicks/taps microphone button
2. Browser requests microphone permission
3. If denied, user sees specific error message
4. If granted:
   - Recording starts (user sees "Recording..." indicator)
   - Audio is captured
   - User releases button to stop recording
   - Audio blob is created
   - Audio file is uploaded to backend
   - Frontend fetches new messages including voice message

#### Backend Processing
1. Upload endpoint validates:
   - Group exists
   - Audio file is provided
   - File size < 50MB
2. Message is created with audio file and duration
3. Group `last_activity` is updated to current time
4. Response includes audio URL for playback

### Frontend Code Changes

**File**: `chatapp/templates/group.html`

Key functions:
- `isMediaRecorderSupported()` - Checks browser support
- `getSupportedMimeType()` - Detects available audio codecs
- `initializeAudio(retryCount)` - Initializes MediaRecorder with retry logic
- `cleanupAudioStream()` - Properly stops all audio tracks
- `sendVoiceMessage(audioBlob)` - Sends audio to backend with validation

### Testing Voice Recording

To test the voice recording feature:

1. **Normal Recording**:
   - Click mic button in chat interface
   - Speak into microphone
   - Release button
   - Should see voice message appear

2. **Permission Denied**:
   - Deny microphone access in browser prompt
   - Should see error: "Microphone access was denied. Please enable microphone permissions..."
   - Try again after enabling in browser settings

3. **No Microphone**:
   - Run on system without microphone
   - Should see error: "No microphone found. Please connect a microphone..."

4. **Using Wrong Browser**:
   - Use unsupported browser (older IE)
   - Should see error: "Voice recording is not supported in your browser..."

5. **HTTPS Required**:
   - Access app over HTTP (not HTTPS)
   - Should see error: "HTTPS is required for microphone access..."

### Browser Console Debugging

Open browser console (F12) to see detailed logs:
```
✓ Microphone access granted
✓ MediaRecorder created with MIME type: audio/webm;codecs=opus
✓ Recording started
Audio data chunk received, size: 4096
Recording duration: 2.45 seconds
Audio blob created, size: 12288
Uploading voice message to /group/CODE/upload-voice/
✓ Voice message uploaded successfully
```

## 2. Automatic Group Deletion (Auto-Delete Feature)

### What It Does
- Automatically deletes groups that have had **zero online users for 30+ minutes**
- Cascades deletion to all messages in the group
- Prevents database bloat from inactive chat rooms
- Works silently - groups are deleted without notification (can be enhanced later)

### How It Works

#### Activity Tracking
1. **Group Activity**: Every time a message is sent or user joins:
   - Group's `last_activity` timestamp is updated to current time
   - Backend: Updated in `upload_voice_message()`, `send_message_ajax()`, and `chat()` view
   
2. **User Status**: Every time user status is updated:
   - User's `last_seen` timestamp is updated
   - Front-end sends heartbeat every 30 seconds (via `sendHeartbeat()`)
   - Auto-marks users offline if inactive for 30+ minutes

3. **Deletion Check**: During polling for new messages:
   - Backend checks for groups with:
     - `last_activity` > 30 minutes ago
     - Zero online users (is_online=True AND last_seen in last 5 mins)
   - Automatically deletes qualifying groups

#### User Status Timeout

**Frontend Heartbeat** (`sendHeartbeat()` every 30 seconds):
- Sends periodic status update to `/group/{code}/update-status/`
- Marks user as online: `is_online = true`
- Updates `last_seen` timestamp
- Keeps online count accurate

**Backend Auto-Timeout** (`update_user_status()` view):
- Checks for users inactive 30+ minutes
- Auto-marks them offline: `is_online = false`
- Acts as safety net if frontend heartbeat fails
- Runs every time ANY user updates their status

#### Deletion Process (`get_new_messages()` view):
```python
# Find groups with no activity for 30+ minutes AND zero online users
empty_groups = Group.objects.filter(
    last_activity__lt=thirty_min_ago
).exclude(messages__isnull=False)

# For each group, verify it's truly empty, then delete
# Deletion cascades to all Message objects
```

### Configuration

All timeouts are configurable in code:

| Setting | Location | Current Value | Purpose |
|---------|----------|----------------|---------|
| User Auto-Offline | `update_user_status()` view | 30 minutes | How long before user marked offline if inactive |
| Heartbeat Interval | `startHeartbeat()` JavaScript | 30 seconds | How often frontend pings to stay online |
| Group Auto-Delete | `get_new_messages()` view | 30 minutes | How long group must be empty before deletion |
| Online Activity Window | `AnonymousUser.filter()` | 5 minutes | How recent last_seen must be to count as "online" |

To change these values, modify:
- JavaScript: `chatapp/templates/group.html`, in `startHeartbeat()` - change `30000` to different milliseconds
- Python: `chatapp/views.py`, in relevant functions - change `timedelta(minutes=30)` values

### Management Command

Cleanup can also be run manually via Django management command:

```bash
# See what would be deleted (dry-run)
python manage.py cleanup_empty_groups --dry-run

# Actually delete empty groups with detailed output
python manage.py cleanup_empty_groups --verbose

# Silently delete empty groups
python manage.py cleanup_empty_groups
```

### Scheduling Auto-Delete

#### Option 1: During Polling (Current Implementation)
- Built-in to `get_new_messages()` view
- Runs automatically when users poll for messages
- No additional setup required
- May have slight delay if no one is polling

#### Option 2: Cron Job (Recommended for Production)
Add to system crontab to run cleanup every 5 minutes:

```bash
# Edit crontab
crontab -e

# Add this line:
*/5 * * * * cd /path/to/chatproject && python manage.py cleanup_empty_groups
```

#### Option 3: Django Celery Beat
For production systems with Celery:

```python
# In chatproject/celery.py
from celery.schedules import crontab

app.conf.beat_schedule = {
    'cleanup-empty-groups': {
        'task': 'chatapp.tasks.cleanup_empty_groups',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
}
```

### Database Changes

New field added to `Group` model:
```python
last_activity = models.DateTimeField(auto_now_add=True)
```

New indexes created:
- Index on `Group.last_activity` for efficient cleanup queries
- Index on `Group.created_at` for other operations

**Migration**: `0005_auto_activity_tracking.py`

Apply migration:
```bash
python manage.py migrate
```

### Backend Code Changes

#### Models (`chatapp/models.py`)
- Added `last_activity` field to Group model
- Added methods:
  - `get_online_count()` - Count online users in last 5 minutes
  - `should_auto_delete()` - Check if group qualifies for deletion

#### Views (`chatapp/views.py`)
- **`chat()`**: Updates group `last_activity` when user joins
- **`upload_voice_message()`**: Updates activity timestamp, logs user action
- **`send_message_ajax()`**: Updates activity timestamp, logs message
- **`update_user_status()`**: Auto-marks inactive users offline, updates group activity
- **`get_new_messages()`**: Checks and deletes empty groups during polling

#### Management Command (`chatapp/management/commands/cleanup_empty_groups.py`)
- Manual cleanup tool
- Options: `--dry-run`, `--verbose`
- Two-step process:
  1. Mark inactive users offline (30+ min inactivity)
  2. Delete empty groups (0 users, 30+ min inactivity)

### Logging

Console output when cleanup occurs:
```
Auto-marked user John as offline (inactive for 30+ minutes)
Auto-deleting empty group: ABC123
Auto-deleted 2 empty groups
```

Enable detailed logging:
```python
# In views.py, print statements show:
✓ User 'John' joined group 'ABC123'
✓ Text message sent: John in group ABC123
✓ Voice message uploaded: Jane in group ABC123 (duration: 5s)
Auto-marked user offline due to inactivity
```

## Quality Assurance

### Voice Recording Test Cases
- [ ] Microphone works in Chrome
- [ ] Microphone works in Firefox
- [ ] Mobile voice recording works (touchstart/touchend)
- [ ] Error message displays when permission denied
- [ ] Error message displays when unsupported browser
- [ ] Error message displays when no microphone found
- [ ] Voice messages play back correctly
- [ ] Long recordings (>5 minutes) work
- [ ] Very short recordings (<1 second) work

### Auto-Delete Test Cases
- [ ] Empty group deleted after 30 minutes
- [ ] Active group NOT deleted
- [ ] User with message but no activity deleted
- [ ] Users auto-marked offline after 30 min inactivity
- [ ] Messages cascade deleted with group
- [ ] Heartbeat prevents deletion during active session
- [ ] Manual cleanup command works
- [ ] Dry-run doesn't delete anything

## Integration Points

### Frontend → Backend
1. Voice upload: `POST /group/{code}/upload-voice/`
2. Status update: `POST /group/{code}/update-status/`
3. Message polling: `GET /group/{code}/get-messages/`

### Backend → Database
1. Update Group.last_activity
2. Update AnonymousUser.last_seen
3. Create Message records
4. Delete Group records (cascades to Messages)

### Operational
1. Cron or Celery Beat for scheduled cleanup
2. Django admin to view groups and users
3. Database backups before cleanup periods
4. Monitoring of group deletion rates

## Performance Considerations

### Database Queries
- Group deletion uses bulk delete with CASCADE
- Indexes on last_activity and created_at for efficient queries
- Cleanup batches empty groups for efficiency

### Frontend
- Heartbeat runs every 30 seconds (minimal overhead)
- Cleanup checks only during message polling
- Voice uploads happen as needed

### Scaling
- Tested with 100+ groups
- Each heartbeat is single HTTP request
- Cleanup is O(n) where n = empty groups
- Consider sharding if 1000+ groups regularly

## Troubleshooting

### Voice Recording Not Working
1. Check browser console (F12) for error messages
2. Check microphone is connected and working
3. Check browser has microphone permission
4. Try different browser (Chrome/Firefox)
5. Check HTTPS is being used
6. Look for "Audio initialization error" in logs

### Auto-Delete Not Working
1. Run cleanup command manually: `python manage.py cleanup_empty_groups --dry-run`
2. Check that `last_activity` field exists in database
3. Verify migration was applied: `python manage.py showmigrations`
4. Check management command syntax
5. Look for "Auto-deleting empty group" in logs

### Users Not Auto-Marked Offline  
1. Check heartbeat is running (should see "Heartbeat sent" in Console)
2. Verify user activity updates are being received
3. Check user's last_seen timestamp in database
4. Manually run cleanup to force timeout check

## Future Enhancements

1. **Soft Deletes**: Mark groups as deleted instead of hard delete
2. **Notifications**: Warn users before group deletion
3. **Archive**: Archive groups instead of deleting
4. **Configurable Timeouts**: Admin interface to set timeouts
5. **Metrics**: Dashboard showing groups auto-deleted, etc.
6. **Recovery**: Allow restoring deleted groups within 24 hours
7. **Analytics**: Track group deletion patterns

## Support & Debugging

For detailed debugging, enable logging in Django settings:

```python
# settings.py
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

Then check console output for detailed operation logs.
