from django.shortcuts import render, redirect, get_object_or_404

from chatproject import settings
from .models import Group, Message, AnonymousUser, GroupMember, DeletedMessage, ONLINE_TIMEOUT_MINUTES, UserProfile
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import timedelta
import uuid
import logging
import io
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .utils.translator import translate_text, normalize_to_professional_english, synthesize_speech_with_gtts
from .utils.tamil_detector import is_valid_english_only, get_language_violation_details, contains_tamil_script, ensure_english_only_display, ensure_tamil_only_display, TAMIL_SCRIPT_START, TAMIL_SCRIPT_END, contains_tanglish

logger = logging.getLogger(__name__)
import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

import google.generativeai as genai

genai.configure(api_key=GEMINI_API_KEY)
# Constants
BRITISH_TO_US_ENGLISH = {
    'colour': 'color', 'Colour': 'Color', 'favour': 'favor', 'Favour': 'Favor',
    'honour': 'honor', 'Honour': 'Honor', 'labour': 'labor', 'Labour': 'Labor',
    'harbour': 'harbor', 'Harbour': 'Harbor', 'centre': 'center', 'Centre': 'Center',
    'metre': 'meter', 'Metre': 'Meter', 'theatre': 'theater', 'Theatre': 'Theater',
    'travelling': 'traveling', 'Travelling': 'Traveling', 'realise': 'realize',
    'Realise': 'Realize', 'organise': 'organize', 'Organise': 'Organize',
    'recognise': 'recognize', 'Recognise': 'Recognize', 'apologise': 'apologize',
    'Apologise': 'Apologize', 'analyse': 'analyze', 'Analyse': 'Analyze',
    'licence': 'license', 'Licence': 'License', 'defence': 'defense',
    'Defence': 'Defense', 'offence': 'offense', 'Offence': 'Offense',
    'grey': 'gray', 'Grey': 'Gray', 'cheque': 'check', 'Cheque': 'Check',
    'gaol': 'jail', 'Gaol': 'Jail', 'kerb': 'curb', 'Kerb': 'Curb',
    'programme': 'program', 'Programme': 'Program',
}


def ensure_us_english(text):
    """Standardize text to US English format."""
    if not text:
        return text
    result = text
    for british, american in BRITISH_TO_US_ENGLISH.items():
        result = result.replace(british, american)
    return result


def check_and_cleanup_group(group):
    """Check if group should be deleted and perform deletion if needed."""
    if not group:
        return False, "group_not_found"
    
    try:
        should_delete, reason = group.should_auto_delete()
        if should_delete and group.get_group_online_count() == 0:
            # Recheck to avoid race condition
            group.refresh_from_db()
            should_delete_again, _ = group.should_auto_delete()
            if should_delete_again and group.get_group_online_count() == 0:
                group.delete()
                return True, reason
        return False, reason
    except Exception as e:
        logger.error(f"check_and_cleanup_group error: {str(e)}")
        return False, "error"


def update_user_online_status(session_id, user_name, is_online=True):
    """Update or create user's online status."""
    try:
        anon_user, _ = AnonymousUser.objects.get_or_create(
            session_id=session_id,
            defaults={'user_name': user_name, 'is_online': is_online}
        )
        anon_user.user_name = user_name
        anon_user.is_online = is_online
        anon_user.last_seen = timezone.now()
        anon_user.save(update_fields=['user_name', 'is_online', 'last_seen'])
        return True
    except Exception as e:
        logger.error(f"update_user_online_status error: {str(e)}")
        return False


def auto_offline_inactive_users():
    """Mark users as offline if inactive for ONLINE_TIMEOUT_MINUTES."""
    try:
        cutoff_time = timezone.now() - timedelta(minutes=ONLINE_TIMEOUT_MINUTES)
        inactive = AnonymousUser.objects.filter(is_online=True, last_seen__lt=cutoff_time)
        count = inactive.update(is_online=False)
        return count
    except Exception as e:
        logger.error(f"auto_offline_inactive_users error: {str(e)}")
        return 0


def get_language_mode(request, session_id):
    """Get language mode from session or database, with fallback."""
    mode = request.session.get('language_mode', 'english').strip().lower()
    
    if not mode or mode == 'english':
        try:
            anon_user = AnonymousUser.objects.filter(session_id=session_id).first()
            if anon_user and anon_user.language_mode and anon_user.language_mode != 'english':
                mode = anon_user.language_mode.lower()
        except Exception:
            pass
    
    return mode if mode in ['english', 'tamil'] else 'english'


def process_english_mode_message(content):
    """
    Process message in English mode: STRICT ENGLISH ONLY.

    Returns: (english_display, tamil_backend, validation_msg, should_warn)
    """
    has_tamil = contains_tamil_script(content)
    has_tanglish = contains_tanglish(content)

    if has_tamil:
        # Tamil script detected - auto-convert to English
        logger.info(f"Tamil script detected in English mode - auto-converting: {content[:50]}")
        try:
            eng_success, english_converted, _ = translate_text(content, 'English')
            english_version = english_converted if eng_success else content
        except Exception as e:
            logger.warning(f"Failed to convert Tamil to English: {str(e)}")
            english_version = content

        validation_msg = "⚠️ Tamil script detected. Converting to English. Only English allowed."
        should_warn = True

    elif has_tanglish:
        # Tanglish detected - try converting to proper English
        logger.info(f"Tanglish detected in English mode - auto-converting: {content[:50]}")
        try:
            eng_success, english_converted, _ = translate_text(content, 'English')
            english_version = english_converted if eng_success else content
        except Exception as e:
            logger.warning(f"Failed to convert Tanglish to English: {str(e)}")
            english_version = content

        validation_msg = "⚠️ Tanglish detected. Converting to proper English. Use English only."
        should_warn = True

    else:
        # Pure English - normalize and standardize
        norm_success, normalized_content, _ = normalize_to_professional_english(content, 'English')
        english_version = ensure_us_english(normalized_content if norm_success else content)
        english_version = ensure_english_only_display(english_version)
        validation_msg = None
        should_warn = False

    # Generate Tamil backend version (for storage only)
    try:
        tamil_success, tamil_version, _ = translate_text(english_version, 'Tamil')
        tamil_version = tamil_version if tamil_success else english_version
    except Exception as e:
        logger.warning(f"Failed to translate to Tamil: {str(e)}")
        tamil_version = english_version

    return english_version, tamil_version, validation_msg, should_warn


