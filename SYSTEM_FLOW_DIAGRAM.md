# 🇹🇳💬 Bilingual Chat System - Visual Guide

## **Complete Message Flow**

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                        BILINGUAL CHAT SYSTEM FLOW                             ║
╚═══════════════════════════════════════════════════════════════════════════════╝

1️⃣  USER JOINS CHAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    ┌──────────────────────────┐
    │ User enters info:        │
    │ - Name: "Vignesh"        │
    │ - Group: "TamilChat"     │
    │ - Mode: "Tamil Mode" 🇹🇳  │
    └──────────────┬───────────┘
                   │
                   ▼
    ┌──────────────────────────────────┐
    │ Session created:                 │
    │ language_mode = "tamil"          │
    └──────────────┬───────────────────┘
                   │
                   ▼
    ┌──────────────────────────────────────────┐
    │ group() view called                      │
    │ Loads: user_language_mode = "tamil"      │
    └──────────────┬───────────────────────────┘
                   │
                   ▼


2️⃣  FILTER EXISTING MESSAGES (Initial Page Load)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    ┌─────────────────────────────────────────┐
    │ Database Message:                       │
    │ - content: "Hello வணக்கம்"              │
    │ - english: "Hello Hello"                │
    │ - tamil: "வணக்கம் வணக்கம்"              │
    └──────────────┬──────────────────────────┘
                   │
                   ▼
    ┌─────────────────────────────────────────┐
    │ Check user mode: TAMIL                  │
    │ user_language_mode == "tamil" ✓         │
    └──────────────┬──────────────────────────┘
                   │
                   ▼
    ┌──────────────────────────────────────────┐
    │ Apply TAMIL FILTER:                      │
    │ ensure_tamil_only_display(msg.tamil)     │
    │                                          │
    │ Input:  "வணக்கம் வணக்கம்"                │
    │ Output: "வணக்கம் வணக்கம்"  ✓ ONLY TAMIL   │
    │ (Removes: spaces, punctuation)           │
    └──────────────┬───────────────────────────┘
                   │
                   ▼
    ┌──────────────────────────────────────────┐
    │ Pass to template:                        │
    │ msg.content = "வணக்கம் வணக்கம்"          │
    │              (Already filtered!)         │
    └──────────────┬───────────────────────────┘
                   │
                   ▼
    ┌──────────────────────────────────────────┐
    │ USER SEES: "வணக்கம் வணக்கம்"             │
    │ ✓ Only Tamil characters                  │
    │ ✓ No English letters                     │
    │ ✓ Clean & readable                      │
    └──────────────────────────────────────────┘


