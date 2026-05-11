# How to Add Extra Languages for Voice Messages and Text Translation

This guide explains exactly where and how to add new languages to the TRANIT chat application.

## Quick Overview

The application supports languages in **TWO** places:
1. **Voice Messages** - Audio file storage for each language
2. **Text Translation** - Automatic translation and display

---

## Part 1: Adding Voice Message Language Support

### What happens with voice messages:
- Users record voice messages in their selected language
- The system stores them as audio files with language-specific naming
- Other users can play back the voice message in their own language (if available)

### Files that need updating:

#### File 1: `chatapp/models.py` (Message Model - Line ~115)

**Current audio fields:**
```python
audio_file_english = models.FileField(upload_to='voice_messages/', blank=True, null=True, help_text='English version of voice message')
audio_file_tamil = models.FileField(upload_to='voice_messages/', blank=True, null=True, help_text='Tamil version of voice message')
audio_file_hindi = models.FileField(upload_to='voice_messages/', blank=True, null=True, help_text='Hindi version of voice message')
audio_file_malayalam = models.FileField(upload_to='voice_messages/', blank=True, null=True, help_text='Malayalam version of voice message')
audio_file_kannada = models.FileField(upload_to='voice_messages/', blank=True, null=True, help_text='Kannada version of voice message')
audio_file_telugu = models.FileField(upload_to='voice_messages/', blank=True, null=True, help_text='Telugu version of voice message')
```

**To add Spanish (Example):**
```python
audio_file_spanish = models.FileField(upload_to='voice_messages/', blank=True, null=True, help_text='Spanish version of voice message')
```

**To add German:**
```python
audio_file_german = models.FileField(upload_to='voice_messages/', blank=True, null=True, help_text='German version of voice message')
```

⚠️ **IMPORTANT:** Use lowercase language names without spaces (spanish, german, portuguese, french, etc.)

### Step 1: Run Migration Commands
```bash
# Navigate to project directory
cd "d:\vignesh_django_ project\building a chat web application\chat 3 4\chat 3\chatproject"

# Activate virtual environment
env\Scripts\activate

# Generate migration
python manage.py makemigrations

# Apply migration to database
python manage.py migrate
```

Expected output:
```
Migrations for 'chatapp':
  chatapp\migrations\00XX_message_audio_file_spanish.py
    + Add field audio_file_spanish to message
    
Operations to perform:
  Apply all migrations: admin, auth, chatapp, contenttypes, sessions
Running migrations:
  Applying chatapp.00XX_message_audio_file_spanish... OK
```

---

## Part 2: Adding Text Translation Language Support

### What happens with text translation:
- Users select their language mode when joining a group
- Messages are translated to their preferred language using Google Gemini
- Translation results are cached for performance

### Files that need updating:

#### File 1: `chatapp/templates/chat.html` (Line ~290)

**Current language options:**
```html
<select required="" id="language_mode" name="language_mode">
    <option value="">Select Language</option>
    <option value="english">🌐 English - Group accepts English input only</option>
    <option value="gujarati">🌍 Gujarati - Group accepts Gujarati input only</option>
    <option value="hindi">🌍 Hindi - Group accepts Hindi input only</option>
    <option value="kannada">🌍 Kannada - Group accepts Kannada input only</option>
    <option value="malayalam">🌍 Malayalam - Group accepts Malayalam input only</option>
    <option value="tamil">🇮🇳 Tamil - Group accepts Tamil input only</option>
</select>
```

**To add Spanish:**
```html
<option value="spanish">🇪🇸 Spanish - Group accepts Spanish input only</option>
```

**To add German:**
```html
<option value="german">🇩🇪 German - Group accepts German input only</option>
```

**To add French:**
```html
<option value="french">🇫🇷 French - Group accepts French input only</option>
```

#### File 2: `chatapp/utils/translator.py` (Line ~15)

**Current supported languages:**
```python
supported_languages=['English', 'Tamil', 'Hindi', 'Telugu', 'Malayalam', 'Kannada', 
                     'Bengali', 'Gujarati', 'Marathi', 'Punjabi', 'Urdu']
```

**To add Spanish, German, French:**
```python
supported_languages=['English', 'Tamil', 'Hindi', 'Telugu', 'Malayalam', 'Kannada', 
                     'Bengali', 'Gujarati', 'Marathi', 'Punjabi', 'Urdu', 
                     'Spanish', 'German', 'French']
```

⚠️ **IMPORTANT:** Use the official English name of the language (Spanish, German, French, Portuguese, etc.)

#### File 3: `chatapp/views.py` (Language Map - around Line ~950)

Find this dictionary:
```python
fallback_language_map = {
    'tamil': 'Tamil',
    'english': 'English',
    'hindi': 'Hindi',
    'telugu': 'Telugu',
    'malayalam': 'Malayalam',
    'kannada': 'Kannada',
    'bengali': 'Bengali',
    'gujarati': 'Gujarati',
    'marathi': 'Marathi',
    'punjabi': 'Punjabi',
    'urdu': 'Urdu',
}
```

**Add Spanish, German, French:**
```python
fallback_language_map = {
    'tamil': 'Tamil',
    'english': 'English',
    'hindi': 'Hindi',
    'telugu': 'Telugu',
    'malayalam': 'Malayalam',
    'kannada': 'Kannada',
    'bengali': 'Bengali',
    'gujarati': 'Gujarati',
    'marathi': 'Marathi',
    'punjabi': 'Punjabi',
    'urdu': 'Urdu',
    'spanish': 'Spanish',
    'german': 'German',
    'french': 'French',
}
```

---

## Part 3: Database Configuration (Language Master Table)

The application has a Language model to store language information. You can add languages via Django admin or Django shell.

