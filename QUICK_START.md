# Quick Start Guide - Voice & Auto-Delete Features

## What Was Fixed

### 1. Voice Message Feature (Microphone Not Working) ✅
Your microphone now works with:
- Better error messages when permission denied
- Support for all modern browsers
- Mobile (touchscreen) support
- Automatic retry on recoverable errors
- Detailed logging for debugging

### 2. Auto-Delete for Empty Groups ✅
Groups now automatically:
- Track when they were last active
- Mark users offline after 30 minutes of no activity  
- Delete themselves if empty for 30 minutes
- Keep user status accurate with heartbeat pings

## Installation (3 Steps)

### Step 1: Apply Database Migration
```bash
python manage.py migrate chatapp 0005_auto_activity_tracking
```

### Step 2: Test Voice Recording
1. Open chat in browser
2. Click microphone button
3. Speak and release
4. Voice message should appear ✓

### Step 3: Setup Auto-Delete (Choose One)

**Option A: Automatic (Built-in)**
- Auto-delete happens during polling
- No additional setup needed
- Works when users are polling for messages

**Option B: Scheduled (Recommended)**
Add to crontab (runs every 5 minutes):
```bash
*/5 * * * * cd /path/to/chatproject && python manage.py cleanup_empty_groups
```

## How It Works

### Voice Recording
1. User clicks mic button
2. Browser asks for microphone permission
3. User speaks
4. User releases button
5. Audio is sent to server
6. Voice message appears in chat
7. Others can play it back

### Auto-Delete
```
User joins group → last_activity timestamp updated
User sends message → last_activity timestamp updated  
30 seconds: Heartbeat ping sent → last_seen timestamp updated
30 minutes of no activity + 0 online users → Group deleted
```

## Testing

### Quick Test - Voice Recording
```bash
# Start server
python manage.py runserver

# In browser:
# 1. Go to http://localhost:8000
# 2. Join a group
# 3. Click mic and speak
# 4. Should see voice message in chat
```

### Quick Test - Auto-Delete
```bash
# Create a test group and send a message
# Then run:
python manage.py cleanup_empty_groups --verbose

# If group was empty 30+ min, it will be deleted
```

## Configuration

All timeouts are in code - easy to customize:

| Setting | File | Where |
|---------|------|-------|
| Heartbeat frequency | group.html | Line with `30000` in startHeartbeat() |
| User timeout | views.py | `timedelta(minutes=30)` in update_user_status() |
| Group delete timeout | views.py | `timedelta(minutes=30)` in get_new_messages() |

## Files Changed

**Frontend**:
- ✅ chatapp/templates/group.html - Voice + heartbeat improvements

**Backend**:
- ✅ chatapp/models.py - Added last_activity field
- ✅ chatapp/views.py - Activity tracking + auto-delete logic  
- ✅ chatapp/management/commands/cleanup_empty_groups.py - NEW
- ✅ chatapp/migrations/0005_auto_activity_tracking.py - NEW migration

**Documentation**:
- ✅ VOICE_AND_AUTO_DELETE_GUIDE.md - Full details
- ✅ DEPLOYMENT_GUIDE.md - Deployment steps
- ✅ IMPLEMENTATION_SUMMARY.md - Technical summary

## Troubleshooting

### Voice Recording Not Working
| Issue | Solution |
|-------|----------|
| "Microphone access denied" | Enable microphone in browser settings |
| "No microphone found" | Connect a microphone |  
| "Not supported" | Use Chrome, Firefox, or Edge |
| "HTTPS required" | Use HTTPS connection |

**Debug**: Open browser console (F12) and look for error messages

### Auto-Delete Not Working
| Issue | Solution |
|-------|----------|
| Groups not deleting | Run `python manage.py cleanup_empty_groups --verbose` |
| Users not going offline | Check heartbeat in console with F12 |
| Migration failed | Run `python manage.py showmigrations` to check status |

## Key Features

✅ **Voice Recording**
- Works in Chrome, Firefox, Edge, Safari
- Desktop and mobile support
- Clear error messages
- Automatic permission handling
- Audio file storage

✅ **User Status Tracking**
- 30-second heartbeat keep-alive
- 30-minute auto-offline timeout
- Activity detection (clicks, typing, movement)
- Accurate online count

✅ **Group Auto-Delete**
- Deletes empty groups after 30 minutes
- Prevents database bloat
- Cascading deletion of messages
- Can be manually run anytime

## Monitoring

Check logs to see what's happening:
```bash
# In console output, look for:
✓ Microphone access granted
✓ Recording started
✓ Voice message uploaded
Heartbeat sent, online_count: 5
Auto-marked user as offline
Auto-deleted 2 empty groups
```

## Next Steps

1. ✅ Install migration: `python manage.py migrate`
2. ✅ Test voice recording manually
3. ✅ Setup cron job for auto-delete
4. ✅ Monitor logs first day
5. ✅ Done!

## Support

For detailed information:
- Full guide: See `VOICE_AND_AUTO_DELETE_GUIDE.md`
- Deployment: See `DEPLOYMENT_GUIDE.md`
- Technical: See `IMPLEMENTATION_SUMMARY.md`

---

**Questions?** Check the detailed guides in the project root directory.

**Status**: Ready to Deploy! 🚀
