# 🚀 QUICK START - AUTO-DELETION SYSTEM

## 5-Minute Quick Start

### Check Current Status

```bash
python manage.py cleanup_empty_groups --status
```

You'll see output like:
```
✅ Active Groups: [Listed with online users]
❌ Delete Candidates: [Listed with reasons - new_empty_5min, all_left_4min]
```

---

### Test Before Running

```bash
python manage.py cleanup_empty_groups --dry-run
```

Shows exactly what will be deleted:
```
❌ Would delete: GROUP_CODE (reason)
   Age: X minutes
   Last Activity: Y minutes ago
```

---

### Run Cleanup

```bash
python manage.py cleanup_empty_groups --verbose
```

Shows deleted groups with timestamps:
```
✅ Deleted 2 groups:
   • GROUP1 (new_empty_5min)
   • GROUP2 (all_left_4min)
```

---

## Web APIs

### Check Single Group

```bash
curl http://127.0.0.1:8000/group/TEST/cleanup-status/
```

Response shows if group should be deleted and why:
```json
{
    "code": "TEST",
    "should_delete": true,
    "reason": "new_empty_5min",
    "online_count": 0,
    "age_minutes": 10.5
}
```

### Check All Groups

```bash
curl http://127.0.0.1:8000/admin/groups-status/
```

Shows overview of all groups with deletion status.

---

## Real-World Scenarios

### Scenario 1: Group Created But No One Joins

```
10:00 AM - Group "NEWGROUP" created
10:05 AM - No one joined yet
→ ManagCmd: CANDIDATE FOR DELETION (new_empty_5min)
```

### Scenario 2: Users Leave

```
11:00 AM - Users Alice & Bob in group "CHAT"
11:30 AM - Both users leave
11:34 AM - After 4 minutes with 0 users
→ ManagCmd: READY TO DELETE (all_left_4min)
```

### Scenario 3: Accessed with 0 Users

```
10:00 AM - Group "OLD" accessed
- Online count: 0
- Age: 30+ minutes
- Last activity: 20+ minutes ago
→ View: AUTO-DELETE ON ACCESS
→ Message shown: "Group OLD was deleted due to inactivity"
```

---

## Production Commands

### Auto-run Every 2 Minutes

**Option 1 - Cron:**
```bash
crontab -e
# Add: */2 * * * * cd /path && python manage.py cleanup_empty_groups
```

**Option 2 - Systemd Timer:**
```bash
# Create /etc/systemd/system/chat-cleanup.timer
[Unit]
Description=Chat Group Cleanup
[Timer]
OnBootSec=1min
OnUnitActiveSec=2min
[Install]
WantedBy=timers.target
```

---

## Troubleshooting

### Check if groups exist
```bash
python manage.py cleanup_empty_groups --status
```
If no groups shown: No groups in database

### Verify cleanup logic
```bash
python manage.py cleanup_empty_groups --dry-run
```
If shows groups but doesn't delete: Use dry-run first to verify!

### Run cleanup safely
```bash
python manage.py cleanup_empty_groups --verbose
# See exactly what was deleted
```

---

## Key Timeouts

| Condition | Timeout | Action |
|-----------|---------|--------|
| New group with 0 users | 5 min | AUTO-DELETE |
| All users left | 4 min | AUTO-DELETE |
| User online status | 5 min | Mark offline |
| User heartbeat | 30 sec | Keep alive |

---

## That's It! 

✅ Auto-deletion running  
✅ Groups cleaned automatically  
✅ Database optimized  

For more details: See [AUTO_DELETION_SYSTEM.md](AUTO_DELETION_SYSTEM.md)
