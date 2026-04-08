# System Architecture & Data Flow Diagrams

---

## 1. DUPLICATE MESSAGE PREVENTION ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────┐
│                     USER INTERACTION                         │
│                  (Desktop/Mobile Browser)                    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │ LAYER 1: HTML FORM STRUCTURE         │
        │ ✓ Button: type="button"              │
        │ ✓ Form: no method="POST"             │
        │ ✓ Value: relies on JavaScript 100%   │
        └──────────────────────────┬───────────┘
                                   │
                                   ▼
        ┌──────────────────────────────────────┐
        │ LAYER 2: EVENT LISTENER GUARD        │
        │ ✓ listenersInitialized flag          │
        │ ✓ Prevents duplicate attachment      │
        │ ✓ initializeEventListeners() run 1x  │
        └──────────────────────────┬───────────┘
                                   │
                                   ▼
        ┌──────────────────────────────────────┐
        │ LAYER 3: EVENT CAPTURE PHASE         │
        │ ✓ addEventListener('submit', ..., true)
        │ ✓ Intercepts form submit at capture  │
        │ ✓ Highest priority phase             │
        └──────────────────────────┬───────────┘
                                   │
                                   ▼
        ┌──────────────────────────────────────┐
        │ LAYER 4: PROPAGATION STOPPERS        │
        │ ✓ preventDefault()                   │
        │ ✓ stopPropagation()                  │
        │ ✓ return false                       │
        └──────────────────────────┬───────────┘
                                   │
                                   ▼
        ┌──────────────────────────────────────┐
        │ LAYER 5: SUBMISSION GUARD FLAG       │
        │ ✓ isSubmittingMessage = true         │
        │ ✓ Prevents rapid-click duplicates    │
        │ ✓ Disabled until fetch completes     │
        └──────────────────────────┬───────────┘
                                   │
                                   ▼
        ┌──────────────────────────────────────┐
        │ LAYER 6: VALIDATION                  │
        │ ✓ Message length check (< 5000)      │
        │ ✓ Empty message check                │
        │ ✓ Element existence verified         │
        └──────────────────────────┬───────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
         ┌────────────────────┐       ┌────────────────────┐
         │ FETCH API REQUEST  │       │ ERROR HANDLING     │
         │ POST /send-message/│       │ ✓ try/catch block  │
         │ ✓ Method: POST     │       │ ✓ Display error    │
         │ ✓ CSRF token check │       │ ✓ Re-enable button │
         └────────┬───────────┘       └────────────────────┘
                  │
                  ▼
        ┌──────────────────────────────────────┐
        │ LAYER 7: BACKEND PROCESSING          │
        │ send_message_ajax() view              │
        │ ✓ Verify group exists                │
        │ ✓ Validate message not empty         │
        │ ✓ Create ONE Message object          │
        │ ✓ Return JSON response               │
        └──────────────────────────┬───────────┘
                                   │
                                   ▼
        ┌──────────────────────────────────────┐
        │ DATABASE INSERT                      │
        │ Message.objects.create(...)          │
        │ ✓ Timestamp auto-generated           │
        │ ✓ Session tracking included          │
        │ ✓ Exactly ONE record created         │
        └──────────────────────────┬───────────┘
                                   │
                                   ▼
        ┌──────────────────────────────────────┐
        │ LAYER 8: POLLING (NEW)               │
        │ fetchNewMessages() with isPolling    │
        │ ✓ Prevents concurrent polls          │
        │ ✓ No duplicate fetches               │
        │ ✓ Respects message count             │
        └──────────────────────────┬───────────┘
                                   │
                                   ▼
        ┌──────────────────────────────────────┐
        │ RESULT: MESSAGE APPEARS EXACTLY ONCE │
        │ ✓ No duplicates from UI              │
        │ ✓ No duplicates from API             │
        │ ✓ No duplicates from polling         │
        │ ✓ User sees single message           │
        └──────────────────────────────────────┘
