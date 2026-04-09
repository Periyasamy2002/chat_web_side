# 🗑️ Django Group Chat - Automatic Group Deletion System

## Overview

This comprehensive auto-deletion system automatically removes inactive or empty groups to keep the chat system clean, efficient, and resource-optimized.

---

## ✅ Delete Conditions

The system automatically deletes groups based on **3 main conditions**:

### **Condition 1: Group opened with 0 users online**
- **Trigger:** When a group page is accessed and there are 0 online users
- **Safety Check:** Verifies online count before deletion
- **Action:** Delete group immediately

```python
# Location: views.py, group() function
online_count = get_group_online_count(group)
if online_count == 0:
    should_delete, reason = group.should_auto_delete()
    if should_delete:
        group.delete()
```

### **Condition 2: New group with no joins in 5 minutes**
- **Trigger:** Group created but no users joined within 5 minutes
- **Detection:** Automatic cleanup via management command
- **Action:** Delete empty new group after 5 minutes

```python
# Location: models.py, should_auto_delete()
five_min_ago = timezone.now() - timedelta(minutes=5)
if self.created_at < five_min_ago and self.get_online_count() == 0:
    return True, "new_empty_5min"
```

### **Condition 3: All users left for 4+ minutes**
- **Trigger:** All users leave the group
- **Wait Period:** 4 minutes for potential rejoin
- **Action:** Delete group if no one returns within 4 minutes

```python
# Location: models.py, should_auto_delete()
four_min_ago = timezone.now() - timedelta(minutes=4)
if self.last_activity < four_min_ago and self.get_online_count() == 0:
    return True, "all_left_4min"
```

---

## 📊 Implementation Architecture

### **1. Database Models** (`models.py`)

#### Group Model Enhancements:
```python
class Group(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)      # Track creation time
    last_activity = models.DateTimeField(auto_now_add=True)   # Track last activity
    
    # New methods for deletion logic:
    def get_online_count(self) -> int
    def get_group_online_count(self) -> int
    def should_auto_delete_empty(self) -> bool
    def should_auto_delete_new_empty(self) -> bool
    def should_auto_delete_all_left(self) -> bool
    def should_auto_delete(self) -> tuple[bool, str]
```

**Key Indexes:**
```python
indexes = [
    models.Index(fields=['last_activity']),      # Fast cleanup queries
    models.Index(fields=['created_at']),          # Find new groups
]
```

#### AnonymousUser Model:
```python
class AnonymousUser(models.Model):
    session_id = models.CharField(max_length=255, unique=True)
    user_name = models.CharField(max_length=100)
    is_online = models.BooleanField(default=True)
    last_seen = models.DateTimeField(auto_now=True)          # Auto-update on heartbeat
    created_at = models.DateTimeField(auto_now_add=True)
```

**Online Detection:**
- User is **online** if `last_seen` is within last **5 minutes**
- Heartbeat updates via `update_user_status()` every 30 seconds

---

### **2. Cleanup Utility Functions** (`group_cleanup.py`)

#### Helper Functions:

```python
def get_group_online_count(group) -> int
    """Get actual online users in a group (cross-checked with messages)"""

def check_and_delete_empty_groups() -> tuple[int, list]
    """Periodic cleanup of all groups"""
    
def check_group_on_access(group) -> tuple[bool, str]
    """Check when group is accessed"""

def cleanup_on_user_join(group, user_session_id) -> bool
    """Update activity when user joins"""

def cleanup_on_user_leave(group, user_session_id) -> tuple[bool, str]
    """Check if group is now empty"""

def update_user_heartbeat(user_session_id) -> bool
    """Update user's last_seen timestamp"""

def get_group_deletion_status(group_code) -> dict
    """Get detailed deletion status for a group"""

def get_all_groups_cleanup_status() -> list
    """Get status for all groups"""
```

---

### **3. View Integration** (`views.py`)

#### Auto-Deletion Checks in Views:

**In `chat()` view:**
```python
# When user joins a group
cleanup_on_user_join(group, request.session.session_key)
```

**In `group()` view:**
```python
# Check 1: If group is opened with 0 users, check if should delete
online_count = get_group_online_count(group)
if online_count == 0:
    should_delete, reason = group.should_auto_delete()
    if should_delete:
        logger.warning(f"Auto-deleting group '{code}'")
        group.delete()
        return render(request, "chat.html", {...})
```

**In `update_user_status()` view:**
```python
# Every 30 seconds, user heartbeat updates last_seen
anon_user.last_seen = timezone.now()
anon_user.save()
```

---

### **4. Management Command** (`management/commands/cleanup_empty_groups.py`)

