# Bilingual Chat System - Quick Reference

## 🎯 Core Principle
**Always translate MEANING (NOT transliteration)**
- Use Gemini API for all translation
- Display filters only remove unwanted characters
- NO Tanglish anywhere in the system

---

## 🔧 Configuration

### Environment Variables Required
```
GEMINI_API_KEY=your_api_key_here
SUPPORTED_LANGUAGES=English,Tamil
DEFAULT_LANGUAGE=English
```

### Django Settings
- Framework: Django 3.x
- Database: SQLite (db.sqlite3)
- Translation API: Google Gemini (gemini-2.5-flash)

---

## 📊 Message Flow

### 1. User Sends Message
```
Input: Any text in any language
Language Mode: 'tamil' or 'english' (user's preference)
```

### 2. Language Detection
```
- is_valid_english_only(text) → Pure English?
- contains_tamil_script(text) → Contains Tamil?
- contains_tanglish(text) → Tanglish (Tamil in English letters)?
```

### 3. Meaning Translation (Gemini API)
**English Mode**: Any non-English → translate to English
- Tamil "வணக்கம்" → "Hello" ✅ (NOT "vanakkam")
- Tanglish "solren" → "tell me" ✅

**Tamil Mode**: Any non-Tamil → translate to Tamil
- English "Hello" → "வணக்கம்" ✅
- Tanglish "solren" → "சொல்" ✅

### 4. Display Filter (No Transliteration!)
**English Mode**: Remove Tamil script, keep English
**Tamil Mode**: Remove English letters, keep Tamil

### 5. User Sees Result
**English Mode**: Pure English text (no Tamil)
**Tamil Mode**: Pure Tamil text (no English)

---

## 🔐 Language Enforcement

### English Mode Processing
```python
def process_english_mode_message(content):
    if contains_tamil_script(content):
        # Translate Tamil meaning to English via Gemini
        return translate_to_english()
    elif contains_tanglish(content):
        # Translate Tanglish meaning to English via Gemini
        return translate_to_english()
    else:
        # Pure English - clean and return
        return ensure_english_only_display(content)
```

### Tamil Mode Processing
```python
def process_tamil_mode_message(content):
    if pure_tamil_only:
        # Keep as-is
        return content
    elif contains_english:
        # Translate to Tamil meaning via Gemini
        return translate_to_tamil()
    elif contains_tanglish:
        # Translate to Tamil meaning via Gemini
        return translate_to_tamil()
```

---

## 📱 Display Filtering (Character Removal Only)

### `ensure_english_only_display(text)`
```
Keep:   a-z, A-Z, 0-9, spaces, punctuation
Remove: Tamil Unicode range (U+0B80-U+0BFF)
Result: Pure English text (NO Tanglish!)
```

### `ensure_tamil_only_display(text)`
```
Keep:   Tamil Unicode characters
Remove: English letters (a-z, A-Z)
Result: Pure Tamil text
```

**Key Point**: Filters REMOVE characters, they do NOT transliterate

---

## 🌐 Gemini Translation API

### Translation Prompt
```python
prompt = f"""Translate the following text to {target_language}. 
Only provide the translated text, nothing else. Do not add explanations or quotes.

Text to translate: {text}"""
```

### API Call
```python
model = genai.GenerativeModel("gemini-2.5-flash")
response = model.generate_content(prompt)
translated_text = response.text.strip()
```

### Supported Languages
- English
- Tamil

---

## 💾 Database Storage

### Message Model Fields
```python
message.content              # Original input (what user typed)
message.english_content      # English meaning (stored)
message.tamil_content        # Tamil meaning (stored)
message.normalized_content   # Cleaned version
message.language_mode        # User's preference: 'tamil' or 'english'
message.timestamp            # When message was sent
message.user_name            # Who sent it
```

### User Language Mode
```python
AnonymousUser.language_mode  # 'tamil' or 'english'
```

---

## ⚡ Real-Time Updates

### Auto-Refresh (JavaScript)
```javascript
// Polls for new messages every 1.5 seconds
setInterval(() => {
    fetch('/get_new_messages/{group_code}')
    .then(response => response.json())
    .then(data => {
        // Display only filtered content
        if (data.messages) {
            updateChat(data.messages);
        }
    });
}, 1500);  // 1.5 seconds
```