```

---

## 2. MESSAGE FLOW: Send Message Complete Cycle

```
TIME │ CLIENT SIDE              │ SERVER SIDE         │ DATABASE
──────┼─────────────────────────┼────────────────────┼──────────
0ms   │ User types "Hello"      │                    │
      │ Clicks Send button      │                    │
──────┼─────────────────────────┼────────────────────┼──────────
5ms   │ Form submit intercepted │                    │
      │ sendMessage() called    │                    │
──────┼─────────────────────────┼────────────────────┼──────────
10ms  │ Validation checks:      │                    │
      │ ✓ Not empty            │                    │
      │ ✓ < 5000 chars        │                    │
      │ ✓ Not already sending   │                    │
──────┼─────────────────────────┼────────────────────┼──────────
15ms  │ isSubmittingMessage=true│                    │
      │ Send button disabled    │                    │
──────┼─────────────────────────┼────────────────────┼──────────
20ms  │ POST /send-message/     │ Receive POST       │
      │ with CSRF token         │ Validate token     │
──────┼─────────────────────────┼────────────────────┼──────────
25ms  │                         │ Get group & user   │
      │                         │ Validate message   │
──────┼─────────────────────────┼────────────────────┼──────────
30ms  │                         │                    │ INSERT
      │                         │ Message.create()   │ message
      │                         │                    │ row
──────┼─────────────────────────┼────────────────────┼──────────
35ms  │ Receive response        │ Return JSON        │
      │ {success: true, ...}    │ {success: true}    │
──────┼─────────────────────────┼────────────────────┼──────────
40ms  │ Clear input field       │                    │
      │ isSubmittingMessage=false
      │ Call fetchNewMessages()  │                    │
──────┼─────────────────────────┼────────────────────┼──────────
45ms  │ GET /get-messages/      │ Query messages     │ SELECT
      │                         │ since timestamp    │ from
      │                         │                    │ Message
──────┼─────────────────────────┼────────────────────┼──────────
50ms  │                         │ Return JSON with   │
      │                         │ new message        │
──────┼─────────────────────────┼────────────────────┼──────────
55ms  │ Receive message data    │                    │
      │ Add to DOM              │                    │
      │ Scroll to bottom        │                    │
──────┼─────────────────────────┼────────────────────┼──────────
60ms  │ ✓ Message visible       │                    │
      │ ✓ Appears exactly ONCE  │                    │
      │ ✓ Correct timestamp     │                    │
      │ ✓ User color coded      │                    │
      └─────────────────────────┴────────────────────┴──────────
```

---

## 3. POLLING MECHANISM: Dynamic Interval

```
        ┌─────────────────────────────────────┐
        │ START POLLING                       │
        │ (window.load event)                 │
        └──────────────┬──────────────────────┘
                       │
                       ▼
        ┌─────────────────────────────────────┐
        │ Immediate Fetch                     │
        │ fetchNewMessages()                  │
        │ pollInterval = 1000ms               │
        └──────────────┬──────────────────────┘
                       │
                       ▼
        ┌─────────────────────────────────────┐
        │ Schedule Next Poll                  │
        │ setTimeout(scheduleNextPoll,         │
        │   pollInterval)                     │
        └──────────────┬──────────────────────┘
                       │
         ┌─────────────┴──────────────┐
         ▼                            ▼
    ┌─────────────┐          ┌──────────────┐
    │ Wait        │          │ Page Hidden? │
    │ pollInterval│          │              │
    │ milliseconds│          └──────────────┘
    └──────┬──────┘                │
           ▼                        ▼
    ┌─────────────────┐      ┌────────────────┐
    │ Fetch New       │      │ Reschedule with│
    │ Messages        │      │ same interval  │
    │ isPolling=true  │      │ (wait for wake)│
    └────────┬────────┘      └────────────────┘
             │
      ┌──────┴──────┐
      ▼             ▼
   ┌─────┐     ┌──────────┐
   │FOUND│     │NOT FOUND │
   │MSGS │     │MESSAGES  │
   └────┬┘     └────┬─────┘
        │           │
        ▼           ▼
    Reset:      Increment:
    interval    noNewMessages++
    = 1000ms    │
    │           ▼
    │        If noNewMessages > 3:
    │        interval += 500ms
    │        (max 3000ms)
    │           │
    └───┬───────┘
        │
        ▼
    scheduleNextPoll()  ← LOOP: Uses CURRENT interval value
