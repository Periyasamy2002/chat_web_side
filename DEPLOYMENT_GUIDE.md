# Migration & Deployment Instructions

## Step 1: Apply Database Migration

Before deploying, apply the migration to add the `last_activity` field to the Group model:

```bash
# Apply the migration
python manage.py migrate chatapp 0005_auto_activity_tracking

# Verify migration was applied
python manage.py showmigrations chatapp
# Should show: [X] 0005_auto_activity_tracking
```

## Step 2: Test Voice Recording

### Local Testing
1. Start development server: `python manage.py runserver`
2. Create or join a group chat
3. Try recording a voice message:
   - Click the microphone button
   - Speak for a few seconds
   - Release the button
   - Voice message should appear in chat
4. Check browser console (F12) for detailed logs
5. Check server console for backend logs

### Test Cases
- Record on desktop (mouse press/hold)
- Record on mobile (touch press/hold)
- Test permission denied scenario
- Test in different browsers

## Step 3: Test Auto-Delete Feature

### Manual Testing
1. Create a test group and capture the group code
2. Let it sit idle for 30+ minutes (optional - can test with cleanup command)
3. Run cleanup command:
   ```bash
   python manage.py cleanup_empty_groups --verbose
   ```
4. Verify group was deleted if it had no activity

### Automatic Testing (Every Poll)
- Groups are automatically deleted during message polling
- Can verify by:
  - Creating a group
  - Not sending messages for 30 minutes
  - Having no online users
  - Then checking if group still exists in database

### Development Testing (Speed Up)
Temporarily modify timeouts for testing:

```python
# In views.py, change to 1 minute for testing
thirty_min_ago = timezone.now() - timezone.timedelta(minutes=1)

# Then test: create group → wait 1 minute → poll for messages → group should be deleted
```

## Step 4: Deployment

### Production Checklist
- [ ] Migration applied successfully
- [ ] Voice recording tested in target browsers
- [ ] Cleanup cron job configured (if not using polling-based cleanup)
- [ ] Database backups scheduled
- [ ] Logging configured for monitoring
- [ ] Staff trained on how to manually run cleanup if needed

### Cron Job Setup (Recommended)
```bash
# Edit crontab
crontab -e

# Add this line to run cleanup every 5 minutes
*/5 * * * * cd /path/to/chatproject && python manage.py cleanup_empty_groups

# Or daily at 2 AM
0 2 * * * cd /path/to/chatproject && python manage.py cleanup_empty_groups --verbose >> /var/log/chatapp-cleanup.log 2>&1
```

### Celery Setup (Alternative)
If using Celery for other tasks, add to beat schedule:

```python
# settings.py
CELERY_BEAT_SCHEDULE = {
    'cleanup-empty-groups': {
        'task': 'chatapp.tasks.cleanup_empty_groups',
        'schedule': crontab(minute='*/5'),
    },
}
```

### Monitoring
Monitor these key metrics:

```bash
# Count of groups in database
python manage.py shell
>>> Group.objects.count()

# Count of empty groups (should be 0 after cleanup)
>>> from datetime import timedelta
>>> from django.utils import timezone
>>> Group.objects.filter(last_activity__lt=timezone.now()-timedelta(minutes=30)).count()

# Count of online users
>>> AnonymousUser.objects.filter(is_online=True).count()
```

## Step 5: Post-Deployment Verification

1. **Voice Recording**:
   - Send test voice message in production group
   - Verify message appears for all users
   - Check audio file was stored correctly
   - Test playback

2. **Auto-Delete**:
   - Create test group
   - Verify group appears in `/admin/`
   - Check `last_activity` timestamp updates with messages
   - After 30 min inactivity, verify group is either still there (if no cleanup yet) or gone (if cleanup ran)

3. **User Status**:
   - Check user goes offline in `AnonymousUser` table
   - Verify online count updates during polling
   - Check heartbeat logs in console

## Rollback Plan

If issues arise with auto-delete feature:

### Option 1: Disable Auto-Delete (Keep Voices)
Comment out deletion code in `get_new_messages()`:

```python
# In views.py get_new_messages()
# Comment out this section:
# if deleted_count > 0:
#     print(f"Auto-deleted {deleted_count} empty groups")
```

### Option 2: Disable Activity Tracking
Remove heartbeat from frontend - comment out in group.html:
```javascript
// startHeartbeat(); // Comment this out in startPolling()
```

### Option 3: Revert Migration
```bash
python manage.py migrate chatapp 0004_anonymoususer_alter_userstatus_unique_together_and_more

# This removes the last_activity field (data will be lost if not backed up!)
```

## Troubleshooting

### Migration Failed
```bash
# Check migration status
python manage.py showmigrations

# If stuck, check for errors:
python manage.py migrate --plan

# If needed, reset (WARNING: Destroys data!)
python manage.py migrate chatapp zero
python manage.py migrate chatapp
```

### Voice Not Working
1. Check server logs: `/var/log/django.log` or console output
2. Check `/media/voice_messages/` directory exists and is writable
3. Run: `python manage.py collectstatic --noinput` (if WhiteNoise is used)
4. Verify CSRF token is being sent with uploads

### Auto-Delete Too Aggressive
- Increase timeout from 30 minutes to 60 minutes
- Modify in `update_user_status()` and `get_new_messages()`
- Also update heartbeat interval if needed

### Auto-Delete Not Running
- Check cleanup command can be run manually: `python manage.py cleanup_empty_groups --verbose`
- If manual works but cron doesn't, check:
  - Cron path to Python interpreter
  - Cron working directory
  - Cron logs: `grep CRON /var/log/syslog`

## Files Modified

### Frontend
- `chatapp/templates/group.html` - Enhanced voice recording, added heartbeat

### Backend
- `chatapp/models.py` - Added `last_activity` field and indexes
- `chatapp/views.py` - Activity tracking, auto-timeout, auto-delete logic
- `chatapp/management/commands/cleanup_empty_groups.py` - New cleanup command
- `chatapp/migrations/0005_auto_activity_tracking.py` - New migration

### Documentation
- `VOICE_AND_AUTO_DELETE_GUIDE.md` - This file

## Support

For issues or questions:
1. Check logs: application and system logs
2. Run cleanup command manually with --verbose flag
3. Check database directly: `python manage.py dbshell`
4. Review the VOICE_AND_AUTO_DELETE_GUIDE.md for detailed info