Run automatic cleanup on schedule:

```bash
# Run cleanup now
python manage.py cleanup_empty_groups

# Show status without deleting
python manage.py cleanup_empty_groups --status

# Test run (show what would be deleted)
python manage.py cleanup_empty_groups --dry-run

# Run with detailed output
python manage.py cleanup_empty_groups --verbose
```

#### Setup with Cron (Every 2 minutes):
```crontab
*/2 * * * * cd /path/to/project && python manage.py cleanup_empty_groups >> /var/log/chat_cleanup.log 2>&1
```

#### Setup with Django APScheduler (Alternative):
```python
from apscheduler.schedulers.background import BackgroundScheduler
from chatapp.group_cleanup import check_and_delete_empty_groups

def start_cleanup_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        check_and_delete_empty_groups,
        'interval',
        minutes=2,
        id='cleanup_groups'
    )
    scheduler.start()
```

---

### **5. Monitoring APIs** (New Endpoints)

#### Get Single Group Status:
```
GET /group/<code>/cleanup-status/
```

**Response:**
```json
{
    "code": "TEST",
    "should_delete": false,
    "reason": "active",
    "online_count": 2,
    "age_minutes": 15.5,
    "inactivity_minutes": 3.2,
    "created_at": "2026-04-09T10:00:00Z",
    "last_activity": "2026-04-09T10:15:00Z"
}
```

#### Get All Groups Status:
```
GET /admin/groups-status/
```

**Response:**
```json
{
    "success": true,
    "total_groups": 3,
    "groups": [
        {
            "code": "TEST",
            "name": "Test Group",
            "should_delete": false,
            "delete_reason": "active",
            "online_count": 2,
            "age_minutes": 15.5,
            "inactivity_minutes": 3.2
        },
        {
            "code": "EMPTY",
            "name": "Empty Group",
            "should_delete": true,
            "delete_reason": "new_empty_5min",
            "online_count": 0,
            "age_minutes": 10.0,
            "inactivity_minutes": 10.0
        }
    ]
}
```

---

## 🔄 Deletion Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ User opens/joins group                                      │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
    ┌─────────────────┐
    │ Check online    │
    │ user count      │
    └────────┬────────┘
             │
        ┌────┴────┐
        │          │
    (0 users)  (≥1 user)
        │          │
        ▼          ▼
   Check time  Continue
   conditions  normally
        │
    ┌───┴────────────────────┐
    │                        │
New? (< 5min)  Old empty? (≥ 4min)
    │                        │
    No                      Yes
    │                        │
    ▼                        ▼
Keep group          🗑️ DELETE GROUP
    │              (all_left_4min)
    │
   Yes (≥ 5min)
    │
    ▼
🗑️ DELETE GROUP
(new_empty_5min)
```

---

## 🧪 Testing the Auto-Deletion System

### **Test 1: New Group Empty for 5 Minutes**

```bash
# Step 1: Create and don't join a group
# - Go to http://127.0.0.1:8000
# - Don't click "Submit" on chat form
# - Wait exactly 5 minutes

# Step 2: Run cleanup
python manage.py cleanup_empty_groups --dry-run

# Expected: Shows "Would delete: [group_code]" with reason "new_empty_5min"
```

### **Test 2: All Users Left for 4 Minutes**

```bash
# Step 1: Create and join group
# - Name: Alice, Code: TEST

# Step 2: Message someone from another browser
# - Name: Bob, Code: TEST
# - Send message

# Step 3: Both users leave
# - Close both browser tabs

# Step 4: Wait 4 minutes

# Step 5: Run cleanup
python manage.py cleanup_empty_groups --status

# Expected: Shows group TEST with "Should Delete: True" and reason "all_left_4min"
```

### **Test 3: Immediate Delete on Access with 0 Users**

```bash
# Step 1: Create group with user
# - Name: Alice, Code: QUICK

# Step 2: Check deletion status
curl http://127.0.0.1:8000/admin/groups-status/

# Step 3: User leaves (wait 5 minutes or more for age)

# Step 4: Someone tries to access group
# - Name: Bob, Code: QUICK

# Expected: Group auto-deletes, shows message "Group QUICK was deleted due to inactivity"
```

### **Test 4: Monitor All Groups**

```bash
# Get real-time status
python manage.py cleanup_empty_groups --status

# Output example:
# ✅ Active Group 1: 2 users, 5 min old, inactivity 2 min
# ❌ Empty Group: 0 users, 7 min old, inactivity 7 min - Should Delete
# ⚠️ New Group: 0 users, 8 min old - Should Delete (new_empty_5min)
```

---

## 🚀 Deployment Setup

### **Option 1: Using Cron**

```bash
# Edit crontab
crontab -e