### Visual Indicator
- 🔄 Spinning icon in header during refresh
- Updates every 1.5 seconds
- Non-blocking (user can type while updating)

---

## 🛡️ Error Handling

### Translation Failure
```python
try:
    success, translated, msg = translate_text(content, target_lang)
except Exception as e:
    # Graceful fallback: return original text
    return original_content, "Translation unavailable"
```

### API Key Missing
```python
if not GEMINI_API_KEY:
    logger.warning("API key not configured")
    # System continues with fallback behavior
```

---

## 🧪 Testing Commands

### Meaning Translation Test
```bash
python test_meaning_translation.py
```
Verifies display filters remove Tamil without transliterating

### Integration Test
```bash
python test_integration_meaning_translation.py
```
Verifies complete message processing flow with Gemini API

### System Check
```bash
python manage.py check
```
Verifies Django configuration (should show 0 issues)

### Syntax Verification
```bash
python -m py_compile chatapp/utils/tamil_detector.py
python -m py_compile chatapp/views.py
python -m py_compile chatapp/utils/translator.py
```

---

## 📞 API Limits

### Gemini API Rate Limiting
- Requests per minute: Check GCP quota
- Max tokens: 1000 (per translate call)
- Fallback: Returns original text if rate limited

### System Response
- Translation latency: < 2 seconds
- Display filter latency: < 10 milliseconds
- Auto-refresh interval: 1.5 seconds

---

## ✅ Verification Checklist

Before deploying to production:

- [ ] GEMINI_API_KEY environment variable set
- [ ] Django system check passes (0 issues)
- [ ] Python syntax validated
- [ ] Meaning translation test passes (no Tanglish)
- [ ] Integration test passes (complete flow)
- [ ] Display filters working (character removal only)
- [ ] Auto-refresh functioning (1.5s polling)
- [ ] Message storage preserving all versions
- [ ] User language modes enforced

---

## 🚀 Deployment Notes

### Production Requirements
1. Gemini API key configured
2. Django DEBUG=False
3. ALLOWED_HOSTS configured
4. Static files collected
5. Database migrated

### Performance Optimization
- Add message caching layer if > 10,000 messages/day
- Consider async translation for high volume
- Monitor API quota usage

### Monitoring
- Log all translation requests
- Track language mode distribution
- Monitor API response times
- Log any translation failures

---

## 📚 Core Files

| File | Purpose |
|---|---|
| `chatapp/views.py` | Message processing logic |
| `chatapp/utils/tamil_detector.py` | Language detection & display filters |
| `chatapp/utils/translator.py` | Gemini API integration |
| `chatapp/models.py` | Data models (Message, AnonymousUser, Group) |
| `chatapp/templates/group.html` | Chat UI + auto-refresh JavaScript |

---

## 🔗 Key Concepts

### Translation vs Transliteration
- **Translation**: Converts meaning (எ.கா. "Hello" → "வணக்கம்")
- **Transliteration**: Converts script (எ.கா. "வணக்கம்" → "vanakkam") ❌ AVOID

This system uses ONLY translation, never transliteration.

### Language Purity
- **Tamil Mode**: Show ONLY Tamil script, NO English or Tanglish
- **English Mode**: Show ONLY English, NO Tamil script or Tanglish
- **No Tanglish**: Never show Tamil mixed with English

### Dual-Storage Strategy
- **Display**: Language-specific (Tamil OR English)
- **Backend**: Both versions stored for searchability
- **Original**: Always preserved for audit

---

## 📞 Support

### Troubleshooting

**Q: Messages showing Tanglish (like "vanakkam")?**
A: Check display filter in `ensure_english_only_display()` - should only remove Tamil, not transliterate

**Q: Translation not working?**
A: Verify GEMINI_API_KEY is set and API quota available

**Q: Auto-refresh not updating?**
A: Check browser console for JavaScript errors, verify polling URL

**Q: Wrong language showing?**
A: Check user's language_mode in database - should be 'tamil' or 'english'

---

**Version**: 1.0 (April 2025)  
**Status**: ✅ Production Ready