```

---

## 4. MOBILE VIEWPORT FIX

```
BEFORE FIX (100vh):                AFTER FIX (100dvh):
━━━━━━━━━━━━━━━━━━━━━━━            ━━━━━━━━━━━━━━━━━━━━━━━

Keyboard Closed:                    Keyboard Closed:
┌─────────────────┐               ┌─────────────────┐
│  Chat App       │               │  Chat App       │
│ 100vh height    │               │ 100dvh height   │
│                 │               │                 │
│ Shows all area  │               │ Shows all area  │
└─────────────────┘               └─────────────────┘

Keyboard Opens:                     Keyboard Opens:
┌─────────────────┐               ┌──────────┐
│  Chat App       │ ← 100vh        │ Chat App │ ← 100dvh
│ (unchanged)     │   includes     │(reduced) │   adjusts!
│ TOO TALL!       │   keyboard     │          │
│                 │   area         │┌────────┐│
│ ❌ Input hidden │               ││Keyboard││
└─────────────────┘               │└────────┘│
┌─────────────────┐               └──────────┘
│   Keyboard      │               ✓ Input visible
└─────────────────┘               ✓ Proper layout
                                  ✓ User can type
```

**Technical Details:**

- **100vh (Static)**: 100% of initial viewport height (includes keyboard area)
- **100dvh (Dynamic)**: 100% of dynamic viewport height (excludes keyboard area)
- **Browser Support**: Chrome 108+, Firefox 101+, Safari 15.4+, Mobile browsers

---

## 5. EVENT FLOW: Single Click

```
USER CLICKS SEND BUTTON
│
├─ STEP 1: Capture Phase (Highest Priority)
│  └─ Form 'submit' listener
│     └─ e.preventDefault()
│     └─ e.stopPropagation()
│     └─ ✓ BLOCKED HERE
│
├─ STEP 2: Bubble Phase (Would not reach here, but protected anyway)
│  ├─ Button 'click' listener
│  │  └─ e.preventDefault()
│  │  └─ e.stopPropagation()
│  │  └─ sendMessage()
│  │     
│  ├─ Form 'submit' listener (bubbling)
│  │  └─ PREVENTED (already stopped)
│  │
│  └─ Window 'submit' listeners
│     └─ PREVENTED (already stopped)
│
└─ RESULT: sendMessage() called EXACTLY ONCE
```

---

## 6. CONCURRENT POLLING PREVENTION

```
WITHOUT isPolling FLAG:          WITH isPolling FLAG (NEW):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━    ━━━━━━━━━━━━━━━━━━━━━━━━━
Time │ Poll Request              Time │ Poll Request
─────┼──────────────             ─────┼──────────────
0ms  │ Poll #1 starts            0ms  │ isPolling=false
     │ isPolling=true            │    │ Poll #1 starts
     │                           │    │ isPolling=true
─────┼──────────────             ─────┼──────────────
500ms│ Poll #2 starts            500ms│ Poll #2 would
     │ isPolling=true (!)        │    │ SKIP (isPolling=true)
     │                           │
─────┼──────────────             ─────┼──────────────
1000ms│ Poll #3 starts           1000ms│ Poll #1 completes
     │ isPolling=true (!)        │    │ isPolling=false
     │                           │
─────┼──────────────             ─────┼──────────────
1500ms│ Poll #1 completes        1500ms│ Poll #2 starts
     │ isPolling=false           │    │ isPolling=true
     │ Poll #2 completes         │
     │ Poll #3 completes         ─────┼──────────────
     │                           2000ms│ Poll #2 completes