### Option A: Using Django Admin (Recommended)

1. Go to `http://localhost:8000/admin/`
2. Login with admin credentials
3. Navigate to "Languages" section
4. Click "Add Language"
5. Fill in:
   - **Name:** Spanish (official English name)
   - **Code:** es (ISO 639-1 code)
   - **Is Active:** ✓ (checked)
6. Click "Save"

### Option B: Using Django Shell

```bash
# Activate environment
env\Scripts\activate

# Open Django shell
python manage.py shell

# Add languages
from chatapp.models import Language

Language.objects.create(name='Spanish', code='es', is_active=True)
Language.objects.create(name='German', code='de', is_active=True)
Language.objects.create(name='French', code='fr', is_active=True)

# Exit shell
exit()
```

---

## Complete Example: Adding Spanish

### Step 1: Update Models
Edit `chatapp/models.py` (Message model, around line 115):
```python
audio_file_spanish = models.FileField(upload_to='voice_messages/', blank=True, null=True, help_text='Spanish version of voice message')
```

### Step 2: Create & Apply Migration
```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 3: Update Templates
Edit `chatapp/templates/chat.html` (around line 300):
```html
<option value="spanish">🇪🇸 Spanish - Group accepts Spanish input only</option>
```

### Step 4: Update Translator
Edit `chatapp/utils/translator.py` (line ~15):
```python
supported_languages=['English', 'Tamil', 'Hindi', 'Telugu', 'Malayalam', 'Kannada', 
                     'Bengali', 'Gujarati', 'Marathi', 'Punjabi', 'Urdu', 'Spanish']
```

### Step 5: Update Views
Edit `chatapp/views.py` (around line 950) - add to dictionary:
```python
'spanish': 'Spanish',
```

### Step 6: Add to Database
```bash
python manage.py shell
from chatapp.models import Language
Language.objects.create(name='Spanish', code='es', is_active=True)
exit()
```

### Step 7: Restart Server
```bash
python manage.py runserver 8000
```

### Step 8: Test
1. Navigate to `http://localhost:8000/chat/`
2. You should see "🇪🇸 Spanish" in the language dropdown
3. Create a test group and select Spanish
4. Send messages and verify they work

---

## Language Codes Reference (ISO 639-1)

For reference when adding new languages:

| Language | Code | Country |
|----------|------|---------|
| English | en | 🌐 |
| Spanish | es | 🇪🇸 |
| French | fr | 🇫🇷 |
| German | de | 🇩🇪 |
| Italian | it | 🇮🇹 |
| Portuguese | pt | 🇵🇹 |
| Dutch | nl | 🇳🇱 |
| Russian | ru | 🇷🇺 |
| Japanese | ja | 🇯🇵 |
| Chinese | zh | 🇨🇳 |
| Korean | ko | 🇰🇷 |
| Arabic | ar | 🌍 |
| Hindi | hi | 🇮🇳 |
| Tamil | ta | 🇮🇳 |
| Telugu | te | 🇮🇳 |
| Kannada | kn | 🇮🇳 |
| Malayalam | ml | 🇮🇳 |
| Bengali | bn | 🇮🇳 |

---

## Troubleshooting

### Problem: Migration fails with "No changes detected"
**Solution:** Make sure you actually added the field to `models.py` before running `makemigrations`

### Problem: Dropdown option shows but translation doesn't work
**Solution:** Make sure you added the language to `supported_languages` in `translator.py`

### Problem: Language appears in dropdown but doesn't save when selected
**Solution:** Check that the language value matches between:
- Template (chat.html): `value="spanish"`
- Views.py: `'spanish': 'Spanish'` in the map
- They must be identical and lowercase

### Problem: Error "audio_file_spanish already exists"
**Solution:** Migration has already been applied. Check if field exists in database using:
```bash
python manage.py shell
from chatapp.models import Message
print(Message._meta.get_fields())
exit()
```

---

## Files Checklist for Adding a New Language

Use this checklist when adding a new language (e.g., Portuguese):

- [ ] Add `audio_file_portuguese` field to `Message` model in `models.py`
- [ ] Run `python manage.py makemigrations`
- [ ] Run `python manage.py migrate`
- [ ] Add `<option value="portuguese">` to `chat.html` language dropdown
- [ ] Add `'Portuguese'` to `supported_languages` list in `translator.py`
- [ ] Add `'portuguese': 'Portuguese'` to `fallback_language_map` in `views.py`
- [ ] Create Language record: `Language.objects.create(name='Portuguese', code='pt', is_active=True)`
- [ ] Restart Django server
- [ ] Test in browser - select Portuguese and send a message

---

## Advanced: Custom Language-Specific Validation

If your language has special validation rules (like Tamil's Tanglish detection), you would add them to the message validation in `group.html`:

```javascript
// Example for Portuguese validation
else if (userLanguageMode === 'portuguese') {
    // Add Portuguese-specific validation here
    inputError.style.display = 'none';
}
```

Current validations:
- **English:** No non-ASCII characters allowed, Tanglish detection
- **Tamil:** Any Tamil script allowed
- **Other languages:** All input allowed

---

## Summary

**Minimum files to modify for a new language:**
1. `models.py` - Add audio_file_* (voice only)
2. `chat.html` - Add dropdown option (translation)
3. `translator.py` - Add to supported_languages (translation)
4. `views.py` - Add to language_map (translation)
5. Database Language table - Add language record (optional but recommended)

**Commands to remember:**
```bash
python manage.py makemigrations    # Generate DB migration
python manage.py migrate            # Apply DB migration  
python manage.py runserver 8000     # Restart server to test
```

That's it! Your new language is now available in the chat application.