3️⃣  SEND MESSAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    ┌──────────────────────────┐
    │ User types message:      │
    │ "Hello வணக்கம்"           │
    │ Then presses SEND ✈️     │
    └──────────────┬───────────┘
                   │
                   ▼ (JavaScript sendMessage)
                   │
    ┌──────────────────────────────────────┐
    │ POST /group/TamilChat/send-message/  │
    └──────────────┬───────────────────────┘
                   │
                   ▼
    ┌────────────────────────────────────────────┐
    │ Django Backend (send_message_ajax):        │
    │                                            │
    │ Step 1: Check MODE                         │
    │ language_mode == "tamil" ✓                 │
    │                                            │
    │ Step 2: Process Tamil Mode                 │
    │ process_tamil_mode_message(                │
    │   "Hello வணக்கம்"                          │
    │ )                                          │
    │                                            │
    │ Step 3: Auto-convert English→Tamil        │
    │ Using Google Gemini API                    │
    │ "Hello" → "வணக்கம்"                        │
    │                                            │
    │ Step 4: Return values:                     │
    │ - english_backend = "Hello Hello"          │
    │ - tamil_display = "வணக்கம் வணக்கம்"       │
    │ - warning_msg = "Converting English→Tamil"│
    │                                            │
    │ Step 5: Apply Display Filter               │
    │ ensure_tamil_only_display(tamil_display)   │
    │                                            │
    │ Step 6: Save to Database                   │
    │ Message.create(                            │
    │   content = "Hello வணக்கம்"                 │
    │   english_content = "Hello Hello"          │
    │   tamil_content = "வணக்கம் வணக்கம்"        │
    │ )                                          │
    └──────────────┬───────────────────────────┘
                   │
                   ▼
    ┌────────────────────────────────────────┐
    │ Return JSON Response:                  │
    │ {                                      │
    │   "success": true,                     │
    │   "message": {                         │
    │     "content": "வணக்கம் வணக்கம்",       │
    │     "tamil": "வணக்கம் வணக்கம்",         │
    │     "english": "Hello Hello",          │
    │     "warning": "Converting..."         │
    │   }                                    │
    │ }                                      │
    └──────────────┬───────────────────────┘
                   │
                   ▼ (JavaScript receives)
                   │
    ┌──────────────────────────────────────┐
    │ Display Sent Message:                │
    │ Message Bubble: "வணக்கம் வணக்கம்" 🟢  │
    │ (Green = Sender's message)           │
    └──────────────────────────────────────┘


4️⃣  FETCH AND DISPLAY NEW MESSAGES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    ┌──────────────────────────────────┐
    │ JavaScript polls every 2 seconds │
    │ GET /group/TamilChat/get-messages│
    └──────────────┬───────────────────┘
                   │
                   ▼
    ┌───────────────────────────────────────────┐
    │ Django Backend (get_new_messages):        │
    │                                           │
    │ For each message in database:             │
    │                                           │
    │ Get user's language_mode = "tamil"        │
    │ Get message versions:                     │
    │   - msg.tamil_content                     │
    │   - msg.english_content                   │
    │                                           │
    │ Apply TAMIL mode filter:                  │
    │ display = ensure_tamil_only_display(      │
    │   msg.tamil_content                       │
    │ )                                         │
    │                                           │
    │ Return in JSON:                           │
    │ {                                         │
    │   "content": <filtered>,  ← ONLY TAMIL   │
    │   "tamil": <full tamil>,                  │
    │   "english": <full english>               │
    │ }                                         │
    └───────────────┬──────────────────────────┘
                    │
                    ▼
    ┌──────────────────────────────────────┐
    │ JavaScript receives & displays:      │
    │                                      │
    │ Message from "OtherUser": 🔵          │
    │ "வணக்கம் வணக்கம்"                    │
    │ (Blue = Receiver's message)          │
    │ (ONLY Tamil visible)                 │
    └──────────────────────────────────────┘


5️⃣  TRANSLATE BUTTON
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    ┌──────────────────────────────┐
    │ User sees message in Tamil:  │
    │ "வணக்கம் வணக்கம்" 🔵         │
    │                              │
    │ User clicks [🌐 Translate]   │
    └──────────────┬───────────────┘
                   │
                   ▼
    ┌──────────────────────────────────┐
    │ System shows translation:        │
    │ (Hidden by default)              │
    │                                  │
    │ Original: "வணக்கம் வணக்கம்"    │
    │ Translation: "Hello Hello"       │
    │                                  │
    │ User can now see BOTH versions!  │
    └──────────────────────────────────┘


╔═══════════════════════════════════════════════════════════════════════════════╗
║                    SAME MESSAGE, DIFFERENT DISPLAYS                           ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Database stores ONCE:
┌────────────────────────────────────────────────────────┐
│ Message ID: 42                                         │
│ From: Vignesh                                          │
│ Timestamp: 2:30 PM                                     │
│                                                        │
│ Original:         "Hello வணக்கம்"                      │
│ english_content:  "Hello Hello"                        │
│ tamil_content:    "வணக்கம் வணக்கம்"                   │
└────────────────────────────────────────────────────────┘

But displays DIFFERENTLY based on MODE:

🇹🇳 TAMIL MODE User Sees:          🔤 ENGLISH MODE User Sees:
┌──────────────────────────┐       ┌──────────────────────────┐
│ Vignesh                  │       │ Vignesh                  │
│                          │       │                          │
│ வணக்கம் வணக்கம்           │       │ Hello Hello              │
│                          │       │                          │
│ 🌐 Translate              │       │ 🌐 Translate              │
│   See: "Hello Hello"           │   See: "வணக்கம் வணக்கம்"    │
└──────────────────────────┘       └──────────────────────────┘

SAME MESSAGE → DIFFERENT DISPLAY ✓


╔═══════════════════════════════════════════════════════════════════════════════╗
║                         FILES & KEY FUNCTIONS                                 ║
╚═══════════════════════════════════════════════════════════════════════════════╝

┌─ DISPLAY FILTERS ─────────────────────────────────────┐
│ File: chatapp/utils/tamil_detector.py                │
│                                                       │
│ ensure_tamil_only_display(text)                       │
│   → Removes all English letters                       │
│   → Keeps Tamil + spaces + punctuation                │
│   → Returns: ONLY TAMIL                               │
│                                                       │
│ ensure_english_only_display(text)                     │
│   → Removes Tamil script (U+0B80-U+0BFF)              │
│   → Keeps English + numbers + punctuation             │
│   → Returns: ONLY ENGLISH                             │
└───────────────────────────────────────────────────────┘

┌─ MESSAGE PROCESSING ──────────────────────────────────┐
│ File: chatapp/views.py                               │
│                                                       │
│ process_tamil_mode_message(content)                   │
│   → Converts English to Tamil                         │
│   → Returns: (eng_backend, tamil_display, warn)       │
│                                                       │
│ process_english_mode_message(content)                 │
│   → Converts Tamil to English                         │
│   → Returns: (eng_display, tamil_backend, warn)       │
└───────────────────────────────────────────────────────┘

┌─ PAGE DISPLAY ────────────────────────────────────────┐
│ File: chatapp/views.py - group()                     │
│                                                       │
│ Filters all messages based on language_mode          │
│ before passing to template                           │
│                                                       │
│ Template shows pre-filtered content                  │
│ No raw data displayed                                │
└───────────────────────────────────────────────────────┘

┌─ MESSAGE SENDING ────────────────────────────────────┐
│ File: chatapp/views.py - send_message_ajax()        │
│                                                      │
│ 1️⃣  Check language mode                              │
│ 2️⃣  Process message (with auto-conversion)           │
│ 3️⃣  Apply display filter                             │
│ 4️⃣  Save to database (both versions)                 │
│ 5️⃣  Return filtered response                         │
└──────────────────────────────────────────────────────┘


╔═══════════════════════════════════════════════════════════════════════════════╗
║                              SYSTEM STATUS                                    ║
╚═══════════════════════════════════════════════════════════════════════════════╝

✅ Tamil Mode Enforcement
   ✓ Converts English to Tamil
   ✓ Displays ONLY Tamil characters
   ✓ Stores both versions in database

✅ English Mode Enforcement
   ✓ Converts Tamil to English
   ✓ Displays ONLY English characters
   ✓ Stores both versions in database

✅ Page Load Filtering
   ✓ Filters all messages on initial load
   ✓ Applies language mode rules immediately
   ✓ Template displays pre-filtered content

✅ AJAX Message Updates
   ✓ Filters new messages in real-time
   ✓ Maintains language purity
   ✓ Returns correct version for user's mode

✅ Multi-User Support
   ✓ Each user sees their language only
   ✓ All users see same message but filtered
   ✓ Perfect for bilingual teams

✅ Database Integrity
   ✓ Stores original message
   ✓ Stores English version
   ✓ Stores Tamil version
   ✓ Full audit trail maintained

═══════════════════════════════════════════════════════════════════════════════
PRODUCTION READY ✅
═══════════════════════════════════════════════════════════════════════════════