def process_tamil_mode_message(content):
    """
    Process message in Tamil mode: STRICT TAMIL DISPLAY.

    Returns: (english_backend, tamil_display, validation_msg, should_warn)
    """
    has_tamil = contains_tamil_script(content)
    has_tanglish = contains_tanglish(content)
    # Check for English: ASCII letters a-z or A-Z
    has_english = any(('a' <= c <= 'z' or 'A' <= c <= 'Z') for c in content)

    if has_tamil and not has_english:
        # Pure Tamil - keep as-is
        tamil_version = content
        try:
            eng_success, english_version, _ = translate_text(content, 'English')
            english_version = english_version if eng_success else content
        except Exception as e:
            logger.warning(f"Failed to translate Tamil to English: {str(e)}")
            english_version = content

        validation_msg = None
        should_warn = False

    elif has_tanglish and not has_tamil:
        # Tanglish: convert to Tamil
        logger.info(f"Tanglish detected in Tamil mode - auto-converting: {content[:50]}")
        try:
            tamil_success, tamil_translated, _ = translate_text(content, 'Tamil')
            tamil_version = tamil_translated if tamil_success else content
        except Exception as e:
            logger.warning(f"Failed to convert Tanglish to Tamil: {str(e)}")
            tamil_version = content

        try:
            eng_success, english_version, _ = translate_text(content, 'English')
            english_version = english_version if eng_success else content
        except Exception as e:
            logger.warning(f"Failed to translate to English: {str(e)}")
            english_version = content

        validation_msg = "⚠️ Tanglish detected. Using Tamil. Please type in Tamil script."
        should_warn = True

    elif has_english:
        # English detected - convert to Tamil
        logger.info(f"English detected in Tamil mode - auto-converting: {content[:50]}")
        try:
            tamil_success, tamil_translated, _ = translate_text(content, 'Tamil')
            tamil_version = tamil_translated if tamil_success else content
        except Exception as e:
            logger.warning(f"Failed to translate to Tamil: {str(e)}")
            tamil_version = content

        try:
            eng_success, english_version, _ = translate_text(content, 'English')
            english_version = english_version if eng_success else content
        except Exception as e:
            logger.warning(f"Failed to translate to English: {str(e)}")
            english_version = content

        validation_msg = "⚠️ English detected. Converting to Tamil. Only Tamil characters allowed in display."
        should_warn = True

    else:
        # Fallback
        logger.warning(f"No Tamil or English detected in Tamil mode: {content[:50]}")
        try:
            tamil_success, tamil_translated, _ = translate_text(content, 'Tamil')
            tamil_version = tamil_translated if tamil_success else content
        except Exception as e:
            logger.warning(f"Failed to translate to Tamil: {str(e)}")
            tamil_version = content

        try:
            eng_success, english_version, _ = translate_text(content, 'English')
            english_version = english_version if eng_success else content
        except Exception as e:
            logger.warning(f"Failed to translate to English: {str(e)}")
            english_version = content

        validation_msg = None
        should_warn = False

    return english_version, tamil_version, validation_msg, should_warn





def save_message(group, content, english_version, tamil_version, display_content, 
                user_name, session_id, language_mode, message_type='text', 
                audio_file=None, audio_mime_type=None, duration=0):
    """Save message with both language versions."""
    message = Message.objects.create(
        group=group,
        content=content,
        normalized_content=english_version,
        english_content=english_version,
        tamil_content=tamil_version,
        message_type=message_type,
        user_name=user_name,
        session_id=session_id,
        audio_file=audio_file,
        audio_mime_type=audio_mime_type or 'audio/webm',
        duration=duration
    )
    
    message.translated_content = display_content
    message.translated_language = 'Tamil' if language_mode == 'tamil' else 'English'
    message.save(update_fields=['translated_content', 'translated_language'])
    
    return message


def register_view(request):
    """Handle user registration with mandatory admin approval."""
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            email = request.POST.get('email')
            mobile = request.POST.get('mobile')
            user = form.save()
            user.email = email
            user.save(update_fields=['email'])
            UserProfile.objects.create(user=user, is_approved=False, mobile_number=mobile)
            return render(request, "login.html", {
                "info": "Registration successful! Please wait for Admin approval before logging in."
            })
    else:
        form = UserCreationForm()
    return render(request, "register.html", {"form": form})


def login_view(request):
    """Handle user login and check for approval status."""
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            
            if user is not None:
                try:
                    profile = user.profile
                    if profile.is_approved or user.is_superuser:
                        login(request, user)
                        return redirect("dashboard") if user.is_superuser else redirect("home")
                    else:
                        return render(request, "login.html", {
                            "form": form,
                            "error": "Your account is pending approval by the Admin."
                        })
                except UserProfile.DoesNotExist:
                    if user.is_superuser:
                        UserProfile.objects.create(user=user, is_approved=True)
                        login(request, user)
                        return redirect("dashboard")
                    return render(request, "login.html", {"form": form, "error": "Profile missing. Please contact Admin."})
    else:
        form = AuthenticationForm()
    return render(request, "login.html", {"form": form})


def logout_view(request):
    """Handle user logout."""
    logout(request)
    return redirect("login")


def dashboard(request):
    """Admin dashboard to manage users and view stats."""
    if not request.user.is_superuser:
        return redirect("home")
    
    pending_users = UserProfile.objects.filter(is_approved=False)
    approved_users = UserProfile.objects.filter(is_approved=True).exclude(user__is_superuser=True)
    all_groups = Group.objects.all()
    return render(request, "dashboard.html", {
        "pending_users": pending_users,
        "approved_users": approved_users,
        "groups": all_groups
    })

def approve_user(request, profile_id):
    """Directly approve a user from the dashboard."""
    if not request.user.is_superuser:
        return redirect("home")
    profile = get_object_or_404(UserProfile, id=profile_id)
    profile.is_approved = True
    profile.save()
    return redirect("dashboard")

def reject_user(request, profile_id):
    """Reject and delete a pending user registration."""
    if not request.user.is_superuser:
        return redirect("home")
    profile = get_object_or_404(UserProfile, id=profile_id)
    user = profile.user
    user.delete() # Cascade deletes profile
    return redirect("dashboard")

def delete_user(request, profile_id):
    """Permanently delete an approved user."""
    if not request.user.is_superuser:
        return redirect("home")
    profile = get_object_or_404(UserProfile, id=profile_id)
    user = profile.user
    user.delete() # Cascade deletes profile
    return redirect("dashboard")


def home(request):
    """Home page - entry point of the app."""
    return render(request, "home.html")