# Add line (run every 2 minutes):
*/2 * * * * cd /opt/chatapp && python manage.py cleanup_empty_groups >> /var/log/chat_cleanup.log 2>&1

# Check logs
tail -f /var/log/chat_cleanup.log
```

### **Option 2: Using Celery**

```python
# celery.py
from celery import shared_task
from chatapp.group_cleanup import check_and_delete_empty_groups

@shared_task
def run_cleanup():
    deleted_count, details = check_and_delete_empty_groups()
    return f"Deleted {deleted_count} groups"

# Schedule in celery beat
from celery.schedules import crontab

app.conf.beat_schedule = {
    'cleanup-every-2-minutes': {
        'task': 'chatapp.tasks.run_cleanup',
        'schedule': crontab(minute='*/2'),
    },
}
```

### **Option 3: Using APScheduler**

```python
# apps.py
from django.apps import AppConfig
from apscheduler.schedulers.background import BackgroundScheduler

class ChatappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chatapp'
    
    def ready(self):
        from .group_cleanup import check_and_delete_empty_groups
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            check_and_delete_empty_groups,
            'interval',
            minutes=2,
            id='group_cleanup'
        )
        if not scheduler.running:
            scheduler.start()
```

---

## 📋 Verification Checklist

- [x] Models enhanced with `should_auto_delete()` method
- [x] `get_group_online_count()` properly counts active users
- [x] Views check deletion on group access
- [x] Management command works for manual cleanup
- [x] --status flag shows all groups
- [x] --dry-run flag shows what would be deleted
- [x] Monitoring APIs return correct data
- [x] Database indexes on `last_activity` and `created_at`
- [x] User heartbeat updates `last_seen` every 30s
- [x] Double-check online count before deletion
- [x] Prevent accidental deletion with safety checks
- [x] Logging enabled for deletion events
- [x] Error handling in all cleanup functions

---

## 📊 Performance Metrics

| Metric | Value | Impact |
|--------|-------|--------|
| Online detection timeout | 5 minutes | Users go offline if inactive |
| Empty group grace period | 4 minutes | Time for users to rejoin |
| New group timeout | 5 minutes | Time before auto-delete new empty groups |
| Heartbeat interval | 30 seconds | Keep user marked as online |
| Cleanup run frequency | Every 2 minutes | Regular removal of stale groups |
| Database query optimization | Indexed fields | Fast deletion checks |

---

## 🔒 Safety Features

1. **Double-Check Before Deletion**
   ```python
   should_delete, reason = group.should_auto_delete()
   if should_delete:
       online_count = get_group_online_count(group)  # Verify again
       if online_count == 0:
           group.delete()  # Only then delete
   ```

2. **Logging of All Deletions**
   ```python
   logger.warning(f"Auto-deleting group '{code}' - reason: {reason}")
   ```

3. **Dry-Run Mode Before Production**
   ```bash
   python manage.py cleanup_empty_groups --dry-run
   ```

4. **Monitoring APIs for Admin**
   ```
   GET /admin/groups-status/
   ```

---

## ❓ FAQ

**Q: What if users rejoin after all leave?**  
A: `last_activity` updates when they rejoin, restarting the 4-minute timer. Deletion is safe.

**Q: Can groups be "soft deleted"?**  
A: Currently hard-deleted. To enable recovery, add `is_deleted` flag to Group model.

**Q: How do I skip deletion for certain groups?**  
A: Add `keep_alive` boolean field to Group, check in `should_auto_delete()`.

**Q: What about group creation timestamp?**  
A: Used to detect new empty groups (< 5 minutes old with 0 users).

---

## 📁 File Changes Summary

| File | Changes | Purpose |
|------|---------|---------|
| `models.py` | Enhanced `Group` model with deletion methods | Deletion logic & conditions |
| `group_cleanup.py` | New utility module | Cleanup helper functions |
| `views.py` | Updated imports, added cleanup calls | Integration with views |
| `management/commands/cleanup_empty_groups.py` | Enhanced command | Manual & scheduled cleanup |
| `urls.py` | Added 2 new routes | Monitoring APIs |

---

## 🎯 Summary

✅ **Automatic**: Runs on schedule via cron/APScheduler  
✅ **Safe**: Double-checks before deletion  
✅ **Efficient**: Indexed database queries  
✅ **Monitored**: APIs for admin oversight  
✅ **Flexible**: Supports manual + automatic cleanup  
✅ **Production-Ready**: Error handling & logging  

---

**Status:** ✅ **COMPLETE & TESTED**  
**Ready for Production:** YES  
**Version:** 1.0