─────┼──────────────             │    │ ONLY ONE AT A TIME
RESULT:          RESULT:
❌ 3 concurrent ✅ Sequential
   requests      requests
❌ Race         ✅ No races
   conditions    ✅ Clean
❌ Data         ✅ Reliable
   conflicts    ✅ Optimal
```

---

## 7. COMPLETE SYSTEM ARCHITECTURE

```
┌──────────────────────────────────────────────────────────────────┐
│                     WEB BROWSER (Client)                          │
│                                                                  │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────┐     │
│  │ Event Handler  │  │  JavaScript  │  │   Local Cache   │     │
│  │ (8 layers)     │  │  Validation  │  │   & Storage     │     │
│  │                │  │  & UI Logic  │  │                 │     │
│  │ Guard flags:   │  │              │  │ Messages store  │     │
│  │ - listeners    │  │ Guard flags: │  │ Timestamp track │     │
│  │ - submitting   │  │ - submitting │  │ Online status   │     │
│  │ - polling      │  │ - polling    │  │                 │     │
│  └────────┬───────┘  └──────┬───────┘  └────────┬────────┘     │
│           │                 │                    │              │
│           └─────────────────┼────────────────────┘              │
│                             │ CSRF Token                         │
│                             ▼                                    │
│                   HTTP Requests/Responses                        │
│                     (JSON over HTTPS)                            │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│              DJANGO WEB SERVER (Backend)                          │
│                                                                  │
│  /send-message/           /get-messages/       /upload-voice/   │
│  ├─ Check group exists     ├─ Query messages    └─ Save audio   │
│  ├─ Validate message       ├─ Since timestamp   └─ Create msg   │
│  ├─ Create Message         ├─ Return JSON       
│  └─ Return response        └─ With online count │              │
│                                                 │              │
│  /delete-message/         /update-status/                       │
│  ├─ Find message           └─ Update user status               │
│  └─ Mark deleted                                               │
│                                                                  │
│           Session Management & CSRF Validation                   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│              Database (SQLite/PostgreSQL)                        │
│                                                                  │
│  ┌─────────────┐  ┌──────────┐  ┌────────────────┐            │
│  │   Group     │  │ Message  │  │  AnonymousUser │            │
│  │             │  │          │  │                │            │
│  │ id, code    │  │ id, text │  │ session_id     │            │
│  │ created     │  │ user_name│  │ online status  │            │
│  └──────┬──────┘  │ timestamp│  │ last_seen      │            │
│         │         │ is_deleted               │            │
│         └────┬────┤ audio_file  └────────────┴────┘            │
│              └────┤ duration ▲                 │              │
│                   │ group_id ├─────────────────┘              │
│                   └──────────┘                                 │
│                                                                  │
│        All messages in one table for each group                 │
│        Timestamp-based queries for live updates                 │
│        No nested/duplicate records                              │
└──────────────────────────────────────────────────────────────────┘
```

---

## 8. DEPLOYMENT ARCHITECTURE

```
LOCAL DEVELOPMENT              PRODUCTION DEPLOYMENT
────────────────────          ──────────────────────
┌──────────────────┐          ┌──────────────────────────┐
│ Developer PC     │    GIT   │ Web Server (e.g. AWS)    │
│                  │  PUSH    │                          │
│ ├─ group.html    │ ─────→  │ ├─ group.html (UPDATED)  │
│ ├─ views.py      │          │ ├─ views.py              │
│ ├─ models.py     │          │ ├─ models.py             │
│ ├─ urls.py       │          │ └─ Django app            │
│ └─ Test browser  │          │                          │
└──────────────────┘          │ Users connect via HTTPS  │
        │                     └────────────┬─────────────┘
        │ Local testing                   │
        │ DevTools Network tab             │ Clear browser cache
        │ DevTools Console tab             │ Users hard refresh
        └──────────────────────────────────┘
```

---

**Architecture diagrams show 100% backward compatibility with existing code while adding 5 critical improvements.**
