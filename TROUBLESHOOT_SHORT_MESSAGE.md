# Short Message Sending - Troubleshooting Guide

## Common Issues & Fixes

### Issue 1: "hi" Message Not Appearing (But No Error)

**Symptoms:**
- Console shows all logs working
- Server shows message saved
- But message doesn't appear in chat window

**Cause:** 
Frontend display bug or message list not updating

**Fixes:**
1. Refresh page and message should appear
2. Check if `fetchNewMessages()` is being called after send
3. Verify message timestamp is after last_message_timestamp

---

### Issue 2: Console Shows "Message is empty"

**Symptoms:**
```
[SEND_MESSAGE] Raw input value: hi
[SEND_MESSAGE] After trim: 
[SEND_MESSAGE] Message is empty, not sending
```

**Cause:**
Trim is removing all characters OR input field is not "messageInput"

**Fix:**
Check HTML input element:
```html
<!-- CORRECT -->
<input type="text" name="message" id="messageInput" placeholder="...">

<!-- WRONG - different ID -->
<input type="text" name="message" id="chatInput" placeholder="...">
```

---

### Issue 3: Server Shows "ERROR: Empty message"

**Symptoms:**
```
[SEND_MESSAGE_AJAX] Content: 
[SEND_MESSAGE_AJAX] Content length: 0
[SEND_MESSAGE_AJAX] ERROR: Empty message
```

**Cause:**
Backend receiving empty message

**Fixes:**
1. Check CSRF token is being sent correctly
2. Verify FormData append is working
3. Check if  POST data is being corrupted

Test with cURL:
```bash
curl -X POST http://127.0.0.1:8000/group/TESTGROUP/send-message/ \
  -d "message=hi" \
  -H "X-CSRFToken: your-csrf-token"
```

---

### Issue 4: Fetch Shows "Response not OK"

**Symptoms:**
```
[SEND_MESSAGE] Response not OK: 400 Bad Request
[SEND_MESSAGE] Response body: {...error...}
```

**Cause:**
Backend validation rejection

**Fixes:**
Check backend logs for specific error:
- `Message cannot be empty` - empty check failed
- `Message too long` - over 5000 chars
- `Group not found` - group code wrong
- CSRF token mismatch

---

### Issue 5: Message Sent But Has Weird Characters

**Symptoms:**
Message appears in database but with strange encoding

**Cause:**
Unicode/UTF-8 encoding issue

**Fixes:**
1. Check file encoding: Should be UTF-8
2. Check database: Should support UTF-8
3. Check Django: Should handle UTF-8

**Test:**
```python
msg = Message.objects.filter(content='hi').first()
print(f"Hex: {msg.content.encode('utf-8').hex()}")  # Should be: 6869
print(f"Characters: {[ord(c) for c in msg.content]}")  # Should be: [104, 105]
```

---

## Quick Fix Checklist

- [ ] Message input ID is "messageInput"
- [ ] Send button onclick triggers sendMessage()
- [ ] CSRF token is present in form
- [ ] console.log shows message text  
- [ ] Server receives message
- [ ] Database has message record
- [ ] Message displays in chat

---

## Manual Testing Steps

### Step 1: Direct Backend Test

```bash
curl -X POST http://127.0.0.1:8000/group/TEST11/send-message/ \
  -d "message=hi" \
  -c cookies.txt
# Check response
```

### Step 2: Frontend Test

```javascript
// In browser console:
const msg = 'hi';
console.log('Test:', msg);
console.log('Length:', msg.length);
console.log('Trimmed:', msg.trim());
console.log('Is empty:', !msg.trim());
```

### Step 3: Database Check

```python
from chatapp.models import Message
msgs = Message.objects.filter(content='hi')
print(f"Count: {msgs.count()}")
for msg in msgs:
    print(f"  ID: {msg.id}, Content: '{msg.content}'")
```

---

## If Still Not Working

**Please provide:**

1. **Browser Console Output** (F12 → Console)
   - Full [SEND_MESSAGE] logs
   - Any red error messages

2. **Server Terminal Output**
   - Full [SEND_MESSAGE_AJAX] logs
   - Any error messages

3. **Database Check Result**
   - Run the query above
   - Tell me how many "hi" messages are in database

4. **What message text you used**
   - Exact text with quotes: "hi"
   - Or did you type " hi " with spaces?
   - Or "hi " with trailing space?

5. **What happens after sending**
   - Does input field clear?
   - Does button stay disabled?
   - Does anything appear in chat?

---

## Known Working Examples

These commands work and should save "hi" to database:

```bash
# From browser, run in console:
sendMessage()  # If form has "hi" typed

# From Django shell:
Message.objects.create(
    group_id=1,
    content='hi',
    user_name='Test',
    message_type='text'
)
```

---

## Performance Note

Short messages should be FASTER than long messages:
- Less text to process
- Faster transmission
- Quicker display

If short messages are slow or failing, it indicates a validation/logic issue, not network.

---

## Next Steps

1. ✅ Follow the [DEBUG_SHORT_MESSAGE.md](DEBUG_SHORT_MESSAGE.md) guide
2. ✅ Collect the diagnostic information above
3. ✅ Share console & server logs
4. ✅ I'll identify exact issue

**Testing now: http://127.0.0.1:8000/**