def chat(request):
    """Chat page - user enters their name and group code."""
    if request.method == "POST":
        user_name = request.POST.get("user_name", "").strip()
        code = request.POST.get("code", "").strip()
        language_mode = request.POST.get("language_mode", "english").strip().lower()
        
        if not user_name or not code:
            return render(request, "chat.html", {"error": "Please enter both name and group code"})
        
        # Allow any username for both English and Tamil groups
        language_mode = language_mode if language_mode in ['english', 'tamil'] else 'english'
        
        # Ensure session key exists
        if not request.session.session_key:
            request.session.save()
        
        request.session['user_name'] = user_name
        request.session['user_id'] = request.session.get('user_id') or str(uuid.uuid4())
        request.session['language'] = language_mode
        request.session['language_mode'] = language_mode
        request.session.save()
        
        # Modified to only allow joining existing groups
        group = Group.objects.filter(code=code).first()
        if not group:
            return render(request, "chat.html", {"error": "Group code not found. Please create the group first."})
            
        group.last_activity = timezone.now()
        group.save(update_fields=['last_activity'])
        
        try:
            anon_user, _ = AnonymousUser.objects.get_or_create(
                session_id=request.session.session_key,
                defaults={
                    'user_name': user_name,
                    'is_online': True,
                    'last_seen': timezone.now(),
                    'language_mode': language_mode
                }
            )
            if not anon_user.user_name == user_name or anon_user.language_mode != language_mode:
                anon_user.user_name = user_name
                anon_user.is_online = True
                anon_user.last_seen = timezone.now()
                anon_user.language_mode = language_mode
                anon_user.save()
            
            # Add to group members
            GroupMember.objects.get_or_create(
                group=group,
                session_id=request.session.session_key,
                defaults={'last_seen': timezone.now()}
            )
            
            logger.info(f"User '{user_name}' joined group '{code}' (mode: {language_mode})")
        except Exception as e:
            logger.error(f"Error creating user record: {str(e)}")
        
        request.session['group_code'] = code
        return redirect("group", code=group.code)

    return render(request, "chat.html")

def group_manage(request):
    """New view to handle group creation and listing."""
    # Protect view: Only Admin or Approved users can manage/create groups
    if not request.user.is_authenticated:
        return redirect("login")
    
    is_allowed = request.user.is_superuser
    if not is_allowed:
        # Ensure user has a profile and check approval status
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        is_allowed = profile.is_approved
        
    if not is_allowed:
        return redirect("home")

    error = None
    if request.method == "POST":
        code = request.POST.get("code", "").strip()
        name = request.POST.get("name", "").strip() or code
        
        if not code:
            error = "Group code is required"
        elif Group.objects.filter(code=code).exists():
            error = "Group code already exists"
        else:
            Group.objects.create(code=code, name=name)
            return redirect("group_manage")

    # Prepare group data with stats for the listing table
    groups = Group.objects.all().order_by('-last_activity')
    groups_data = []

    for g in groups:
        groups_data.append({
            'code': g.code,
            'name': g.name,
            'created_at': g.created_at,
            'message_count': g.messages.count(),
            'online_count': g.get_group_online_count(),
            'last_activity': g.last_activity
        })
        
    return render(request, "group_create.html", {
        "groups": groups_data, 
        "error": error
    })

def delete_group_entirely(request, code):
    """Delete a group and all its data."""
    try:
        Group.objects.filter(code=code).delete()
    except Exception:
        pass
    return redirect("group_manage")

def group(request, code):
    """Group chat view with language mode filtering."""
    try:
        group = Group.objects.get(code=code)
    except Group.DoesNotExist:
        return redirect('chat')
    
    should_delete, reason = check_and_cleanup_group(group)
    if should_delete:
        return render(request, "chat.html", {
            "info": f"Group was deleted due to inactivity ({reason}). Please create a new one!"
        })
    
    user_name = request.session.get('user_name', 'Anonymous')
    user_language = request.session.get('language', 'English')
    user_language_mode = request.session.get('language_mode', 'english').lower()
    session_id = request.session.session_key
    
    # Ensure user is a member of the group
    GroupMember.objects.get_or_create(
        group=group,
        session_id=session_id,
        defaults={'last_seen': timezone.now()}
    )
    
    # Get messages from database
    raw_messages = Message.objects.filter(group=group).order_by('timestamp')
    
    # Filter and prepare messages based on language mode
    messages_list = []
    for msg in raw_messages:
        # Get language versions
        tamil_version = msg.tamil_content or msg.translated_content
        english_version = ensure_us_english(msg.english_content or msg.normalized_content or msg.content) if msg.content else ""
        
        # Apply language purity filter based on user mode
        if user_language_mode == 'tamil':
            # TAMIL MODE: Show ONLY Tamil (no English characters)
            display_content = ensure_tamil_only_display(tamil_version) if tamil_version else tamil_version
            display_content = display_content or tamil_version or english_version
        else:
            # ENGLISH MODE: Show ONLY English (no Tamil characters)
            display_content = ensure_english_only_display(english_version) if english_version else english_version
        
        # Prepare message object for template
        msg_data = {
            'id': msg.id,
            'user_name': msg.user_name,
            'content': display_content,  # Filtered display content
            'original_content': msg.content,
            'tamil_content': tamil_version,
            'english_content': english_version,
            'message_type': msg.message_type,
            'timestamp': msg.timestamp,
            'session_id': msg.session_id,
            'is_deleted': msg.is_deleted,
            'audio_file': msg.audio_file,
            'audio_file_tamil': msg.audio_file_tamil,
            'audio_file_english': msg.audio_file_english,
            'audio_mime_type': msg.audio_mime_type or 'audio/webm',
            'duration': msg.duration
        }
        messages_list.append(msg_data)
    
    # Get online users count
    online_users = AnonymousUser.objects.filter(
        last_seen__gte=timezone.now() - timedelta(minutes=ONLINE_TIMEOUT_MINUTES)
    ).distinct()
    
    last_message_timestamp = messages_list[-1]['timestamp'].isoformat() if messages_list else timezone.now().isoformat()
    
    context = {
        "group": group,
        "messages": messages_list,
        "user_name": user_name,
        "online_count": online_users.count(),
        "last_message_timestamp": last_message_timestamp,
        "language": user_language,
        "language_name": user_language,
        "language_mode": user_language_mode,
        "user_session_id": session_id,
    }
    
    return render(request, "group.html", context)

# ================================
# 🔹 IMPORTS
# ================================
import os
import tempfile

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

import speech_recognition as sr
from pydub import AudioSegment, effects
from gtts import gTTS

from dotenv import load_dotenv
import google.generativeai as genai


