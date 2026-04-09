# 🚀 AUTO-DELETION SYSTEM TEST GUIDE

**Last Updated**: April 9, 2026  
**Status**: Ready for Testing  
**Server**: Running at http://127.0.0.1:8000/

---

## ✅ Complete Implementation Checklist

### Backend (views.py)
- ✅ Removed all `from .group_cleanup import` statements
- ✅ Added `check_and_cleanup_group()` helper function
- ✅ Added `update_user_online_status()` helper function
- ✅ Added `auto_offline_inactive_users()` helper function
- ✅ All 8 API endpoints include deletion checks
- ✅ Returns HTTP 410 Gone when group is deleted
- ✅ Comprehensive logging with [GROUP], [DELETE CHECK], [MESSAGE] prefixes

### Backend (models.py)
- ✅ Fixed `get_group_online_count()` to be group-specific
- ✅ Enhanced `should_auto_delete()` with detailed reasons
- ✅ Added detailed logging to deletion logic
- ✅ Implements all 3 deletion conditions correctly

### Frontend (group.html)
- ✅ `getNewMessages()` handles 410 Gone - shows message & redirects
- ✅ `sendMessage()` handles 410 Gone - alerts user & redirects
- ✅ `uploadVoiceMessage()` handles 410 Gone - alerts user & redirects
- ✅ `sendHeartbeat()` handles 410 Gone - stops polling
- ✅ Page unload API call remains fire-and-forget

---

## 🧪 Test Scenario 1: Auto-Delete After Inactivity

### Prerequisites
- Server running: `python manage.py runserver`
- Console visible to see logs
- Browser developer tools open (F12)

### Steps

**1. Create a Test Group**
```
URL: http://127.0.0.1:8000/chat/
Name: TestUser
Code: AUTO_DELETE_TEST_1
```
**Expected**: 
- Group page loads
- Console shows: `[GROUP AUTO_DELETE_TEST_1] Group online users: 1`
- Send a test message

**2. Close Browser Tab (Simulate User Leaving)**
- Close the browser tab/window
- Wait 30 seconds for heartbeat to stop (frontend stops sending updates)

**3. Wait for Auto-Offline (30+ minutes OR Force)**
- **Option A (Real)**: Wait 30+ minutes
- **Option B (Force)**: Open terminal and run:
  ```bash
  python manage.py shell
  >>> from chatapp.models import AnonymousUser
  >>> from django.utils import timezone
  >>> from datetime import timedelta
  >>> # Mark all users as inactive
  >>> AnonymousUser.objects.update(last_seen=timezone.now() - timedelta(minutes=31))
  ```

**4. Trigger Deletion Check**
- Open new browser: `http://127.0.0.1:8000/group/AUTO_DELETE_TEST_1/`
- OR call API directly with curl:
  ```bash
  curl http://127.0.0.1:8000/group/AUTO_DELETE_TEST_1/get-messages/
  ```

**Expected Console Output**:
```
[GROUP AUTO_DELETE_TEST_1] Group online users: 0 (from 1 total users), Age: 5.2 min, Inactivity: 5.1 min
[DELETE CHECK] Group AUTO_DELETE_TEST_1: DELETE (Condition 2) - new_empty_5min
[CLEANUP] Group AUTO_DELETE_TEST_1: Final check - 0 online users
[DELETE] Group AUTO_DELETE_TEST_1: DELETING - Reason: new_empty_5min
```

**Frontend Response**:
- If browser page: "Group was deleted due to inactivity (new_empty_5min)" message
- Redirects to chat page after 2 seconds
- Browser console: No errors, only info about deletion

**Database**:
- Run: `python manage.py shell`
- Verify: `Group.objects.filter(code='AUTO_DELETE_TEST_1').exists()` → False

---

## 🧪 Test Scenario 2: Group with Multiple Users

### Prerequisites
- Two browser windows (or terminals with curl)
- Same server running

### Steps

**1. User 1 Creates & Joins Group**
```
Name: User1
Code: MULTI_USER_TEST
Message: "Hello from User 1"
```

**2. User 2 Joins Same Group**
- Open new browser window
- Go to: http://127.0.0.1:8000/chat/
- Name: User2
- Code: MULTI_USER_TEST
- Click Join

**Expected**:
- Both see each other's messages
- Console shows: `[GROUP MULTI_USER_TEST] Group online users: 2`

**3. User 1 Leaves (Close Tab 1)**
- Close first browser tab
- Wait 30 seconds
- Console shows User1 offline after 30 min check

**4. User 2 Stays, Then Leaves**
- User 2 keeps group open for 2+ minutes
- Then closes tab
- Wait 30 seconds

