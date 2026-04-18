# Chat Application - Feature Documentation

## Overview
A Django-based real-time chat application with **dual-language support** (English & Tamil), **press-and-hold voice recording**, **automatic translation**, and **text-to-speech synthesis**.

---

## 🎯 Key Features

### 1. **Language Mode System**
- **English Mode**: Users see English only; Tamil/Tanglish auto-converts to English
- **Tamil Mode**: Users see Tamil only; English/Tanglish auto-converts to Tamil

### 2. **Tanglish Blocking** ⛔
- **Client-side validation**: Real-time checks while typing
- **Server-side enforcement**: Rejects messages with Tanglish (Tamil words in English letters)
- **Literal detection**: Blocks "tanglish" and "tangenglish" keywords explicitly
- **Voice transcript validation**: Rejects Tanglish speech-to-text output

### 3. **Text Messages**
- **Send**: Type English or Tamil; auto-translates to other language for storage
- **Translate Button**: Manually translate any message with `🌐 Translate`
- **Tanglish Rejection**: "⚠️ Tanglish not allowed. Please use English or Tamil only."

### 4. **Voice Messages** 🎤
- **Record**: Press & hold mic button to record
- **Transcription** (optional): Browser's SpeechRecognition transcribes to text
- **Translation**: Transcribed text is translated via Gemini
- **Playback**: Click ▶️ to play; drag to seek

### 5. **Voice Synthesis** (NEW)
- **Endpoint**: `POST /group/<code>/synthesize-voice/`
- **Input**: Text + target language (English/Tamil)
- **Output**: Synthesized audio saved as voice message using gTTS
- **Tanglish Check**: Rejects Tanglish in text before synthesis

### 6. **Group Lifecycle**
- **New Groups**: Auto-delete after **1 day** (1440 minutes) if no messages
- **Inactive Groups**: Auto-delete after **12 hours** (720 minutes) with no activity
- **Online Timeout**: Users marked offline after 5 minutes of inactivity

---

## 📋 Setup Instructions

### Prerequisites
```bash
# Install Python 3.8+
# Install pip packages
pip install django django-cors-headers google-generativeai gtts
```

### Environment Variables
```bash
# Create .env or set in shell
export GEMINI_API_KEY="your-gemini-api-key-here"
export SUPPORTED_LANGUAGES="English,Tamil"
export DEFAULT_LANGUAGE="English"
```

### Database Setup
```bash
python manage.py migrate
```

### Run Server
```bash
python manage.py runserver
```

Then open: `http://localhost:8000`

---

## 🔄 API Endpoints

### Message APIs
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/group/<code>/send-message/` | Send text (auto-rejects Tanglish) |
| POST | `/group/<code>/upload-voice/` | Upload recorded audio (auto-rejects Tanglish transcripts) |
| POST | `/group/<code>/synthesize-voice/` | **[NEW]** Synthesize & save voice from text |
| POST | `/group/<code>/translate/` | Translate a message |
| POST | `/group/<code>/delete-message/` | Delete a message |

### Status APIs
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/group/<code>/get-messages/` | Fetch messages (lang-filtered) |
| GET | `/group/<code>/online-users/` | List online users |
| GET | `/group/<code>/cleanup-status/` | Check group auto-delete status |

---

## 🧪 Testing Tanglish Rejection

### Test Case 1: Text Message Tanglish
```bash
curl -X POST http://localhost:8000/group/test/send-message/ \
  -H "X-CSRFToken: <token>" \
  --data "message=solhra+enna+solren"
# Expected: ❌ "Tanglish is not allowed..."
```

### Test Case 2: Voice Upload with Tanglish Transcript
```bash
# Record English phrase, browser transcribes to "enna vanakkam"
# Expected: ❌ "Tanglish not allowed in voice messages..."
```

### Test Case 3: Valid Tamil
```bash
curl -X POST http://localhost:8000/group/test/send-message/ \
  -H "X-CSRFToken: <token>" \
  --data "message=வணக்கம்"
# Expected: ✅ Message sent & translated to English
```

### Test Case 4: Valid English
```bash
curl -X POST http://localhost:8000/group/test/send-message/ \
  -H "X-CSRFToken: <token>" \
  --data "message=Hello+world"
# Expected: ✅ Message sent & translated to Tamil
```

### Test Case 5: Synthesize Voice (NEW)
```bash
curl -X POST http://localhost:8000/group/test/synthesize-voice/ \
  -H "X-CSRFToken: <token>" \
  --data "text=Hello+everyone&language=English"
# Expected: ✅ MP3 generated, saved as voice message
```

---

## 🗂️ File Structure

```
chatapp/
├── models.py              # Group, Message, AnonymousUser
├── views.py               # All endpoint handlers (includes new synthesize_voice_message)
├── urls.py                # Route definitions (includes /synthesize-voice/)
├── templates/
│   ├── group.html         # Chat UI + mic recording JS
│   └── ...
├── utils/
│   ├── translator.py      # translate_text(), synthesize_speech_with_gtts()
│   ├── tamil_detector.py  # contains_tanglish(), is_valid_english_only()
│   └── ...
└── migrations/
    └── 0013_...           # Latest schema
```

---

## 🔧 Technical Details

### Tanglish Detection (Client)
- Client-side regex patterns in `group.html`
- Checks against 20+ common Tanglish words
- Shows inline error: "⚠️ Tanglish detected..."

### Tanglish Rejection (Server)
- Server imports `contains_tanglish()` from `tamil_detector.py`
- Applied in:
  - `send_message_ajax()` (text messages)
  - `upload_voice_message()` (voice transcripts)
  - `synthesize_voice_message()` (TTS text)
- Returns HTTP 400 with clear error message

### Text-to-Speech
- Uses **gTTS** (Google Translate TTS) as fallback
- Generates MP3 audio files
- Saves in `media/voice_messages/`
- Can be replaced with Google Cloud Text-to-Speech API for production

### Group Auto-Delete
- **NEW_GROUP_DELETE_MINUTES = 1440** (1 day)
- **INACTIVITY_DELETE_MINUTES = 720** (12 hours)
- Check happens on every request via `check_and_cleanup_group()`

---

## 📱 Frontend Usage

### Sending Text
1. Type message in input field
2. Press Enter or click ✈️ button
3. Auto-translated & stored with both languages

### Recording Voice
1. **Press & Hold** 🎤 button
2. Speak your message
3. Release to upload
4. Optional: Browser transcribes to text
5. Text translated & TTS synthesized (if available)

### Synthesizing Voice from Text
1. (Backend API only for now)
2. POST `/group/<code>/synthesize-voice/` with text + language
3. Receives MP3 URL to stream/save

---

## ⚠️ Limitations & Future Work

- **gTTS** only; consider Google Cloud TTS for production
- Voice synthesis quality depends on gTTS service
- Tanglish detection uses regex; Gemini API can improve accuracy
- No user authentication (anonymous sessions only)

---

## 📞 Support

For issues or feature requests, refer to the inline code comments and debug logs in `chatapp/` directory.

---

**Last Updated**: April 17, 2026