# ================================
# 🔹 LOAD ENV + GEMINI
# ================================
# ================================
# 🔹 SPEECH TO TEXT
# ================================
def speech_to_text(audio_file_path, lang="en-IN"):
    print(f"🎤 STT: Processing file {audio_file_path} with language {lang}")
    recognizer = sr.Recognizer()
    wav_file_path = audio_file_path + ".wav"

    try:
        print("🔄 Converting audio to WAV format...")
        audio = AudioSegment.from_file(audio_file_path)
        print(f"📊 Audio loaded: {len(audio)}ms duration, {audio.frame_rate}Hz")

        # Normalize audio for better recognition
        audio = audio.set_frame_rate(16000).set_channels(1)
        audio = effects.normalize(audio)
        audio.export(wav_file_path, format="wav")
        print(f"✅ WAV conversion complete ({audio.frame_rate}Hz, {audio.channels} channel)")

        print("🎧 Starting speech recognition...")
        with sr.AudioFile(wav_file_path) as source:
            print("🔊 Adjusting for ambient noise...")
            recognizer.energy_threshold = 100
            recognizer.dynamic_energy_threshold = True
            recognizer.pause_threshold = 0.5
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            print("🎙️ Recording audio data...")
            audio_data = recognizer.record(source)
            print(f"📝 Audio data recorded, calling Google API with lang={lang}...")

            def try_recognize(locale):
                try:
                    result = recognizer.recognize_google(audio_data, language=locale, show_all=True)
                    if isinstance(result, dict) and result.get('alternative'):
                        text = result['alternative'][0].get('transcript', '').strip()
                        if text:
                            print(f"✅ STT Success ({locale}): '{text}'")
                            return text
                    return None
                except sr.UnknownValueError:
                    print(f"⚠️ No speech recognized with {locale}")
                    return None
                except sr.RequestError as e:
                    print(f"❌ STT Request failed for {locale}: {e}")
                    return None

            if lang == "en":
                for candidate in ["en-US", "en-GB", "en-IN", "en"]:
                    text = try_recognize(candidate)
                    if text:
                        return text
                return ""

            text = try_recognize(lang)
            if text:
                return text.strip()
            return ""

    except sr.UnknownValueError:
        print("❌ STT Error: Speech not recognized (UnknownValueError)")
        return ""
    except sr.RequestError as e:
        print(f"❌ STT Error: API request failed: {e}")
        return ""
    except Exception as e:
        print(f"❌ STT Error: Unexpected error: {e}")
        return ""

    finally:
        if os.path.exists(wav_file_path):
            os.remove(wav_file_path)
            print("🧹 Cleaned up WAV file")

# ================================
# 🔹 GEMINI TRANSLATION
# ================================
def translate_with_gemini(tamil_text):
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")

        prompt = f"""
        Translate the following Tamil sentence into natural, spoken English.

        Correct the sentence if needed and give the most natural meaning.

        Tamil: {tamil_text}

        Return only the final English sentence.
        """

        response = model.generate_content(prompt)

        return response.text.strip().replace("\n", "")

    except Exception as e:
        return f"Translation error: {e}"


# ================================
# 🔹 TEXT → 2 AUDIO (Tamil + English)
# ================================
def text_to_voice_by_mode(tamil_text, english_text, language_mode):
    try:
        from django.conf import settings
        import uuid

        filename = f"{uuid.uuid4()}.mp3"
        audio_path = os.path.join(settings.MEDIA_ROOT, filename)

        # 🎯 Decide based on mode
        if language_mode == "tamil":
            text = tamil_text
            lang = "ta"
        else:
            text = english_text
            lang = "en"

        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(audio_path)

        audio_url = f"{settings.MEDIA_URL}{filename}"

        return audio_url, audio_path

    except Exception as e:
        print("Voice error:", e)
        return None, None


def generate_bilingual_audio(tamil_text, english_text):
    """Generate BOTH Tamil and English audio files for voice messages."""
    print(f"🎵 Generating bilingual audio for Tamil: '{tamil_text}' (len: {len(tamil_text) if tamil_text else 0}), English: '{english_text}' (len: {len(english_text) if english_text else 0})")

    try:
        from django.conf import settings
        import uuid

        audio_files = {}

        # Generate English audio
        try:
            print("🔊 Generating English audio...")
            if not english_text or not english_text.strip():
                print("⚠️ No English text provided, skipping English audio generation")
                audio_files['english'] = None
            else:
                english_filename = f"{uuid.uuid4()}.mp3"
                english_audio_path = os.path.join(settings.MEDIA_ROOT, english_filename)

                tts_en = gTTS(text=english_text, lang="en", slow=False)
                tts_en.save(english_audio_path)
                print(f"✅ English audio saved: {english_audio_path}")

                audio_files['english'] = {
                    'url': f"{settings.MEDIA_URL}{english_filename}",
                    'path': english_audio_path,
                    'filename': english_filename
                }
        except Exception as e:
            print(f"❌ Failed to generate English audio: {str(e)}")
            audio_files['english'] = None

        # Generate Tamil audio
        try:
            print("🔊 Generating Tamil audio...")
            if not tamil_text or not tamil_text.strip():
                print("⚠️ No Tamil text provided, skipping Tamil audio generation")
                audio_files['tamil'] = None
            else:
                tamil_filename = f"{uuid.uuid4()}.mp3"
                tamil_audio_path = os.path.join(settings.MEDIA_ROOT, tamil_filename)

                tts_ta = gTTS(text=tamil_text, lang="ta", slow=False)
                tts_ta.save(tamil_audio_path)
                print(f"✅ Tamil audio saved: {tamil_audio_path}")

                audio_files['tamil'] = {
                    'url': f"{settings.MEDIA_URL}{tamil_filename}",
                    'path': tamil_audio_path,
                    'filename': tamil_filename
                }
        except Exception as e:
            print(f"❌ Failed to generate Tamil audio: {str(e)}")
            audio_files['tamil'] = None

        print(f"📊 Audio generation complete: Tamil={audio_files['tamil'] is not None}, English={audio_files['english'] is not None}")
        return audio_files

    except Exception as e:
        print(f"❌ generate_bilingual_audio error: {str(e)}")
        return {'english': None, 'tamil': None}

# ================================
# 🔹 MAIN API
# ================================