**5. Trigger Deletion Check After Both Gone**
- API call to group: `curl http://127.0.0.1:8000/group/MULTI_USER_TEST/`
- Wait 5 minutes total (from U1 leaving)

**Expected**:
```
[GROUP MULTI_USER_TEST] Group online users: 0 (from 2 total users), Age: 5.2 min, Inactivity: 5.1 min
[DELETE CHECK] Group MULTI_USER_TEST: DELETE (Condition 2) - new_empty_5min
[DELETE] Group MULTI_USER_TEST: DELETING - Reason new_empty_5min
```

---

## 🧪 Test Scenario 3: Fresh Group (NEW_EMPTY condition)

### Expected Behavior
**Condition**: Group created but no users ever joined (0 messages)

### Steps

**1. Create Empty Group Programmatically**
```bash
python manage.py shell
>>> from chatapp.models import Group
>>> from django.utils import timezone
>>> from datetime import timedelta
>>> # Create group that's 6 minutes old with 0 users
>>> g = Group.objects.create(
...     code='EMPTY_TEST_OLD',
...     name='Empty Test Old',
...     created_at=timezone.now() - timedelta(minutes=6),
...     last_activity=timezone.now() - timedelta(minutes=6)
... )
```

**2. Trigger Deletion Check**
```bash
curl http://127.0.0.1:8000/group/EMPTY_TEST_OLD/
```

**Expected Console Output**:
```
[GROUP EMPTY_TEST_OLD] Group online users: 0 (from 0 total users), Age: 6.0 min, Inactivity: 6.0 min
[DELETE CHECK] Group EMPTY_TEST_OLD: DELETE (Condition 2) - new_empty_5min
[DELETE] Group EMPTY_TEST_OLD: DELETING - Reason: new_empty_5min
```

**Database Check**:
```bash
python manage.py shell
>>> Group.objects.filter(code='EMPTY_TEST_OLD').exists()  # False
```

---

## 🧪 Test Scenario 4: Keep Active Group

### Expected Behavior
**Group should NOT delete** if users are active

### Steps

**1. Create Group & Send Message Every 3 Minutes**
```
Name: ActiveUser
Code: KEEP_ACTIVE_TEST
Message: "Still here!" (every 3 min)
```

**2. Wait 10 Minutes While Sending Messages**
- Send at 0 min, 3 min, 6 min, 9 min
- Keep browser open and active

**3. Check Group Status at 11 Minutes**
```bash
curl http://127.0.0.1:8000/group/KEEP_ACTIVE_TEST/cleanup-status/
```

**Expected Console Output**:
```
[GROUP KEEP_ACTIVE_TEST] Group online users: 1 (from 1 total users), Age: 11.0 min, Inactivity: 0.5 min
[DELETE CHECK] Group KEEP_ACTIVE_TEST: KEEP (1 users online)
```

**Response**:
```json
{
  "should_delete": false,
  "delete_reason": "active"
}
```

**Database**:
- Group still exists
- 4+ messages in database

---

## 📊 Admin Monitoring Endpoints

### Get All Groups Status
```bash
curl http://127.0.0.1:8000/admin/groups-status/ | python -m json.tool
```

**Output Example**:
```json
{
  "success": true,
  "total_groups": 3,
  "groups": [
    {
      "group_code": "DELETE_ME_1",
      "group_name": "DELETE_ME_1",
      "created_at": "2026-04-09T08:00:00Z",
      "last_activity": "2026-04-09T08:10:00Z",
      "age_minutes": 321.5,
      "inactivity_minutes": 315.2,
      "online_count": 0,
      "total_messages": 12,
      "should_delete": true,
      "delete_reason": "all_left_4min"
    },
    {
      "group_code": "KEEP_ACTIVE_TEST",
      "age_minutes": 11.2,
      "inactivity_minutes": 0.5,
      "online_count": 1,
      "should_delete": false,
      "delete_reason": "active"
    }
  ]
}
```

### Get Single Group Status
```bash
curl http://127.0.0.1:8000/group/AUTO_DELETE_TEST_1/cleanup-status/ | python -m json.tool
```

---

## 🔍 Console Debugging

### View All Console Logs
1. Open Safari/Chrome DevTools (F12)
2. Go to Console tab
3. Filter by:
   - `[GROUP]` - Group status checks
   - `[DELETE CHECK]` - Deletion decision logic
   - `[MESSAGE]` - Text messages sent
   - `[VOICE]` - Voice messages uploaded
   - `[USER]` - User online/offline changes
   - `[ERROR]` - Any errors

### Server-Side Logs
Terminal running `python manage.py runserver` shows:
- All database queries
- All group deletion checks with reasons
- User activity updates
- Error messages

### Quick Filter Example
```bash
# Show only deletion checks
grep "\[DELETE" console_output.log

# Show only group online count checks
grep "\[GROUP" console_output.log

# Show when groups are actually deleted
grep "\[DELETE\]" console_output.log | grep DELETING
```

---

## ⚠️ Common Issues & Debugging

### Issue 1: Group Not Deleting After 5 Minutes
**Possible Cause**: User's `last_seen` is still being updated by heartbeat

**Check**:
```bash
curl http://127.0.0.1:8000/group/TESTCODE/cleanup-status/
# Look at "inactivity_minutes" - should be >= 4
# Look at "online_count" - should be 0
# Look at "delete_reason" - should show reason if should_delete is true
```

**Fix**: 
- Wait longer for heartbeat to timeout (30 minutes default)
- OR manually update in shell:
  ```bash
  python manage.py shell
  >>> from chatapp.models import AnonymousUser
  >>> u = AnonymousUser.objects.get(user_name='TestUser')
  >>> from django.utils import timezone
  >>> from datetime import timedelta
  >>> u.last_seen = timezone.now() - timedelta(minutes=31)
  >>> u.save()
  ```

### Issue 2: 410 Gone But Page Doesn't Redirect
**Check**:
1. Open browser DevTools (F12) → Network tab
2. Look for request to `/group/CODE/get-messages/`
3. Check Response Status: Should be 410
4. Check Console: Look for redirect message

**If console shows error**: JavaScript error may be preventing redirect
- Check console for JavaScript errors
- Look at error handler functions in group.html

### Issue 3: Console Shows No Deletion Logs
**Possible Cause**: 
- Deletion check not being called
- Group still has users or is too new

**Debug**:
1. Send API request manually:
   ```bash
   curl -v http://127.0.0.1:8000/group/TESTCODE/get-messages/
   ```
2. Watch console for `[GROUP]` and `[DELETE CHECK]` logs
3. If not present, deletion function not being called

**Fix**:
- Check that endpoint is calling `check_and_cleanup_group(group)`
- Verify group meets deletion criteria (online_count==0, age>=5, inactivity>=4)

---

## ✅ Verification Checklist

**Before declaring success, verify**:

- [ ] Group deletes after 5 min age + 0 users (`new_empty_5min`)
- [ ] Group deletes after 4 min inactivity + 0 users (`all_left_4min`)
- [ ] Group does NOT delete if users are online
- [ ] Console shows `[DELETE CHECK]` and deletion reason
- [ ] Frontend handles 410 Gone and redirects
- [ ] Admin endpoints return correct status
- [ ] Multiple users scenarios work correctly
- [ ] Heartbeat stops when user leaves, eventually marks offline
- [ ] Database records are actually deleted (not soft-delete)
- [ ] No new error messages in server console

---

## 🎉 Success Criteria

✅ **PASS** when:
1. Created groups auto-delete after meeting conditions
2. Console shows detailed logs with reasons
3. Frontend gracefully handles deletion with user message
4. Admin endpoints show correct group status
5. No errors in server or browser console
6. Database queries are efficient (indexed queries)
7. Multiple concurrent users don't break system

---

## 📝 Quick Reference Commands

```bash
# Start server (terminal 1)
cd chatproject
python manage.py runserver

# Open shell (terminal 2)
python manage.py shell

# Get all groups
>>> from chatapp.models import Group
>>> Group.objects.all().values_list('code', 'created_at', 'last_activity')

# Check specific group deletion status
>>> g = Group.objects.get(code='TEST')
>>> g.should_auto_delete()
>>> g.get_group_online_count()

# Mark users inactive (force offline after 30 min)
>>> from chatapp.models import AnonymousUser
>>> from django.utils import timezone
>>> from datetime import timedelta
>>> AnonymousUser.objects.update(
...     last_seen=timezone.now() - timedelta(minutes=31)
... )

# Delete all test groups
>>> Group.objects.filter(code__startswith='TEST').delete()

# Check deletion logs in real-time
tail -f server_console_output.log | grep "\[DELETE"
```

---

## 📞 Still Having Issues?

Check these in order:
1. Is server running? `http://127.0.0.1:8000/ should load`
2. Are there database errors? Check terminal where runserver is running
3. Do groups have users? Check with cleanup-status endpoint
4. Is group old enough? Must be 5+ minutes created
5. Are users actually offline? Check last_seen timestamps
6. Is deletion logic running? Should see `[GROUP]` log on every API call

If still stuck, check the CONSOLIDATION_COMPLETE.md for full debugging guide.