@require_http_methods(["POST"])
def upload_voice_message(request, code):

    if 'audio' not in request.FILES:
        return JsonResponse({'error': 'Audio not received'}, status=400)

    audio_file = request.FILES['audio']
    transcript_text = request.POST.get('text', '').strip()

    if audio_file.size == 0:
        return JsonResponse({'error': 'Empty audio'}, status=400)

    try:
        # =========================================
        # 💾 Save temp audio
        # =========================================
        file_name = f"{uuid.uuid4()}.webm"
        temp_path = os.path.join(settings.MEDIA_ROOT, file_name)

        with open(temp_path, 'wb+') as destination:
            for chunk in audio_file.chunks():
                destination.write(chunk)

        print("✅ Audio saved:", temp_path)

        # =========================================
        # 🎯 GET MODE
        # =========================================
        session_id = request.session.session_key
        if not session_id:
            request.session.create()
            session_id = request.session.session_key

        language_mode = get_language_mode(request, session_id)

        # =========================================
        # 🧠 SPEECH → TEXT (BASED ON MODE)
        # =========================================
        stt_failed = False

        if language_mode == "tamil":
            print(f"🎤 Tamil mode: Processing audio with ta-IN")
            tamil_text = speech_to_text(temp_path, lang="ta-IN")
            print(f"📝 Tamil STT result: '{tamil_text}' (length: {len(tamil_text) if tamil_text else 0})")

            if not tamil_text and transcript_text:
                print("⚠️ Tamil STT empty, using client-provided transcript fallback")
                tamil_text = transcript_text

            if not tamil_text:
                print("❌ Tamil STT failed - saving voice-only message")
                tamil_text = ""
                english_text = ""
                stt_failed = True
            else:
                print("🔄 Translating Tamil to English...")
                english_text = translate_with_gemini(tamil_text)
                print(f"📝 English translation: '{english_text}'")

        else:
            print(f"🎤 English mode: Processing audio with en (general English)")
            english_text = speech_to_text(temp_path, lang="en")
            print(f"📝 English STT result: '{english_text}' (length: {len(english_text) if english_text else 0})")

            if not english_text:
                print("❌ English STT failed - trying with en-US...")
                english_text = speech_to_text(temp_path, lang="en-US")
                print(f"📝 English STT en-US result: '{english_text}' (length: {len(english_text) if english_text else 0})")

                if not english_text and transcript_text:
                    print("⚠️ English STT empty, using client-provided transcript fallback")
                    english_text = transcript_text

                if not english_text:
                    print("❌ English STT completely failed - saving voice-only message")
                    english_text = ""
                    tamil_text = ""
                    stt_failed = True

            if english_text:
                print("🔄 Translating English to Tamil...")
                try:
                    success, tamil_text, translation_msg = translate_text(english_text, 'Tamil')
                    print(f"📝 Tamil translation success: {success}, result: '{tamil_text}', msg: {translation_msg}")
                    if not success:
                        print("⚠️ Translation failed, using English text as fallback")
                        tamil_text = english_text
                except Exception as e:
                    print(f"⚠️ Translation exception: {e}, using English text as fallback")
                    tamil_text = english_text

        print("📝 Tamil:", tamil_text)
        print("📝 English:", english_text)

        # =========================================
        # 🔊 GENERATE BILINGUAL AUDIO
        # =========================================
        audio_files = generate_bilingual_audio(tamil_text, english_text)

        # =========================================
        # 💾 SAVE MESSAGE
        # =========================================
        message_id = None

        try:
            group = Group.objects.get(code=code)
            user_name = request.session.get('user_name', 'Anonymous')

            # Always use English as primary content
            content = english_text
            word_count = len(content.split())
            estimated_duration = max(1, word_count / 2.5)

            message_audio_mime_type = audio_file.content_type or 'audio/webm'
            message = Message.objects.create(
                group=group,
                content=content,
                normalized_content=english_text,
                english_content=english_text,
                tamil_content=tamil_text,
                message_type='voice',
                duration=estimated_duration,
                user_name=user_name,
                session_id=session_id,
                audio_mime_type=message_audio_mime_type
            )

            # ✅ SAVE BILINGUAL AUDIO FILES
            from django.core.files import File
            print(f"💾 Saving audio files: English={audio_files.get('english') is not None}, Tamil={audio_files.get('tamil') is not None}")
            
            # Save English audio
            if audio_files.get('english') and audio_files['english']['path'] and os.path.exists(audio_files['english']['path']):
                try:
                    print(f"💾 Saving English audio file: {audio_files['english']['path']}")
                    with open(audio_files['english']['path'], 'rb') as f:
                        message.audio_file_english.save(audio_files['english']['filename'], File(f))
                    print("✅ English audio saved to database")
                except Exception as e:
                    print(f"❌ Failed to save English audio: {str(e)}")
            
            # Save Tamil audio
            if audio_files.get('tamil') and audio_files['tamil']['path'] and os.path.exists(audio_files['tamil']['path']):
                try:
                    print(f"💾 Saving Tamil audio file: {audio_files['tamil']['path']}")
                    with open(audio_files['tamil']['path'], 'rb') as f:
                        message.audio_file_tamil.save(audio_files['tamil']['filename'], File(f))
                    print("✅ Tamil audio saved to database")
                except Exception as e:
                    print(f"❌ Failed to save Tamil audio: {str(e)}")
            
            # Set default audio_file to English version if available
            primary_audio_saved_as_mp3 = False
            if audio_files.get('english') and audio_files['english']['path']:
                try:
                    print(f"💾 Setting default audio file to English: {audio_files['english']['path']}")
                    with open(audio_files['english']['path'], 'rb') as f:
                        message.audio_file.save(audio_files['english']['filename'], File(f))
                    print("✅ Default audio file set")
                    primary_audio_saved_as_mp3 = True
                except Exception as e:
                    print(f"❌ Failed to save default audio file: {str(e)}")
            elif os.path.exists(temp_path):
                try:
                    print(f"💾 Saving original uploaded voice file as fallback: {temp_path}")
                    with open(temp_path, 'rb') as f:
                        message.audio_file.save(os.path.basename(temp_path), File(f))
                    print("✅ Saved original voice file to database")
                except Exception as e:
                    print(f"❌ Failed to save original voice file: {str(e)}")
            else:
                print("⚠️ No audio file available to save for this message")

            message.translated_content = english_text
            message.translated_language = 'English'
            if primary_audio_saved_as_mp3:
                message.audio_mime_type = 'audio/mpeg'
            else:
                message.audio_mime_type = audio_file.content_type or 'audio/webm'
            message.save(update_fields=['audio_file_english', 'audio_file_tamil', 'audio_file', 'translated_content', 'translated_language', 'audio_mime_type'])

            # Update user
            anon_user, _ = AnonymousUser.objects.get_or_create(
                session_id=session_id,
                defaults={'user_name': user_name}
            )
            anon_user.last_seen = timezone.now()
            anon_user.is_online = True
            anon_user.save(update_fields=['last_seen', 'is_online'])

            group.last_activity = timezone.now()
            group.save(update_fields=['last_activity'])

            message_id = message.id

        except Exception as save_error:
            logger.error(f"Save error: {save_error}")

        # =========================================
        # 🧹 CLEANUP
        # =========================================
        if os.path.exists(temp_path):
            os.remove(temp_path)

        # Clean up both audio files
        if audio_files.get('english') and audio_files['english']['path'] and os.path.exists(audio_files['english']['path']):
            try:
                os.remove(audio_files['english']['path'])
            except Exception as e:
                logger.warning(f"Failed to cleanup English audio: {str(e)}")

        if audio_files.get('tamil') and audio_files['tamil']['path'] and os.path.exists(audio_files['tamil']['path']):
            try:
                os.remove(audio_files['tamil']['path'])
            except Exception as e:
                logger.warning(f"Failed to cleanup Tamil audio: {str(e)}")

        # =========================================
        # ✅ RESPONSE
        # =========================================
        response = {
            'success': True,
            'tamil_text': tamil_text,
            'english_text': english_text,
            'audio': message.audio_file.url if message.audio_file else (audio_files['english']['url'] if audio_files.get('english') else None),
            'mode': language_mode
        }

        if stt_failed:
            response['note'] = 'speech_recognition_unavailable'

        if message_id:
            response['message_id'] = message_id

        return JsonResponse(response)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)




@require_http_methods(["POST"])
def delete_message(request, code):
    """Delete a message for me or for everyone."""
    try:
        group = Group.objects.get(code=code)
        should_delete, delete_reason = check_and_cleanup_group(group)
        if should_delete:
            return JsonResponse({'error': 'Group deleted', 'status': 'group_deleted', 'reason': delete_reason}, status=410)
        
        message_id = request.POST.get('message_id')
        delete_type = request.POST.get('delete_type')
        session_id = request.session.session_key
        
        if not message_id or not delete_type:
            return JsonResponse({'error': 'Missing parameters'}, status=400)
        
        message = Message.objects.get(id=message_id, group=group)
        
        if delete_type == 'for_all' and message.session_id != session_id:
            return JsonResponse({'error': 'Only sender can delete for everyone'}, status=403)
        
        if delete_type == 'for_all':
            message.is_deleted = 'deleted_for_all'
            message.save(update_fields=['is_deleted'])
        else:
            # For me: create DeletedMessage entry
            DeletedMessage.objects.get_or_create(message=message, session_id=session_id)
        
        return JsonResponse({'success': True, 'status': 'deleted_for_all' if delete_type == 'for_all' else 'deleted_for_me'})
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Group not found', 'status': 'group_not_found'}, status=404)
    except Message.DoesNotExist:
        return JsonResponse({'error': 'Message not found'}, status=404)
    except Exception as e:
        logger.error(f"delete_message error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["POST"])
def update_user_status(request, code):
    """Update user online/offline status."""
    try:
        group = Group.objects.get(code=code)
        should_delete, delete_reason = check_and_cleanup_group(group)
        if should_delete:
            return JsonResponse({'error': 'Group deleted', 'status': 'group_deleted', 'reason': delete_reason}, status=410)
        
        user_name = request.session.get('user_name', 'Anonymous')
        session_id = request.session.session_key
        is_online = request.POST.get('is_online', 'false').lower() == 'true'
        
        anon_user, _ = AnonymousUser.objects.get_or_create(session_id=session_id, defaults={'user_name': user_name})
        anon_user.is_online = is_online
        anon_user.last_seen = timezone.now()
        anon_user.save(update_fields=['is_online', 'last_seen'])
        
        # Update group member last_seen
        GroupMember.objects.filter(group=group, session_id=session_id).update(last_seen=timezone.now())
        
        group.last_activity = timezone.now()
        group.save(update_fields=['last_activity'])
        auto_offline_inactive_users()
        
        online_count = group.get_group_online_count()
        
        return JsonResponse({'success': True, 'is_online': anon_user.is_online, 'online_count': online_count})
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Group not found', 'status': 'group_not_found'}, status=404)
    except Exception as e:
        logger.error(f"update_user_status error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["GET"])
def get_online_users(request, code):
    """Get list of online users in the group."""
    try:
        group = Group.objects.get(code=code)
        should_delete, delete_reason = check_and_cleanup_group(group)
        if should_delete:
            return JsonResponse({'error': 'Group deleted', 'status': 'group_deleted', 'reason': delete_reason}, status=410)
        
        group_user_session_ids = group.members.values_list('session_id', flat=True)
        online_users = AnonymousUser.objects.filter(
            session_id__in=group_user_session_ids,
            is_online=True,
            last_seen__gte=timezone.now() - timedelta(minutes=ONLINE_TIMEOUT_MINUTES)
        ).values_list('user_name', 'id', 'session_id').distinct()
        
        users_list = [{'id': user[1], 'session_id': user[2], 'display_name': user[0] or 'Anonymous'} for user in online_users]
        
        return JsonResponse({'success': True, 'users': users_list, 'count': len(users_list)})
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Group not found', 'status': 'group_not_found'}, status=404)
    except Exception as e:
        logger.error(f"get_online_users error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["GET"])
def get_new_messages(request, code):
    """Get new messages since last timestamp - returns both Tamil and English versions."""
    try:
        group = Group.objects.get(code=code)
        session_id = request.session.session_key
        since_timestamp = request.GET.get('since', '')
        user_language_mode = get_language_mode(request, session_id)
        
        should_delete, delete_reason = check_and_cleanup_group(group)
        if should_delete:
            return JsonResponse({'error': 'Group deleted', 'status': 'group_deleted', 'reason': delete_reason}, status=410)
        
        messages_query = Message.objects.filter(group=group).order_by('timestamp')
        
        if since_timestamp:
            try:
                from django.utils.dateparse import parse_datetime
                since_dt = parse_datetime(since_timestamp)
                if since_dt:
                    messages_query = messages_query.filter(timestamp__gt=since_dt)
            except Exception:
                pass
        
        messages_list = []
        for msg_obj in messages_query:
            # Check if deleted for this user
            if DeletedMessage.objects.filter(message=msg_obj, session_id=session_id).exists():
                continue
            
            try:
                tamil_version = msg_obj.tamil_content or msg_obj.translated_content
                english_version = ensure_us_english(msg_obj.english_content or msg_obj.normalized_content or msg_obj.content)
                
                # Enforce language purity based on mode
                if user_language_mode == 'english':
                    # English mode: ONLY English characters in display
                    display_content = ensure_english_only_display(english_version)
                else:  # tamil mode
                    # Tamil mode: ONLY Tamil characters in display
                    # Ensure no English letters in the Tamil display
                    display_content = ensure_tamil_only_display(tamil_version) if tamil_version else tamil_version
                    display_content = display_content or tamil_version or english_version
                
                message_obj = {
                    'id': msg_obj.id,
                    'user_name': msg_obj.user_name,
                    'content': display_content,
                    'tamil': tamil_version,
                    'english': english_version,
                    'original_content': msg_obj.content,
                    'message_type': msg_obj.message_type,
                    'timestamp': msg_obj.timestamp.isoformat(),
                    'is_sender': msg_obj.session_id == session_id,
                    'is_deleted': False,  # Since we filtered out deleted ones
                    'language_mode': user_language_mode,
                }
                
                if msg_obj.message_type == 'voice':
                    message_obj['audio_url'] = msg_obj.audio_file.url if msg_obj.audio_file else ''
                    message_obj['audio_mime_type'] = msg_obj.audio_mime_type or 'audio/webm'
                    message_obj['duration'] = msg_obj.duration
                
                messages_list.append(message_obj)
            except Exception as msg_error:
                logger.error(f"Error processing message {msg_obj.id}: {msg_error}")
                continue
        
        online_count = group.get_group_online_count()
        update_user_online_status(session_id, request.session.get('user_name', 'Anonymous'), is_online=True)
        
        return JsonResponse({
            'success': True,
            'messages': messages_list,
            'online_count': online_count,
            'timestamp': timezone.now().isoformat(),
            'language_mode': user_language_mode
        })
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Group not found', 'success': False, 'status': 'group_not_found'}, status=404)
    except Exception as e:
        logger.error(f"get_new_messages error: {str(e)}")
        return JsonResponse({'error': str(e), 'success': False}, status=500)


@require_http_methods(["POST"])
def send_message_ajax(request, code):
    """Send text message via AJAX with dual-mode language support."""
    try:
        group = Group.objects.get(code=code)
        should_delete, delete_reason = check_and_cleanup_group(group)
        if should_delete:
            return JsonResponse({'error': 'Group deleted', 'status': 'group_deleted', 'reason': delete_reason}, status=410)
        
        user_name = request.session.get('user_name', 'Anonymous')
        session_id = request.session.session_key
        content = request.POST.get('message', '').strip()
        user_language_mode = get_language_mode(request, session_id)
        
        if not content:
            return JsonResponse({'error': 'Message cannot be empty'}, status=400)

        # Convert Tanglish instead of rejecting
        if contains_tanglish(content):
            logger.info(f"Tanglish detected - converting: {content[:50]}")
            try:
                # Try to translate Tanglish to proper language
                if user_language_mode == 'english':
                    eng_success, converted, _ = translate_text(content, 'English')
                    if eng_success:
                        content = converted
                        validation_msg = "⚠️ Tanglish detected. Converted to English."
                        should_warn = True
                else:
                    tamil_success, converted, _ = translate_text(content, 'Tamil')
                    if tamil_success:
                        content = converted
                        validation_msg = "⚠️ Tanglish detected. Converted to Tamil."
                        should_warn = True
            except Exception as e:
                logger.warning(f"Failed to convert Tanglish: {str(e)}")
                # Continue with original content
        
        if len(content) > 5000:
            return JsonResponse({'error': 'Message too long (max 5000 characters)'}, status=400)
        
        # Process message based on language mode with auto-conversion and fallbacks
        try:
            if user_language_mode == 'english':
                # ENGLISH MODE: Accept English, auto-convert Tamil to English
                english_version, tamil_version, validation_msg, should_warn = process_english_mode_message(content)
                display_content = english_version
                
                if should_warn and validation_msg:
                    logger.warning(f"Tamil converted to English in English mode: {content[:50]}")
            else:  # tamil mode
                # TAMIL MODE: Accept Tamil + English, auto-convert English to Tamil
                english_version, tamil_version, validation_msg, should_warn = process_tamil_mode_message(content)
                display_content = tamil_version
                
                if should_warn and validation_msg:
                    logger.warning(f"English converted to Tamil in Tamil mode: {content[:50]}")
        except Exception as e:
            logger.warning(f"Translation failed, using original: {str(e)}")
            # Fallback: use original content
            english_version = content
            tamil_version = content
            display_content = content
            validation_msg = "⚠️ Translation failed. Using original text."
            should_warn = True
        anon_user, _ = AnonymousUser.objects.get_or_create(session_id=session_id, defaults={'user_name': user_name})
        anon_user.last_seen = timezone.now()
        anon_user.is_online = True
        anon_user.save(update_fields=['last_seen', 'is_online'])
        
        message = save_message(group, content, english_version, tamil_version, display_content,
                              user_name, session_id, user_language_mode)
        
        group.last_activity = timezone.now()
        group.save(update_fields=['last_activity'])
        
        logger.info(f"Message sent by {user_name} ({user_language_mode} mode)")
        
        # Enforce language purity in response display
        if user_language_mode == 'tamil':
            # Tamil mode: Ensure ONLY Tamil characters in display
            display_for_response = ensure_tamil_only_display(display_content) if display_content else display_content
        else:
            # English mode: Already enforced during processing
            display_for_response = display_content
        
        # Build response with optional validation message from system
        response_data = {
            'success': True,
            'message': {
                'id': message.id,
                'user_name': message.user_name,
                'content': display_for_response,
                'tamil': tamil_version,
                'english': english_version,
                'timestamp': message.timestamp.isoformat(),
                'is_sender': True,
                'is_deleted': message.is_deleted,
                'language_mode': user_language_mode
            }
        }
        
        # Add validation warning if language conversion occurred
        if validation_msg:
            response_data['warning'] = validation_msg
            response_data['auto_converted'] = True
        
        return JsonResponse(response_data)
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Group not found', 'status': 'group_not_found'}, status=404)
    except Exception as e:
        logger.error(f"send_message_ajax error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["GET"])
def get_group_cleanup_status(request, code):
    """Get deletion status for a specific group."""
    try:
        group = Group.objects.get(code=code)
        should_delete, reason = group.should_auto_delete()
        online_count = group.get_group_online_count()
        
        return JsonResponse({
            'success': True,
            'group_code': group.code,
            'group_name': group.name,
            'created_at': group.created_at.isoformat(),
            'last_activity': group.last_activity.isoformat(),
            'age_minutes': (timezone.now() - group.created_at).total_seconds() / 60,
            'inactivity_minutes': (timezone.now() - group.last_activity).total_seconds() / 60,
            'online_count': online_count,
            'total_messages': group.messages.count(),
            'should_delete': should_delete,
            'delete_reason': reason
        })
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Group not found'}, status=404)
    except Exception as e:
        logger.error(f"get_group_cleanup_status error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["GET"])
def get_all_groups_status(request):
    """Get cleanup status for all groups."""
    try:
        all_groups = Group.objects.all()
        statuses = []
        
        for group in all_groups:
            should_delete, reason = group.should_auto_delete()
            online_count = group.get_group_online_count()
            
            statuses.append({
                'group_code': group.code,
                'group_name': group.name,
                'created_at': group.created_at.isoformat(),
                'last_activity': group.last_activity.isoformat(),
                'age_minutes': (timezone.now() - group.created_at).total_seconds() / 60,
                'inactivity_minutes': (timezone.now() - group.last_activity).total_seconds() / 60,
                'online_count': online_count,
                'total_messages': group.messages.count(),
                'should_delete': should_delete,
                'delete_reason': reason
            })
        
        statuses.sort(key=lambda x: (not x['should_delete'], x['inactivity_minutes']), reverse=True)
        
        return JsonResponse({'success': True, 'total_groups': len(statuses), 'groups': statuses})
    except Exception as e:
        logger.error(f"get_all_groups_status error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["POST"])
def translate_message(request, code):
    """Translate a message to user's selected language."""
    try:
        group = Group.objects.get(code=code)
        should_delete, delete_reason = check_and_cleanup_group(group)
        if should_delete:
            return JsonResponse({'error': 'Group deleted', 'status': 'group_deleted', 'reason': delete_reason}, status=410)
        
        # Simple rate limiting: max 10 translations per session per hour
        session_id = request.session.session_key
        if not session_id:
            return JsonResponse({'error': 'Session required'}, status=400)
        
        translation_count_key = f'translation_count_{session_id}'
        last_reset_key = f'translation_reset_{session_id}'
        
        now = timezone.now()
        last_reset = request.session.get(last_reset_key)
        if last_reset:
            last_reset = timezone.datetime.fromisoformat(last_reset)
            if (now - last_reset).total_seconds() > 3600:  # 1 hour
                request.session[translation_count_key] = 0
                request.session[last_reset_key] = now.isoformat()
        else:
            request.session[last_reset_key] = now.isoformat()
            request.session[translation_count_key] = 0
        
        count = request.session.get(translation_count_key, 0)
        if count >= 10:
            return JsonResponse({'error': 'Translation limit exceeded. Try again later.'}, status=429)
        
        request.session[translation_count_key] = count + 1
        
        text = request.POST.get('text', '').strip()
        target_language = request.POST.get('language', 'English').strip()
        
        if not text or not target_language:
            return JsonResponse({'error': 'Missing text or language'}, status=400)
        
        norm_success, normalized_text, _ = normalize_to_professional_english(text)
        text_to_translate = normalized_text if norm_success else text
        
        success, translated_text, message = translate_text(text_to_translate, target_language)
        
        if not success:
            return JsonResponse({'success': False, 'error': message, 'translated': text_to_translate}, status=400)
        
        return JsonResponse({'success': True, 'translated': translated_text, 'target_language': target_language, 'message': message})
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Group not found', 'status': 'group_not_found'}, status=404)
    except Exception as e:
        logger.error(f"translate_message error: {str(e)}")
        return JsonResponse({'error': f'Translation error: {str(e)}'}, status=400)


@require_http_methods(["POST"])
def synthesize_voice_message(request, code):
    """Synthesize translated text to speech and save as voice message."""
    try:
        group = Group.objects.get(code=code)
        should_delete, delete_reason = check_and_cleanup_group(group)
        if should_delete:
            return JsonResponse({'error': 'Group deleted', 'status': 'group_deleted', 'reason': delete_reason}, status=410)
        
        user_name = request.session.get('user_name', 'Anonymous')
        session_id = request.session.session_key
        user_language_mode = get_language_mode(request, session_id)
        
        text = request.POST.get('text', '').strip()
        print(f"Received text for synthesis: '{text[:100]}'")
        target_language = request.POST.get('language', 'English').strip()  # Target for synthesis
        
        if not text or not target_language:
            return JsonResponse({'error': 'Missing text or language'}, status=400)
        
        if len(text) > 5000:
            return JsonResponse({'error': 'Text too long for synthesis (max 5000 chars)'}, status=400)
        
        # Reject Tanglish
        if contains_tanglish(text):
            logger.warning(f"Tanglish in synthesis request from {user_name}: {text[:100]}")
            return JsonResponse({'error': 'Tanglish not allowed. Use English or Tamil only.'}, status=400)
        
        # Synthesize speech
        lang_code = 'ta' if target_language.lower() == 'tamil' else 'en'
        success, audio_bytes, synth_msg = synthesize_speech_with_gtts(text, lang_code)
        
        if not success:
            logger.warning(f"Speech synthesis failed: {synth_msg}")
            return JsonResponse({'error': 'Speech synthesis failed. ' + synth_msg, 'status': 'synthesis_failed'}, status=400)
        
        if not audio_bytes:
            return JsonResponse({'error': 'Generated audio is empty', 'status': 'empty_audio'}, status=400)
        
        # Save audio file
        from django.core.files.base import ContentFile
        anon_user, _ = AnonymousUser.objects.get_or_create(session_id=session_id, defaults={'user_name': user_name})
        anon_user.last_seen = timezone.now()
        anon_user.is_online = True
        anon_user.save(update_fields=['last_seen', 'is_online'])
        
        # Estimate duration: roughly 150 words/min = 2.5 words/sec; average 5 chars/word
        word_count = len(text.split())
        estimated_duration = max(1, word_count / 2.5)
        
        message = Message.objects.create(
            group=group,
            content=text,
            normalized_content=text,
            english_content=text if target_language.lower() == 'english' else text,
            tamil_content=text if target_language.lower() == 'tamil' else text,
            message_type='voice',
            duration=estimated_duration,
            user_name=user_name,
            session_id=session_id,
            audio_mime_type='audio/mpeg'
        )
        
        # Save the synthesized audio file
        audio_file_name = f'synthesized_{message.id}_{target_language.lower()}.mp3'
        message.audio_file.save(audio_file_name, ContentFile(audio_bytes))
        
        message.translated_content = text
        message.translated_language = target_language
        message.save(update_fields=['audio_file', 'translated_content', 'translated_language'])
        
        group.last_activity = timezone.now()
        group.save(update_fields=['last_activity'])
        
        logger.info(f"Synthesized voice message from {user_name}, duration: {estimated_duration}s, language: {target_language}")
        
        return JsonResponse({
            'success': True,
            'message_id': message.id,
            'audio_url': message.audio_file.url,
            'audio_mime_type': message.audio_mime_type,
            'duration': estimated_duration,
            'synthesis_msg': synth_msg
        })
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Group not found', 'status': 'group_not_found'}, status=404)
    except Exception as e:
        logger.error(f"synthesize_voice_message error: {str(e)}")
        return JsonResponse({'error': f'Synthesis error: {str(e)}'}, status=400)
