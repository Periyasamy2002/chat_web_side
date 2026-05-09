from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse

from chatproject import settings
from .models import Group, Message, AnonymousUser, GroupMember, DeletedMessage, ONLINE_TIMEOUT_MINUTES, UserProfile, Language
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
import uuid
import logging
from django.contrib import messages
import json
import io
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .utils.translator import translate_text, normalize_to_professional_english, synthesize_speech_with_gtts
from .utils.language import process_message_content, SUPPORTED_LANGUAGES
from .utils.tamil_detector import is_valid_english_only, get_language_violation_details, contains_tamil_script, ensure_english_only_display, ensure_tamil_only_display, ensure_hindi_only_display, TAMIL_SCRIPT_START, TAMIL_SCRIPT_END, contains_tanglish

logger = logging.getLogger(__name__)
import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Keep using google.generativeai (deprecated but stable)
# Suppress FutureWarning for now - full migration planned
import warnings
warnings.filterwarnings('ignore', category=FutureWarning, module='google.generativeai')
import google.generativeai as genai

genai.configure(api_key=GEMINI_API_KEY)
# Constants

def clean_tts_text(text):
    """Clean text for TTS generation by removing unsupported characters while preserving Unicode."""
    import re

    if not text:
        return ""

    # Remove emojis and unsupported symbols, but preserve Hindi Unicode characters
    # \u0900-\u097F covers Devanagari script (Hindi)
    # \u0B80-\u0BFF covers Tamil script
    text = re.sub(r'[^\w\s\u0900-\u097F\u0B80-\u0BFF]', '', text)

    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def ensure_session(request):
    """Ensure session key exists, create if None."""
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def file_exists_safely(file_field):
    """
    Safely check if a file field's file actually exists.
    Returns True only if file exists, handles all edge cases.
    """
    if not file_field or not file_field.name:
        return False
    
    try:
        # Check via storage
        if hasattr(file_field, 'storage'):
            return file_field.storage.exists(file_field.name)
        # Fallback: check filesystem
        if hasattr(file_field, 'path'):
            return os.path.exists(file_field.path)
    except Exception as e:
        logger.warning(f"Error checking file existence for {file_field.name}: {str(e)}")
    
    return False


def get_audio_url_safely(message):
    """
    Safely get audio URL from message, returns None if file doesn't exist.
    Prevents 404 errors when files are missing on ephemeral filesystems.
    """
    if not message or not message.audio_file:
        return None
    
    try:
        # Check if file actually exists before returning URL
        if file_exists_safely(message.audio_file):
            return message.audio_file.url
        else:
            logger.warning(f"Audio file missing for message {message.id}: {message.audio_file.name}")
            return None
    except Exception as e:
        logger.warning(f"Error getting audio URL for message {message.id}: {str(e)}")
        return None


def get_translation_audio_url_safely(translation):
    """
    Safely get audio URL from translation, returns None if file doesn't exist.
    """
    if not translation or not translation.audio_file:
        return None
    
    try:
        if file_exists_safely(translation.audio_file):
            return translation.audio_file.url
        else:
            logger.warning(f"Audio file missing for translation {translation.id}: {translation.audio_file.name}")
            return None
    except Exception as e:
        logger.warning(f"Error getting translation audio URL {translation.id}: {str(e)}")
        return None


def delete_file_field(file_field):
    """Delete a file field from storage and filesystem."""
    if not file_field:
        return

    try:
        # Try the standard Django way first
        if hasattr(file_field, 'storage') and hasattr(file_field, 'name') and file_field.name:
            if file_field.storage.exists(file_field.name):
                file_field.delete(save=False)
                logger.info(f"Deleted file via storage: {file_field.name}")
            else:
                logger.warning(f"File not found in storage: {file_field.name}")

        # Also try to delete from filesystem directly as backup
        if hasattr(file_field, 'path'):
            try:
                if os.path.exists(file_field.path):
                    os.remove(file_field.path)
                    logger.info(f"Deleted file from filesystem: {file_field.path}")
            except Exception as e:
                logger.warning(f"Failed to delete from filesystem: {str(e)}")

    except Exception as e:
        logger.warning(f"delete_file_field error: {str(e)}")


def delete_message_media(message):
    """Delete all media files associated with a message."""
    if not message:
        return

    logger.info(f"Deleting media for message {message.id} (type: {message.message_type})")

    media_fields = [
        'audio_file',
        'audio_file_english',
        'audio_file_tamil',
        'audio_file_hindi',
        'audio_file_malayalam',
        'audio_file_kannada'
    ]

    files_deleted = 0
    for field_name in media_fields:
        file_field = getattr(message, field_name, None)
        if file_field:
            logger.info(f"Deleting {field_name}: {file_field.name if hasattr(file_field, 'name') else 'no name'}")
            delete_file_field(file_field)
            files_deleted += 1

    # Delete translation audio files
    for translation in message.message_translations.all():
        if translation.audio_file:
            logger.info(f"Deleting translation audio for {translation.language}: {translation.audio_file.name}")
            delete_file_field(translation.audio_file)
            files_deleted += 1
        try:
            translation.delete()
        except Exception as e:
            logger.warning(f"delete_message_media translation delete error: {str(e)}")

    logger.info(f"Deleted {files_deleted} media files for message {message.id}")


def delete_group_and_media(group):
    """Delete a group and all its associated media files."""
    if not group:
        logger.warning("delete_group_and_media: No group provided")
        return

    logger.info(f"Starting deletion of group '{group.code}' with {group.messages.count()} messages")

    try:
        # Delete all messages and their media
        messages_deleted = 0
        for message in list(group.messages.all()):
            logger.info(f"Deleting message {message.id} with type {message.message_type}")
            delete_message_media(message)
            try:
                message.delete()
                messages_deleted += 1
            except Exception as e:
                logger.warning(f"delete_group_and_media message delete error: {str(e)}")

        logger.info(f"Deleted {messages_deleted} messages for group '{group.code}'")

        # Finally delete the group itself
        group.delete()
        logger.info(f"Successfully deleted group '{group.code}' and all associated data")

    except Exception as e:
        logger.error(f"delete_group_and_media error for group '{group.code}': {str(e)}")


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
                delete_group_and_media(group)
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
    mode = request.session.get('language_mode', 'english').lower()
    
    # Get from database if exists
    anon_user = AnonymousUser.objects.filter(session_id=session_id).first()
    if anon_user and anon_user.language_mode:
        mode = anon_user.language_mode.lower()
    
    # Normalize short codes and full names to the same format
    # Support both: 'ta'/'tamil', 'hi'/'hindi', 'en'/'english'
    mode_map = {
        'ta': 'tamil',
        'tamil': 'tamil',
        'hi': 'hindi',
        'hindi': 'hindi',
        'te': 'telugu',
        'telugu': 'telugu',
        'ml': 'malayalam',
        'malayalam': 'malayalam',
        'kn': 'kannada',
        'kannada': 'kannada',
        'bn': 'bengali',
        'bengali': 'bengali',
        'gu': 'gujarati',
        'gujarati': 'gujarati',
        'mr': 'marathi',
        'marathi': 'marathi',
        'pa': 'punjabi',
        'punjabi': 'punjabi',
        'ur': 'urdu',
        'urdu': 'urdu',
        'en': 'english',
        'english': 'english'
    }
    
    # Return normalized mode name
    return mode_map.get(mode, 'english')


def process_english_mode_gn(content):
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
            try:
                email = request.POST.get('email', '').strip()
                mobile = request.POST.get('mobile', '').strip()
                user = form.save()
                
                if email:
                    user.email = email
                    user.save(update_fields=['email'])
                
                # IMPORTANT: Ensure UserProfile is created
                profile, created = UserProfile.objects.get_or_create(
                    user=user,
                    defaults={'is_approved': False, 'mobile_number': mobile}
                )
                
                if not created and not profile.mobile_number and mobile:
                    profile.mobile_number = mobile
                    profile.save()
                
                logger.info(f"[REGISTER] [SUCCESS] User '{user.username}' registered. Profile created: {created}, approved: {profile.is_approved}")
                messages.success(request, "✅ Registration successful! Awaiting Admin approval.")
                return redirect("login")
            except Exception as e:
                logger.error(f"[REGISTER] Error: {str(e)}")
                messages.error(request, f"Registration error: {str(e)}")
        else:
            logger.warning(f"[REGISTER] Form errors: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = UserCreationForm()
    
    return render(request, "register.html", {"form": form})


def login_view(request):
    """
    Enhanced login view - works for both admins (superusers) and regular users.
    
    Flow:
    1. POST: Authenticate with Django's authenticate()
    2. For admins (is_superuser=True): Direct login, no profile check needed
    3. For regular users: Check UserProfile and approval status
    4. Redirect to appropriate page (admin panel or home)
    """
    if request.method == "POST":
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        
        logger.info(f"[LOGIN] Attempt for username: {username}")
        
        if not username or not password:
            logger.warning(f"[LOGIN] Empty credentials submitted")
            return render(request, "login.html", {
                "form": AuthenticationForm(),
                "error": "❌ Username and password required",
            })
        
        # Authenticate user with Django's built-in auth
        from django.contrib.auth import authenticate, login
        user = authenticate(request, username=username, password=password)
        
        if user is None:
            logger.warning(f"[LOGIN] Authentication FAILED for '{username}'")
            return render(request, "login.html", {
                "form": AuthenticationForm(),
                "error": "❌ Invalid username or password",
                "username": username
            })
        
        # ✅ Authentication successful
        logger.info(f"[LOGIN] User authenticated: {user.username} (ID: {user.id}, is_superuser: {user.is_superuser})")
        
        # Check if admin/superuser
        if user.is_superuser:
            logger.info(f"[LOGIN] [SUCCESS] Admin user '{user.username}' logging in - accessing /admin/")
            
            # Ensure session exists
            if not request.session.session_key:
                request.session.create()
            
            # Login the user
            login(request, user)
            logger.info(f"[LOGIN] Session created for admin: {request.session.session_key}")
            
            # Redirect to Django admin panel
            return redirect('home')
        
        # Regular user - check profile and approval
        try:
            profile = user.profile
        except UserProfile.DoesNotExist:
            # Auto-create profile for regular users
            profile = UserProfile.objects.create(user=user, is_approved=False)
            logger.info(f"[LOGIN] Auto-created profile for user: {user.username}")
        
        # Check if approved
        if not profile.is_approved:
            logger.warning(f"[LOGIN] User {user.username} NOT APPROVED")
            return render(request, "login.html", {
                "form": AuthenticationForm(),
                "error": "⏳ Your account is pending admin approval",
                "info": f"Account '{username}' was registered but needs approval. Please wait.",
                "username": username
            })
        
        # ✅ User approved - login
        logger.info(f"[LOGIN] [SUCCESS] Regular user '{user.username}' approved - logging in")
        
        if not request.session.session_key:
            request.session.create()
        
        login(request, user)
        logger.info(f"[LOGIN] Session created for user: {request.session.session_key}")
        
        # Redirect to home/dashboard
        return redirect('home')
    
    # GET request: Display login form
    else:
        form = AuthenticationForm()
        logger.debug(f"[LOGIN] GET request - displaying login form")
    
    return render(request, "login.html", {
        "form": form
    })

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
    all_languages = Language.objects.all().order_by('name')
    
    return render(request, "dashboard.html", {
        "pending_users": pending_users,
        "approved_users": approved_users,
        "groups": all_groups,
        "languages": all_languages
    })

@require_http_methods(["POST"])
def add_language(request):
    """Add a new language from the dropdown menu."""
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    try:
        data = json.loads(request.body)
        name = data.get('name')
        
        if name:
            lang, created = Language.objects.get_or_create(name=name)
            if not created and not lang.is_active:
                # If it exists but was disabled, re-enable it
                lang.is_active = True
                lang.save()
                return JsonResponse({'success': True})
            if created:
                return JsonResponse({'success': True})
            return JsonResponse({'success': False, 'error': f'"{name}" is already in the list.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'Language name is required.'}, status=400)

@require_http_methods(["POST"])
def toggle_language(request, lang_id):
    """Enable or disable a language's visibility."""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    lang = get_object_or_404(Language, id=lang_id)
    lang.is_active = not lang.is_active
    lang.save()
    return JsonResponse({'success': True, 'is_active': lang.is_active})

@require_http_methods(["POST"])
def delete_language(request, lang_id):
    """Hard delete a language from the database."""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    lang = get_object_or_404(Language, id=lang_id)
    lang.delete()
    return JsonResponse({'success': True})

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
    group_code = request.GET.get('code', '')
    
    if request.method == "POST":
        user_name = request.POST.get("user_name", "").strip()
        code = request.POST.get("code", "").strip()
        language_mode = request.POST.get("language_mode", "english").strip().lower()
        
        if not user_name or not code:
            return render(request, "chat.html", {"error": "Please enter both name and group code"})
        
        # Accept any language from user selection (validated by Language model)
        # Default to 'english' if empty or invalid
        if not language_mode:
            language_mode = 'english'
        
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

    # Get active languages from database
    try:
        active_languages = Language.objects.filter(is_active=True).values('id', 'name').order_by('name')
    except:
        active_languages = []
    
    context = {
        'languages': active_languages,
        'group_code': group_code
    }
    return render(request, "chat.html", context)

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

    # 🕒 Auto Expiry Logic: Delete groups older than 3 hours
    expiry_limit = timezone.now() - timedelta(hours=3)
    expired_groups = Group.objects.filter(created_at__lt=expiry_limit)
    for expired_group in expired_groups:
        delete_group_and_media(expired_group)

    error = None
    if request.method == "POST":
        code = request.POST.get("code", "").strip()
        name = request.POST.get("name", "").strip() or code

        if not code:
            error = "Group code is required"
        elif Group.objects.filter(code=code).exists():
            error = "Group code already exists"
        else:
            # Save group with owner info
            Group.objects.create(code=code, name=name, created_by=request.user)
            return redirect("group_manage")

    # 👁️ Visibility Rules: Admin sees all, Users see only their own
    if request.user.is_superuser:
        groups = Group.objects.all().order_by('-created_at')
    else:
        groups = Group.objects.filter(created_by=request.user).order_by('-created_at')

    groups_data = []
    for g in groups:
        # Calculate exact expiry timestamp for the countdown (created_at + 3 hours)
        expiry_time = g.created_at + timedelta(hours=3)
        groups_data.append({
            'code': g.code,
            'name': g.name,
            'created_at': g.created_at,
            'expiry_iso': expiry_time.isoformat(),
            'message_count': g.messages.count(),
            'online_count': g.get_group_online_count(),
            'last_activity': g.last_activity,
            'owner': g.created_by.username if g.created_by else "System"
        })

    return render(request, "group_create.html", {
        "groups": groups_data, 
        "error": error
    })

def delete_group_entirely(request, code):
    """Delete a group and all its data."""
    try:
        group = Group.objects.filter(code=code).first()
        if group:
            delete_group_and_media(group)
    except Exception as e:
        logger.error(f"delete_group_entirely error: {str(e)}")
    return redirect("group_manage")


@require_http_methods(["GET"])
def group_info(request, code):
    """Return basic metadata for a group code."""
    group = Group.objects.filter(code=code).first()
    if not group:
        return JsonResponse({'error': 'Group not found'}, status=404)

    return JsonResponse({
        'code': group.code,
        'name': group.name,
        'group_url': request.build_absolute_uri(reverse('group', args=[group.code]))
    })


def group(request, code):
    """
    Optimized group chat view with:
    - Message pagination (last 50 messages only)
    - Lazy per-user translation (no all-language generation)
    - Database query optimization (select_related)
    - Cache-aware message loading
    """
    try:
        # Optimized query: select_related for any foreign keys
        group = Group.objects.select_related().get(code=code)
    except Group.DoesNotExist:
        return redirect('chat')
    
    user_name = request.session.get('user_name', 'Anonymous')
    user_language_mode = request.session.get('language_mode', 'english').lower()
    session_id = ensure_session(request)
    
    # Ensure user is a member
    GroupMember.objects.get_or_create(
        group=group,
        session_id=session_id,
        defaults={'last_seen': timezone.now()}
    )
    
    # 📊 OPTIMIZATION 1: Pagination - Load last 50 messages only (not all)
    MESSAGE_PAGE_SIZE = 50
    
    # Get total count for pagination (text messages plus voice messages for this language)
    total_messages = group.messages.filter(
        Q(message_type='text') | Q(message_type='voice', translated_language=user_language_mode)
    ).count()
    
    # Optimized query: select_related for group (already done above)
    all_messages = group.messages.filter(
        Q(message_type='text') | Q(message_type='voice', translated_language=user_language_mode)
    ).select_related('group').order_by('timestamp')[max(0, total_messages - MESSAGE_PAGE_SIZE):]
    
    # 📊 OPTIMIZATION 2: Translate text messages on the fly for the user's language
    from chatapp.utils.translator import get_user_translation

    messages_list = []
    for msg in all_messages:
        if msg.message_type == 'text':
            english_version = msg.english_content or msg.normalized_content or msg.content or ""
            if user_language_mode == 'english':
                display_content = ensure_english_only_display(english_version) if english_version else ""
            else:
                success, translated, _ = get_user_translation(msg.id, english_version, user_language_mode, skip_cache=False)
                display_content = translated if success and translated else english_version
        else:
            display_content = msg.content or ""

        # Build message dict for template
        msg_data = {
            'id': msg.id,
            'user_name': msg.user_name,
            'content': display_content,
            'display_content': display_content,
            'original_content': msg.content,
            'english_content': msg.english_content or "",
            'message_type': msg.message_type,
            'timestamp': msg.timestamp,
            'session_id': msg.session_id,
            'is_deleted': msg.is_deleted,
            'audio_file': msg.audio_file,
            'audio_url': get_audio_url_safely(msg),
            'audio_mime_type': msg.audio_mime_type or 'audio/webm',
            'duration': msg.duration
        }
        messages_list.append(msg_data)
    
    # Get online users count
    online_users = AnonymousUser.objects.filter(
        last_seen__gte=timezone.now() - timedelta(minutes=ONLINE_TIMEOUT_MINUTES)
    ).distinct().count()
    
    last_message_timestamp = messages_list[-1]['timestamp'].isoformat() if messages_list else timezone.now().isoformat()
    
    # Get language name
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
    
    language_name = fallback_language_map.get(user_language_mode.lower(), user_language_mode.capitalize())
    
    try:
        lang_obj = Language.objects.filter(name__iexact=user_language_mode, is_active=True).first()
        if lang_obj:
            language_name = lang_obj.name
    except Exception as e:
        logger.warning(f"Error fetching language: {str(e)}")
    
    context = {
        "group": group,
        "messages": messages_list,
        "user_name": user_name,
        "online_count": online_users,
        "last_message_timestamp": last_message_timestamp,
        "language_mode": user_language_mode,
        "language_name": language_name,
        "user_session_id": session_id,
        "total_messages": total_messages,
        "has_more_messages": total_messages > MESSAGE_PAGE_SIZE,
    }
    
    return render(request, "group.html", context)

# ================================
# 🔹 IMPORTS
# ================================
import os
import tempfile
import uuid

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

import speech_recognition as sr
from pydub import AudioSegment, effects
from gtts import gTTS

from dotenv import load_dotenv

# Keep using google.generativeai (deprecated but stable)
# Suppress FutureWarning for now - full migration planned
import warnings
warnings.filterwarnings('ignore', category=FutureWarning, module='google.generativeai')
import google.generativeai as genai


# ================================
# 🔹 LOAD ENV + GEMINI
# ================================
# ================================
# 🔹 SPEECH TO TEXT
# ================================
def speech_to_text(audio_file_path, lang="en-IN"):

    print("==================================================")
    print(f"[MIC] STT STARTED")
    print(f"[MIC] File: {audio_file_path}")
    print(f"[MIC] Language: {lang}")
    print("==================================================")

    recognizer = sr.Recognizer()

    wav_file_path = audio_file_path + ".wav"

    try:

        # =====================================================
        # CHECK FILE EXISTS
        # =====================================================

        if not os.path.exists(audio_file_path):

            print("[ERROR] Audio file does not exist")

            return ""

        file_size = os.path.getsize(audio_file_path)

        print(f"[INFO] File size: {file_size} bytes")

        if file_size == 0:

            print("[ERROR] Empty audio file")

            return ""

        # =====================================================
        # CONVERT AUDIO TO WAV
        # =====================================================

        print("[PROCESS] Loading audio file...")

        audio = AudioSegment.from_file(audio_file_path)

        print(
            f"[STATS] Original audio: "
            f"{len(audio)}ms | "
            f"{audio.frame_rate}Hz | "
            f"{audio.channels} channels"
        )

        # =====================================================
        # AUDIO PREPROCESSING
        # =====================================================

        print("[PROCESS] Optimizing audio for STT...")

        # Normalize volume
        audio = effects.normalize(audio)

        # Mono channel
        if audio.channels > 1:

            audio = audio.set_channels(1)

            print("[AUDIO] Converted to mono")

        # Best sample rate for Google STT
        audio = audio.set_frame_rate(16000)

        print("[AUDIO] Sample rate set to 16000Hz")

        # Dynamic compression
        audio = effects.compress_dynamic_range(
            audio,
            threshold=-20.0,
            ratio=4.0,
            attack=5.0,
            release=50.0
        )

        print("[AUDIO] Compression applied")

        # =====================================================
        # EXPORT WAV
        # =====================================================

        audio.export(
            wav_file_path,
            format="wav"
        )

        print(f"[SUCCESS] WAV exported: {wav_file_path}")

        # =====================================================
        # LOAD AUDIO FOR RECOGNITION
        # =====================================================

        print("[AUDIO] Opening WAV for recognition...")

        with sr.AudioFile(wav_file_path) as source:

            # Better noise handling
            recognizer.energy_threshold = 300
            recognizer.dynamic_energy_threshold = True
            recognizer.pause_threshold = 0.8
            recognizer.non_speaking_duration = 0.5

            print("[AUDIO] Adjusting ambient noise...")

            recognizer.adjust_for_ambient_noise(
                source,
                duration=1
            )

            print(
                f"[AUDIO] Energy threshold: "
                f"{recognizer.energy_threshold}"
            )

            print("[AUDIO] Recording audio data...")

            audio_data = recognizer.record(source)

            print(
                f"[SUCCESS] Audio recorded "
                f"({len(audio_data.frame_data)} bytes)"
            )

        # =====================================================
        # RECOGNITION FUNCTION
        # =====================================================

        def try_recognize(locale):

            try:

                print(f"[STT] Trying locale: {locale}")

                result = recognizer.recognize_google(
                    audio_data,
                    language=locale,
                    show_all=True
                )

                print(f"[DEBUG] Raw Google Result: {result}")

                if not result:

                    print(f"[WARNING] Empty result for {locale}")

                    return None

                if isinstance(result, dict):

                    alternatives = result.get("alternative", [])

                    if alternatives:

                        best_result = alternatives[0]

                        text = best_result.get(
                            "transcript",
                            ""
                        ).strip()

                        confidence = best_result.get(
                            "confidence",
                            0
                        )

                        if text:

                            print(
                                f"[SUCCESS] "
                                f"Recognized with {locale}"
                            )

                            print(f"[TEXT] {text}")

                            print(
                                f"[CONFIDENCE] "
                                f"{confidence}"
                            )

                            return text

                elif isinstance(result, str):

                    text = result.strip()

                    if text:

                        print(
                            f"[SUCCESS] "
                            f"Recognized string result"
                        )

                        print(f"[TEXT] {text}")

                        return text

                return None

            except sr.UnknownValueError:

                print(
                    f"[WARNING] "
                    f"No speech recognized with {locale}"
                )

                return None

            except sr.RequestError as e:

                print(
                    f"[FAIL] Google API error "
                    f"for {locale}: {str(e)}"
                )

                return None

            except Exception as e:

                print(
                    f"[ERROR] Locale error "
                    f"for {locale}: {str(e)}"
                )

                return None

        # =====================================================
        # LOCALE FALLBACKS
        # =====================================================

        fallback_locales = STT_LOCALE_FALLBACKS.get(
            lang,
            [lang]
        )

        # Add English fallback
        if "en-IN" not in fallback_locales:

            fallback_locales.append("en-IN")

        print(f"[STT] Fallback locales: {fallback_locales}")

        # =====================================================
        # TRY ALL LOCALES
        # =====================================================

        for locale in fallback_locales:

            recognized_text = try_recognize(locale)

            if recognized_text:

                print("==================================================")
                print("[STT SUCCESS] speech_to_text COMPLETED")
                print("==================================================")

                return recognized_text.strip()

        # =====================================================
        # FINAL FAILURE
        # =====================================================

        print(
            f"[FAIL] STT failed for all locales: "
            f"{fallback_locales}"
        )

        return ""

    except sr.UnknownValueError:

        print("[FAIL] Speech not recognized")

        return ""

    except sr.RequestError as e:

        print(f"[FAIL] Google request failed: {str(e)}")

        return ""

    except Exception as e:

        print(f"[FAIL] Unexpected STT error: {str(e)}")

        return ""

    finally:

        # =====================================================
        # CLEANUP WAV
        # =====================================================

        try:

            if os.path.exists(wav_file_path):

                os.remove(wav_file_path)

                print("[CLEANUP] WAV file removed")

        except Exception as cleanup_error:

            print(
                f"[CLEANUP ERROR] "
                f"{str(cleanup_error)}"
            )

        print("==================================================")
        print("[MIC] STT END")
        print("==================================================")
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
# 🔹 MULTI-LANGUAGE SUPPORT MAPS
# ================================
LANGUAGE_MODE_TO_STT_LOCALE = {
    'english': 'en',
    'tamil': 'ta-IN',
    'hindi': 'hi-IN',
    'telugu': 'te-IN',
    'malayalam': 'ml-IN',
    'kannada': 'kn-IN',
    'bengali': 'bn-IN',
    'gujarati': 'gu-IN',
    'marathi': 'mr-IN',
    'punjabi': 'pa-IN',
    'urdu': 'ur-IN',
}

# ================================
# 🔹 SAFE REUSABLE TTS FUNCTION
# ================================
def create_tts_audio(text, language_code, media_root):
    """
    Create MP3 audio file from text using gTTS.
    
    Args:
        text: Text to convert to speech
        language_code: Language code (en, hi, ta, ml, etc.)
        media_root: Path to media directory
        
    Returns:
        filename if successful, None if failed
    """
    import os
    import uuid
    from gtts import gTTS
    
    try:
        print("=" * 50)
        print("[TTS] START")
        print(f"[TEXT] {text}")
        print(f"[LANG] {language_code}")

        if not text or not text.strip():
            print("[FAIL] Empty text")
            return None

        filename = f"{uuid.uuid4()}.mp3"
        output_path = os.path.join(media_root, filename)
        
        print(f"[PATH] {output_path}")

        tts = gTTS(
            text=text,
            lang=language_code,
            slow=False
        )

        tts.save(output_path)

        # Verify file was created
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"[SUCCESS] Audio saved: {output_path}")
            print(f"[SIZE] {file_size} bytes")
            return filename
        else:
            print("[FAIL] MP3 file not created after save")
            return None

    except Exception as e:
        print("[TTS ERROR]")
        print(f"[ERROR] {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

# Fallback STT locales for better recognition
STT_LOCALE_FALLBACKS = {
    'en': ['en-US', 'en-GB', 'en-IN', 'en-AU', 'en-CA', 'en'],
    'ta-IN': ['ta-IN', 'ta', 'en-IN'],  # Tamil with English fallback
    'hi-IN': ['hi-IN', 'hi', 'en-IN'],  # Hindi with English fallback
    'te-IN': ['te-IN', 'te', 'en-IN'],  # Telugu with English fallback
    'ml-IN': ['ml-IN', 'ml', 'en-IN'],  # Malayalam with English fallback
    'kn-IN': ['kn-IN', 'kn', 'en-IN'],  # Kannada with English fallback
    'bn-IN': ['bn-IN', 'bn', 'en-IN'],  # Bengali with English fallback
    'gu-IN': ['gu-IN', 'gu', 'en-IN'],  # Gujarati with English fallback
    'mr-IN': ['mr-IN', 'mr', 'en-IN'],  # Marathi with English fallback
    'pa-IN': ['pa-IN', 'pa', 'en-IN'],  # Punjabi with English fallback
    'ur-IN': ['ur-IN', 'ur', 'en-IN'],  # Urdu with English fallback
}

LANGUAGE_MODE_TO_GTTS_CODE = {
    'english': 'en',
    'tamil': 'ta',
    'hindi': 'hi',
    'telugu': 'te',
    'malayalam': 'ml',
    'kannada': 'kn',
    'bengali': 'bn',
    'gujarati': 'gu',
    'marathi': 'mr',
    'punjabi': 'pa',
    'urdu': 'ur',
}

LANGUAGE_MODE_TO_AUDIO_FIELD = {
    'english': 'audio_file_english',
    'tamil': 'audio_file_tamil',
    'hindi': 'audio_file_hindi',
    'malayalam': 'audio_file_malayalam',
    'kannada': 'audio_file_kannada',
}

SUPPORTED_TTS_LANGUAGES = ['english', 'tamil', 'hindi', 'malayalam', 'kannada']

LANGUAGE_NAME_FOR_TRANSLATION = {
    'english': 'English',
    'tamil': 'Tamil',
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


# ================================
# 🔹 DYNAMIC LANGUAGE DETECTION
# ================================

def get_active_languages_in_group(group):
    """
    Get set of active languages currently used by group members.
    Only generates translations/audio for these languages.
    """
    from django.utils import timezone
    from datetime import timedelta
    from django.db import models

    # Get online users in last 5 minutes + recent active users
    cutoff_time = timezone.now() - timedelta(minutes=ONLINE_TIMEOUT_MINUTES)

    # Get language modes from active group members
    active_languages = set(
        AnonymousUser.objects.filter(
            session_id__in=group.members.values_list('session_id', flat=True)
        ).filter(
            # Either online OR recently active
            models.Q(last_seen__gte=cutoff_time) |
            models.Q(is_online=True)
        ).values_list('language_mode', flat=True).distinct()
    )

    # Always include English as fallback
    active_languages.add('english')

    # Normalize language names
    normalized_languages = set()
    for lang in active_languages:
        if lang:
            normalized = lang.lower().strip()
            if normalized in LANGUAGE_MODE_TO_GTTS_CODE:
                normalized_languages.add(normalized)

    return normalized_languages


def generate_audio_for_active_languages(message, source_text, english_text, active_languages):
    """
    Generate audio ONLY for active languages in the group.
    Returns dict of language -> MessageTranslation objects.
    """
    from django.core.files.base import ContentFile
    from chatapp.models import MessageTranslation

    print(f"[AUDIO] Generating for active languages: {active_languages}")

    translations_created = {}

    # Always generate English audio if not already exists
    if 'english' in active_languages and english_text:
        try:
            # Check if already exists
            existing = MessageTranslation.objects.filter(
                message=message,
                language='english'
            ).first()

            if not existing:
                success, audio_bytes, synth_msg = synthesize_speech_with_gtts(english_text, 'en')
                if success and audio_bytes:
                    translation = MessageTranslation.objects.create(
                        message=message,
                        language='english',
                        translated_text=english_text,
                        audio_mime_type='audio/mpeg'
                    )
                    audio_filename = f'voice_{message.id}_english.mp3'
                    translation.audio_file.save(audio_filename, ContentFile(audio_bytes))
                    translation.save()
                    translations_created['english'] = translation
                    print(f"[SUCCESS] English audio created for message {message.id}")
                else:
                    print(f"[FAIL] English audio generation failed: {synth_msg}")
            else:
                translations_created['english'] = existing
                print(f"[SKIP] English audio already exists for message {message.id}")

        except Exception as e:
            print(f"[ERROR] English audio creation failed: {str(e)}")

    # Generate audio for other active languages
    for language in active_languages:
        if language == 'english':
            continue  # Already handled above

        try:
            # Check if already exists
            existing = MessageTranslation.objects.filter(
                message=message,
                language=language
            ).first()

            if existing:
                translations_created[language] = existing
                print(f"[SKIP] {language} audio already exists for message {message.id}")
                continue

            # Get translation for this language
            language_name = LANGUAGE_NAME_FOR_TRANSLATION.get(language, language.title())
            success, translated_text, msg = translate_text(
                english_text,
                language_name,
                source_language='English'
            )

            if not success or not translated_text:
                print(f"[FAIL] Translation to {language} failed: {msg}")
                continue

            # Generate audio
            lang_code = LANGUAGE_MODE_TO_GTTS_CODE.get(language, 'en')
            success, audio_bytes, synth_msg = synthesize_speech_with_gtts(translated_text, lang_code)

            if success and audio_bytes:
                translation = MessageTranslation.objects.create(
                    message=message,
                    language=language,
                    translated_text=translated_text,
                    audio_mime_type='audio/mpeg'
                )
                audio_filename = f'voice_{message.id}_{language}.mp3'
                translation.audio_file.save(audio_filename, ContentFile(audio_bytes))
                translation.save()
                translations_created[language] = translation
                print(f"[SUCCESS] {language} audio created for message {message.id}")
            else:
                print(f"[FAIL] {language} audio generation failed: {synth_msg}")

        except Exception as e:
            print(f"[ERROR] {language} audio creation failed: {str(e)}")

    return translations_created


def ensure_message_translation_for_language(message, language):
    """
    Ensure a message has translation/audio for a specific language.
    Generates it if it doesn't exist (lazy generation).
    """
    from chatapp.models import MessageTranslation
    from django.core.files.base import ContentFile

    # Check if already exists
    existing = MessageTranslation.objects.filter(
        message=message,
        language=language
    ).first()

    if existing:
        return existing

    # Generate translation/audio for this language
    english_text = message.english_content or message.normalized_content or message.content or ""

    if not english_text:
        print(f"[LAZY] No English text available for message {message.id}")
        return None

    try:
        # Get translation
        language_name = LANGUAGE_NAME_FOR_TRANSLATION.get(language, language.title())
        success, translated_text, msg = translate_text(
            english_text,
            language_name,
            source_language='English'
        )

        if not success or not translated_text:
            print(f"[LAZY] Translation failed for {language}: {msg}")
            return None

        # Generate audio
        lang_code = LANGUAGE_MODE_TO_GTTS_CODE.get(language, 'en')
        success, audio_bytes, synth_msg = synthesize_speech_with_gtts(translated_text, lang_code)

        if not success or not audio_bytes:
            print(f"[LAZY] Audio generation failed for {language}: {synth_msg}")
            return None

        # Create MessageTranslation
        translation = MessageTranslation.objects.create(
            message=message,
            language=language,
            translated_text=translated_text,
            audio_mime_type='audio/mpeg'
        )
        audio_filename = f'voice_{message.id}_{language}.mp3'
        translation.audio_file.save(audio_filename, ContentFile(audio_bytes))
        translation.save()

        print(f"[LAZY] Generated {language} translation/audio for message {message.id}")
        return translation

    except Exception as e:
        print(f"[LAZY] Error generating {language} for message {message.id}: {str(e)}")
        return None


# ================================
# 🔹 TEXT → 2 AUDIO (Tamil + English)
# ================================
def text_to_voice_by_mode(source_text, english_text, language_mode):
    try:
        from django.conf import settings
        import uuid
        import os

        filename = f"{uuid.uuid4()}.mp3"
        audio_path = os.path.join(settings.MEDIA_ROOT, filename)

        # =========================================
        # LANGUAGE MAP
        # =========================================
        lang_map = {
            "english": "en",
            "tamil": "ta",
            "hindi": "hi",
            "telugu": "te",
            "malayalam": "ml",
            "kannada": "kn",
            "bengali": "bn",
            "gujarati": "gu",
            "marathi": "mr",
            "punjabi": "pa",
            "urdu": "ur",
        }

        normalized_mode = language_mode.lower()

        # =========================================
        # SELECT TEXT + LANGUAGE
        # =========================================

        # English mode
        if normalized_mode in ["english", "en"]:

            text = english_text
            lang = "en"

        # Other language modes
        else:

            # Use source language voice
            text = source_text

            # Get correct gTTS language code
            lang = lang_map.get(normalized_mode, "en")

        print(f"[VOICE] Language Mode: {normalized_mode}")
        print(f"[VOICE] gTTS Lang Code: {lang}")
        print(f"[VOICE] Text: {text}")

        # =========================================
        # EMPTY TEXT CHECK
        # =========================================
        if not text or not text.strip():
            print("[VOICE ERROR] Empty text")
            return None, None

        # =========================================
        # GENERATE AUDIO
        # =========================================
        tts = gTTS(
            text=text,
            lang=lang,
            slow=False
        )

        tts.save(audio_path)

        print(f"[VOICE SUCCESS] Audio saved: {audio_path}")

        audio_url = f"{settings.MEDIA_URL}{filename}"

        return audio_url, audio_path

    except Exception as e:

        print(f"[VOICE ERROR] {str(e)}")

        return None, None
    
# ================================
# 🔹 GENERATE MULTILINGUAL AUDIO
# ================================
def generate_multilingual_audio(
    source_text,
    english_text,
    translated_text,
    source_language_mode,
    target_language_mode
):

    import os

    from django.conf import settings

    print("=" * 60)
    print("[AUDIO] MULTILINGUAL AUDIO GENERATION START")
    print("=" * 60)

    print(f"[SOURCE MODE] {source_language_mode}")
    print(f"[TARGET MODE] {target_language_mode}")

    try:

        # =========================================
        # NORMALIZE LANGUAGE MODES
        # =========================================
        source_language_mode = (
            source_language_mode or "english"
        ).lower()

        target_language_mode = (
            target_language_mode or "english"
        ).lower()

        # =========================================
        # AUDIO RESULT HOLDER
        # =========================================
        audio_files = {
            "english": None,
            "tamil": None,
            "hindi": None,
            "malayalam": None,
            "kannada": None,
            "source": None,
        }

        # =========================================
        # LANGUAGE CODE MAP
        # =========================================
        source_lang_code = LANGUAGE_MODE_TO_GTTS_CODE.get(
            source_language_mode,
            "en"
        )

        target_lang_code = LANGUAGE_MODE_TO_GTTS_CODE.get(
            target_language_mode,
            "en"
        )

        print(f"[SOURCE LANG CODE] {source_lang_code}")
        print(f"[TARGET LANG CODE] {target_lang_code}")
        print("-" * 60)

        # =========================================
        # ENGLISH AUDIO (always generate)
        # =========================================
        print("[AUDIO] Generating ENGLISH audio")
        if english_text and english_text.strip():
            filename = create_tts_audio(
                text=english_text,
                language_code="en",
                media_root=settings.MEDIA_ROOT
            )
            if filename:
                audio_files["english"] = {
                    "filename": filename,
                    "url": f"{settings.MEDIA_URL}{filename}",
                    "path": os.path.join(settings.MEDIA_ROOT, filename)
                }
                print(f"[SUCCESS] English audio: {filename}")
            else:
                print("[FAIL] English audio generation failed")
        else:
            print("[SKIP] English text empty")

        print("-" * 60)

        # =========================================
        # GENERATE ALL SUPPORTED LANGUAGE AUDIO
        # =========================================
        language_texts = {
            'tamil': None,
            'hindi': None,
            'malayalam': None,
            'kannada': None,
        }

        # If translated_text already represents the current target language,
        # reuse it for that language to avoid an extra translation call.
        if target_language_mode in language_texts and translated_text:
            language_texts[target_language_mode] = translated_text

        for lang_key in language_texts:
            if language_texts[lang_key] is None:
                language_name = LANGUAGE_NAME_FOR_TRANSLATION.get(lang_key, lang_key.title())
                success, translation, _ = translate_text(
                    english_text,
                    language_name,
                    source_language='English'
                )
                language_texts[lang_key] = translation if success and translation else english_text

            print(f"[AUDIO] Generating {lang_key.upper()} audio")
            if language_texts[lang_key] and language_texts[lang_key].strip():
                filename = create_tts_audio(
                    text=language_texts[lang_key],
                    language_code=LANGUAGE_MODE_TO_GTTS_CODE.get(lang_key, 'en'),
                    media_root=settings.MEDIA_ROOT
                )
                if filename:
                    audio_files[lang_key] = {
                        'filename': filename,
                        'url': f"{settings.MEDIA_URL}{filename}",
                        'path': os.path.join(settings.MEDIA_ROOT, filename)
                    }
                    print(f"[SUCCESS] {lang_key.title()} audio: {filename}")
                else:
                    print(f"[FAIL] {lang_key.title()} audio generation failed")
            else:
                print(f"[SKIP] {lang_key.title()} text empty")

            print("-" * 60)

        # =========================================
        # SOURCE AUDIO (use source language code)
        # =========================================
        print(f"[AUDIO] Generating SOURCE audio in {source_language_mode}")
        if source_text and source_text.strip():
            filename = create_tts_audio(
                text=source_text,
                language_code=source_lang_code,
                media_root=settings.MEDIA_ROOT
            )
            if filename:
                audio_files["source"] = {
                    "filename": filename,
                    "url": f"{settings.MEDIA_URL}{filename}",
                    "path": os.path.join(settings.MEDIA_ROOT, filename)
                }
                print(f"[SUCCESS] Source audio: {filename}")
            else:
                print(f"[FAIL] Source audio generation failed for {source_language_mode}")
        else:
            print("[SKIP] Source text empty")

        print("-" * 60)

        # =========================================
        # FINAL STATUS
        # =========================================
        print("=" * 60)
        print("[AUDIO] GENERATION COMPLETE")
        print("=" * 60)

        print(
            f"[RESULT] "
            f"English={audio_files['english'] is not None} | "
            f"Tamil={audio_files['tamil'] is not None} | "
            f"Hindi={audio_files['hindi'] is not None} | "
            f"Malayalam={audio_files['malayalam'] is not None} | "
            f"Kannada={audio_files['kannada'] is not None} | "
            f"Source={audio_files['source'] is not None}"
        )

        return audio_files

    except Exception as e:
        print("=" * 60)
        print("[FAIL] generate_multilingual_audio ERROR")
        print("=" * 60)
        print(f"[ERROR] {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            "english": None,
            "translated": None,
            "source": None
        }
# ================================
# 🔹 MAIN API
# ================================

@require_http_methods(["POST"])
def upload_voice_message(request, code):

    import os
    import uuid

    from django.conf import settings
    from django.http import JsonResponse
    from django.core.files import File
    from django.utils import timezone

    if 'audio' not in request.FILES:
        return JsonResponse({'error': 'Audio not received'}, status=400)

    audio_file = request.FILES['audio']
    transcript_text = request.POST.get('text', '').strip()

    if audio_file.size == 0:
        return JsonResponse({'error': 'Empty audio'}, status=400)

    temp_path = None

    try:

        # =====================================================
        # SAVE TEMP AUDIO
        # =====================================================
        file_name = f"{uuid.uuid4()}.webm"
        temp_path = os.path.join(settings.MEDIA_ROOT, file_name)

        with open(temp_path, 'wb+') as destination:
            for chunk in audio_file.chunks():
                destination.write(chunk)

        print(f"[SAVE] Temp audio saved: {temp_path}")

        # =====================================================
        # SESSION + LANGUAGE
        # =====================================================
        session_id = request.session.session_key

        if not session_id:
            request.session.create()
            session_id = request.session.session_key

        language_mode = request.session.get(
            'language_mode',
            'english'
        ).lower()

        print(f"[LANGUAGE] Current mode: {language_mode}")

        # =====================================================
        # SPEECH TO TEXT
        # =====================================================
        stt_locale = LANGUAGE_MODE_TO_STT_LOCALE.get(
            language_mode,
            'en-IN'
        )

        print(f"[STT] Using locale: {stt_locale}")

        source_text = speech_to_text(
            temp_path,
            lang=stt_locale
        )

        print(f"[STT RESULT] {source_text}")

        # fallback transcript
        if not source_text and transcript_text:
            source_text = transcript_text
            print("[FALLBACK] Using transcript text")

        stt_failed = False

        if not source_text:
            stt_failed = True
            source_text = ""
            english_text = ""
            translated_text = ""

            print("[FAIL] STT completely failed")

        else:

            # =====================================================
            # ENGLISH MODE
            # =====================================================
            if language_mode in ['english', 'en']:

                english_text = source_text

                success, translated_text, msg = translate_text(
                    english_text,
                    'Tamil',
                    source_language='English'
                )

                if not success:
                    translated_text = english_text

                print(f"[TRANSLATE] English -> Tamil")
                print(translated_text)

            # =====================================================
            # TAMIL MODE
            # =====================================================
            elif language_mode in ['tamil', 'ta']:

                translated_text = source_text

                success, english_text, msg = translate_text(
                    translated_text,
                    'English',
                    source_language='Tamil'
                )

                if not success:
                    english_text = translated_text

                print(f"[TRANSLATE] Tamil -> English")
                print(english_text)

            # =====================================================
            # OTHER LANGUAGES
            # =====================================================
            else:

                source_language_name = LANGUAGE_NAME_FOR_TRANSLATION.get(
                    language_mode,
                    'English'
                )

                # Source -> English
                success, english_text, msg = translate_text(
                    source_text,
                    'English',
                    source_language=source_language_name
                )

                if not success:
                    english_text = source_text

                # English -> SAME LANGUAGE
                success, translated_text, msg = translate_text(
                    english_text,
                    source_language_name,
                    source_language='English'
                )

                if not success:
                    translated_text = source_text

                print(f"[TRANSLATE] {source_language_name} -> English")
                print(english_text)

                print(f"[TRANSLATE] English -> {source_language_name}")
                print(translated_text)

        # =====================================================
        # GENERATE AUDIO
        # =====================================================
        target_language_mode = language_mode
        if language_mode in ['english', 'en']:
            # In English mode the translated text is always Tamil.
            target_language_mode = 'tamil'
            tamil_text = translated_text
        else:
            target_language_mode = language_mode
            # Always preserve a clean Tamil translation for backward compatibility
            success, tamil_text, _ = translate_text(
                english_text,
                'Tamil',
                source_language='English'
            )
            if not success or not tamil_text:
                tamil_text = english_text

        # =====================================================
        # DYNAMIC AUDIO GENERATION FOR ACTIVE LANGUAGES
        # =====================================================
        group = Group.objects.get(code=code)

        # Get active languages in this group
        active_languages = get_active_languages_in_group(group)
        print(f"[ACTIVE LANGUAGES] {active_languages}")

        # =====================================================
        # CREATE MESSAGES FOR ALL ACTIVE LANGUAGES
        # =====================================================
        user_name = request.session.get('user_name', 'Anonymous')
        created_messages = []

        for lang in active_languages:
            print(f"[MESSAGE] Creating message for language: {lang}")

            # Get translation for this language
            if lang == 'english':
                content = english_text
                translated_content = english_text
                audio_content = english_text
            elif lang == language_mode:
                # User's original language
                content = source_text
                translated_content = translated_text if translated_text else source_text
                audio_content = source_text
            else:
                # Translate to this language
                lang_name = LANGUAGE_NAME_FOR_TRANSLATION.get(lang, lang.title())
                success, lang_text, msg = translate_text(
                    english_text,
                    lang_name,
                    source_language='English'
                )
                if success and lang_text:
                    content = lang_text
                    translated_content = lang_text
                    audio_content = lang_text
                else:
                    content = english_text
                    translated_content = english_text
                    audio_content = english_text

            word_count = len(content.split()) if content else 0
            estimated_duration = max(1, word_count / 2.5)

            # Create message for this language
            message = Message.objects.create(
                group=group,
                content=content,
                normalized_content=english_text,  # Always store canonical English
                english_content=english_text,
                message_type='voice',
                duration=estimated_duration,
                user_name=user_name,
                session_id=session_id,
                audio_mime_type='audio/mpeg',
                translated_content=translated_content,
                translated_language=lang
            )

            # Generate audio for this language
            lang_code = LANGUAGE_MODE_TO_GTTS_CODE.get(lang, 'en')
            success, audio_bytes, synth_msg = synthesize_speech_with_gtts(audio_content, lang_code)

            if success and audio_bytes:
                from django.core.files.base import ContentFile
                audio_filename = f'voice_{message.id}_{lang}.mp3'
                message.audio_file.save(audio_filename, ContentFile(audio_bytes))
                message.save()
                print(f"[SUCCESS] Audio generated and saved for {lang}: {audio_filename}")
            else:
                print(f"[FAIL] Audio generation failed for {lang}: {synth_msg}")
                # Fallback to original audio if generation failed
                if os.path.exists(temp_path):
                    try:
                        with open(temp_path, 'rb') as f:
                            message.audio_file.save(
                                os.path.basename(temp_path),
                                File(f)
                            )
                        message.audio_mime_type = audio_file.content_type or 'audio/webm'
                        print(f"[FALLBACK] Original voice saved for {lang}")
                    except Exception as e:
                        print(f"[ERROR] Failed to save fallback audio for {lang}: {str(e)}")

            created_messages.append(message)
            print(f"[MESSAGE] Created ID: {message.id} for language: {lang}")

        # Use the message for the user's language for the response
        message = None
        for msg in created_messages:
            if msg.translated_language == language_mode:
                message = msg
                break
        # Fallback to first message if user's language not found
        if not message and created_messages:
            message = created_messages[0]

        # =====================================================
        # UPDATE USER STATUS
        # =====================================================
        anon_user, _ = AnonymousUser.objects.get_or_create(
            session_id=session_id,
            defaults={'user_name': user_name}
        )

        anon_user.last_seen = timezone.now()
        anon_user.is_online = True

        anon_user.save(
            update_fields=['last_seen', 'is_online']
        )

        group.last_activity = timezone.now()

        group.save(
            update_fields=['last_activity']
        )

        # =====================================================
        # DISPLAY CONTENT (for response)
        # =====================================================
        display_content = message.content if message else "🎤 Voice Message"

        # =====================================================
        # RESPONSE
        # =====================================================
        response_data = {
            'success': True,
            'message': {
                'id': message.id,
                'user_name': message.user_name,
                'display_content': display_content,
                'content': display_content,
                'source_text': source_text,
                'translated_text': message.translated_content,
                'english_text': english_text,
                'audio_url': get_audio_url_safely(message),
                'message_type': 'voice',
                'timestamp': message.timestamp.isoformat(),
                'is_sender': True,
                'duration': message.duration,
                'audio_mime_type': message.audio_mime_type,
                'language_mode': message.translated_language
            }
        }

        if stt_failed:
            response_data['warning'] = (
                "Speech recognition failed"
            )

        # =====================================================
        # CLEANUP GENERATED AUDIO
        # =====================================================
        for key in ['english', 'tamil', 'hindi', 'malayalam', 'kannada', 'source']:
            if (
                audio_files.get(key)
                and audio_files[key]['path']
                and os.path.exists(audio_files[key]['path'])
            ):
                try:
                    os.remove(audio_files[key]['path'])
                except:
                    pass

        # TEMP FILE CLEANUP
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

        print("[SUCCESS] upload_voice_message completed")

        return JsonResponse(response_data)

    except Exception as e:

        print(f"[ERROR] upload_voice_message: {str(e)}")

        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

        return JsonResponse({
            'error': str(e)
        }, status=500)

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
        session_id = ensure_session(request)
        
        # AUTHORIZATION CHECK: Must be group member
        is_member = GroupMember.objects.filter(
            group=group,
            session_id=session_id
        ).exists()
        if not is_member:
            return JsonResponse({'error': 'Unauthorized access to group'}, status=403)
        
        # REMOVED: check_and_cleanup_group() - now handled by background cron job
        
        # CACHE ONLINE USERS: Reduce database queries
        from django.core.cache import cache
        cache_key = f'online_users_{group.code}'
        cached_users = cache.get(cache_key)
        if cached_users:
            return JsonResponse(cached_users)
        
        group_user_session_ids = group.members.values_list('session_id', flat=True)
        online_users = AnonymousUser.objects.filter(
            session_id__in=group_user_session_ids,
            is_online=True,
            last_seen__gte=timezone.now() - timedelta(minutes=ONLINE_TIMEOUT_MINUTES)
        ).values_list('user_name', 'id', 'session_id').distinct()
        
        users_list = [{'id': user[1], 'session_id': user[2], 'display_name': user[0] or 'Anonymous'} for user in online_users]
        result = {'success': True, 'users': users_list, 'count': len(users_list)}
        
        # Cache for 30 seconds
        cache.set(cache_key, result, 30)
        
        return JsonResponse(result)
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Group not found', 'status': 'group_not_found'}, status=404)
    except Exception as e:
        logger.error(f"get_online_users error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["GET"])
def get_new_messages(request, code):
    """
    Optimized message polling with:
    - Per-user lazy translation (only translate to user's language)
    - Efficient caching (check cache before DB)
    - Minimal database queries
    """
    try:
        group = Group.objects.get(code=code)
        session_id = ensure_session(request)
        since_timestamp = request.GET.get('since', '')
        user_language_mode = get_language_mode(request, session_id)
        
        # Authorization check
        is_member = GroupMember.objects.filter(group=group, session_id=session_id).exists()
        if not is_member:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        # Optimized query with select_related
        base_query = Message.objects.filter(
            group=group,
            translated_language=user_language_mode
        ).select_related('group')
        
        if since_timestamp:
            try:
                from django.utils.dateparse import parse_datetime
                since_dt = parse_datetime(since_timestamp)
                if since_dt and not timezone.is_naive(since_dt):
                    base_query = base_query.filter(timestamp__gt=since_dt)
            except Exception as e:
                logger.warning(f"Invalid timestamp: {since_timestamp}")
        
        # Load last 50 messages only
        messages_query = base_query.order_by('-timestamp')[:50]
        messages_query = list(messages_query[::-1])  # Reverse to chronological
        
        # Get all deleted message IDs for this user (single query)
        deleted_ids = set(DeletedMessage.objects.filter(
            session_id=session_id
        ).values_list('message_id', flat=True))
        
        # Use lazy translation for each message
        from chatapp.utils.translator import get_user_translation
        
        messages_list = []
        from chatapp.utils.translator import get_user_translation

        for msg_obj in messages_query:
            if msg_obj.id in deleted_ids:
                continue
            
            try:
                if msg_obj.message_type == 'text':
                    english_version = msg_obj.english_content or msg_obj.normalized_content or msg_obj.content or ""
                    if user_language_mode == 'english':
                        display_content = ensure_english_only_display(english_version) if english_version else ""
                    else:
                        success, translated, _ = get_user_translation(msg_obj.id, english_version, user_language_mode, skip_cache=False)
                        display_content = translated if success and translated else english_version
                else:
                    display_content = msg_obj.content or ""
                
                msg_data = {
                    'id': msg_obj.id,
                    'user_name': msg_obj.user_name,
                    'content': display_content,
                    'display_content': display_content,
                    'english': msg_obj.english_content or "",
                    'message_type': msg_obj.message_type,
                    'timestamp': msg_obj.timestamp.isoformat(),
                    'is_sender': msg_obj.session_id == session_id,
                    'is_deleted': False,
                    'language_mode': msg_obj.translated_language,
                }
                
                if msg_obj.message_type == 'voice':
                    # Audio is already attached to the message
                    msg_data['audio_url'] = get_audio_url_safely(msg_obj)
                    msg_data['audio_mime_type'] = msg_obj.audio_mime_type or 'audio/mpeg'
                    msg_data['duration'] = msg_obj.duration
                
                messages_list.append(msg_data)
            except Exception as e:
                logger.error(f"Error processing message {msg_obj.id}: {str(e)}")
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
        session_id = ensure_session(request)
        user_name = request.session.get('user_name', 'Anonymous')
        content = request.POST.get('message', '').strip()
        user_language_mode = get_language_mode(request, session_id)
        
        # AUTHORIZATION CHECK: Must be group member
        is_member = GroupMember.objects.filter(
            group=group,
            session_id=session_id
        ).exists()
        if not is_member:
            return JsonResponse({'error': 'Unauthorized access to group'}, status=403)
        
        # REMOVED: check_and_cleanup_group() - now handled by background cron job
        # This prevents expensive operations during user requests
        
        if not content:
            return JsonResponse({'error': 'Message cannot be empty'}, status=400)

        # RATE LIMITING: Prevent spam
        from django.core.cache import cache
        rate_limit_key = f'send_message_{session_id}'
        message_count = cache.get(rate_limit_key, 0)
        if message_count >= 20:  # 20 messages per minute
            return JsonResponse({'error': 'Rate limit exceeded. Please wait before sending more messages.'}, status=429)
        cache.set(rate_limit_key, message_count + 1, 60)  # 1 minute expiry

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
            # Use the new generic multi-language processor
            english_version, display_content, validation_msg, should_warn, tamil_version = process_message_content(content, user_language_mode)
        except Exception as e:
            
            return JsonResponse({'error': str(e)}, status=400)
        
        # STORE CANONICAL ENGLISH VERSION ONLY
        # This ensures all users get the same base message
        # Each user will see their own language translation when fetching
        message = Message.objects.create(
            group=group,
            user_name=user_name,
            session_id=session_id,
            content=english_version,  # Store canonical English
            normalized_content=english_version,
            english_content=english_version,
            tamil_content=tamil_version,  # Keep for backward compatibility
            message_type='text',
            translations='',
            # Don't store translated_content/language - will be translated per-user on retrieval
            translated_content='',
            translated_language=''
        )
        group.last_activity = timezone.now()
        group.save(update_fields=['last_activity'])
        
        logger.debug(f"Message sent by {user_name} ({user_language_mode} mode)")
        
        # TRANSLATE FOR IMMEDIATE RESPONSE DISPLAY
        # Since we store canonical English, translate to user's language for immediate feedback
        if user_language_mode == 'english':
            display_for_response = ensure_english_only_display(english_version)
        elif user_language_mode == 'tamil':
            display_for_response = ensure_tamil_only_display(display_content) if display_content else display_content
        else:
            # OTHER LANGUAGES: Translate English → User's language for display
            try:
                translated_success, translated_text, _ = translate_text(english_version, SUPPORTED_LANGUAGES.get(user_language_mode, user_language_mode), source_language='English')
                if translated_success and translated_text:
                    display_for_response = translated_text
                    # Apply script filtering for purity
                    if user_language_mode == 'hindi':
                        display_for_response = ensure_hindi_only_display(display_for_response)
                    # Add similar for other languages if needed
                else:
                    display_for_response = english_version  # Fallback
            except Exception as e:
                logger.warning(f"Failed to translate response to {user_language_mode}: {e}")
                display_for_response = english_version
        
        # Build response with optional validation message from system
        response_data = {
            'success': True,
            'message': {
                'id': message.id,
                'user_name': message.user_name,
                'content': display_for_response,
                'display_content': display_for_response,
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
        session_id = ensure_session(request)
        user_name = request.session.get('user_name', 'Anonymous')
        user_language_mode = get_language_mode(request, session_id)
        
        # AUTHORIZATION CHECK: Must be group member
        is_member = GroupMember.objects.filter(
            group=group,
            session_id=session_id
        ).exists()
        if not is_member:
            return JsonResponse({'error': 'Unauthorized access to group'}, status=403)
        
        # REMOVED: check_and_cleanup_group() - now handled by background cron job
        
        text = request.POST.get('text', '').strip()
        target_language = request.POST.get('language', 'English').strip()
        
        if not text or not target_language:
            return JsonResponse({'error': 'Missing text or language'}, status=400)
        
        # RATE LIMITING: Prevent abuse of TTS service
        from django.core.cache import cache
        tts_rate_key = f'tts_{session_id}'
        tts_count = cache.get(tts_rate_key, 0)
        if tts_count >= 10:  # 10 TTS requests per hour
            return JsonResponse({'error': 'TTS rate limit exceeded. Please wait before requesting more speech synthesis.'}, status=429)
        cache.set(tts_rate_key, tts_count + 1, 3600)  # 1 hour expiry
        
        if len(text) > 5000:
            return JsonResponse({'error': 'Text too long for synthesis (max 5000 chars)'}, status=400)
        
        # Reject Tanglish
        if contains_tanglish(text):
            logger.warning(f"Tanglish in synthesis request from {user_name}: {text[:100]}")
            return JsonResponse({'error': 'Tanglish not allowed. Use English or Tamil only.'}, status=400)
        
        # Synthesize speech - map language names to gTTS codes
        lang_code_map = {
            'english': 'en',
            'tamil': 'ta',
            'hindi': 'hi',
            'telugu': 'te',
            'malayalam': 'ml',
            'kannada': 'kn',
            'bengali': 'bn',
            'gujarati': 'gu',
            'marathi': 'mr',
            'punjabi': 'pa',
            'urdu': 'ur',
        }
        lang_code = lang_code_map.get(target_language.lower(), 'en')  # Default to English
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
            english_content='',
            tamil_content='',
            message_type='voice',
            duration=estimated_duration,
            user_name=user_name,
            session_id=session_id,
            audio_mime_type='audio/mpeg'
        )

        if target_language.lower() == 'english':
            message.english_content = text
        elif target_language.lower() == 'tamil':
            message.tamil_content = text
        
        # Save the synthesized audio file
        audio_file_name = f'synthesized_{message.id}_{target_language.lower()}.mp3'
        message.audio_file.save(audio_file_name, ContentFile(audio_bytes))
        
        message.translated_content = text
        message.translated_language = target_language
        message.save(update_fields=['audio_file', 'translated_content', 'translated_language', 'english_content', 'tamil_content'])
        
        group.last_activity = timezone.now()
        group.save(update_fields=['last_activity'])
        
        logger.debug(f"Synthesized voice message from {user_name}, duration: {estimated_duration}s, language: {target_language}")
        
        return JsonResponse({
            'success': True,
            'message_id': message.id,
            'audio_url': get_audio_url_safely(message),
            'audio_mime_type': message.audio_mime_type,
            'duration': estimated_duration,
            'synthesis_msg': synth_msg
        })
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Group not found', 'status': 'group_not_found'}, status=404)
    except Exception as e:
        logger.error(f"synthesize_voice_message error: {str(e)}")
        return JsonResponse({'error': f'Synthesis error: {str(e)}'}, status=400)




@require_http_methods(["GET"])
def get_translation_metrics(request):
    """Get API usage metrics (admin only)."""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        from chatapp.utils.translator import get_translation_metrics
        metrics = get_translation_metrics()
        return JsonResponse({'success': True, 'metrics': metrics})
    except Exception as e:
        logger.error(f"get_translation_metrics error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["GET"])
def load_more_messages(request, code):
    """Load older messages when user scrolls up (pagination)."""
    try:
        group = Group.objects.get(code=code)
        session_id = ensure_session(request)
        
        # Authorization check
        is_member = GroupMember.objects.filter(group=group, session_id=session_id).exists()
        if not is_member:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        user_language_mode = get_language_mode(request, session_id)
        offset = int(request.GET.get('offset', 0))  # Which batch to load
        limit = int(request.GET.get('limit', 50))   # Messages per batch
        
        # Safety checks
        offset = max(0, min(offset, 10000))  # Max offset
        limit = max(1, min(limit, 100))      # Max 100 messages per request
        
        # Get total count
        total_messages = group.messages.count()
        
        # Load older messages (skip the most recent ones already loaded)
        older_messages = group.messages.select_related('group').order_by('timestamp')[
            offset:offset + limit
        ]
        
        # Get deleted IDs
        deleted_ids = set(DeletedMessage.objects.filter(
            session_id=session_id
        ).values_list('message_id', flat=True))
        
        from chatapp.utils.translator import get_user_translation
        
        messages_list = []
        for msg_obj in older_messages:
            if msg_obj.id in deleted_ids:
                continue
            
            try:
                english_version = msg_obj.english_content or msg_obj.normalized_content or msg_obj.content or ""
                
                if user_language_mode == 'english':
                    display_content = ensure_english_only_display(english_version) if english_version else ""
                else:
                    success, translated, _ = get_user_translation(msg_obj.id, english_version, user_language_mode, skip_cache=False)
                    display_content = translated if success and translated else english_version
                
                msg_data = {
                    'id': msg_obj.id,
                    'user_name': msg_obj.user_name,
                    'content': display_content,
                    'message_type': msg_obj.message_type,
                    'timestamp': msg_obj.timestamp.isoformat(),
                    'is_sender': msg_obj.session_id == session_id,
                    'duration': msg_obj.duration if msg_obj.message_type == 'voice' else 0,
                }
                
                if msg_obj.message_type == 'voice':
                    # Get audio for user's language from MessageTranslation
                    from chatapp.models import MessageTranslation
                    user_translation = MessageTranslation.objects.filter(
                        message=msg_obj,
                        language=user_language_mode
                    ).first()

                    if not user_translation:
                        # Lazy generation: create translation/audio for this language
                        user_translation = ensure_message_translation_for_language(msg_obj, user_language_mode)

                    if user_translation and user_translation.audio_file:
                        msg_data['audio_url'] = get_translation_audio_url_safely(user_translation)
                        msg_data['audio_mime_type'] = user_translation.audio_mime_type or 'audio/mpeg'
                        print(f"[VOICE LOAD_MORE] Using {user_language_mode} audio for message {msg_obj.id}")
                    elif user_language_mode != 'english':
                        # Try English fallback
                        english_translation = MessageTranslation.objects.filter(
                            message=msg_obj,
                            language='english'
                        ).first()

                        if not english_translation:
                            english_translation = ensure_message_translation_for_language(msg_obj, 'english')

                        if english_translation and english_translation.audio_file:
                            msg_data['audio_url'] = get_translation_audio_url_safely(english_translation)
                            msg_data['audio_mime_type'] = english_translation.audio_mime_type or 'audio/mpeg'
                            print(f"[VOICE LOAD_MORE] Using English fallback for message {msg_obj.id}")
                        else:
                            print(f"[VOICE LOAD_MORE] No audio for message {msg_obj.id}")
                    else:
                        print(f"[VOICE LOAD_MORE] No audio for message {msg_obj.id}")
                
                messages_list.append(msg_data)
            except Exception as e:
                logger.error(f"Error loading message {msg_obj.id}: {str(e)}")
                continue
        
        return JsonResponse({
            'success': True,
            'messages': messages_list,
            'offset': offset + limit,
            'has_more': (offset + limit) < total_messages,
            'total_messages': total_messages,
        })
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Group not found'}, status=404)
    except Exception as e:
        logger.error(f"load_more_messages error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)


from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.http import require_http_methods

@require_http_methods(["GET", "POST"])
def admin_register_view(request):
    """Create new Django admin (superuser) with protection."""
    error = None
    success = None
    secret_key = os.getenv('ADMIN_SECRET_KEY', '')
    
    # 🔥 SECURITY FIX: Use POST only for admin key
    provided_key = request.POST.get('admin_key', '') if request.method == 'POST' else ''
    
    # Count existing superusers
    superuser_count = User.objects.filter(is_superuser=True).count()
    can_register = True
    
    # If superuser exists, require secret key
    if superuser_count > 0 and secret_key:
        if provided_key != secret_key:
            can_register = False
            error = "❌ Invalid or missing admin registration key"
    
    # Check admin limit with transaction safety
    if superuser_count >= 3:
        return render(request, "admin_register.html", {
            "error": "❌ Admin limit reached (only 3 allowed)",
            "superuser_count": superuser_count
        })

    if request.method == "POST":
        provided_key = request.POST.get('admin_key', '')
        
        # If superuser exists, require secret key
        if superuser_count > 0 and secret_key:
            if provided_key != secret_key:
                can_register = False
                error = "❌ Invalid or missing admin registration key"

        if not can_register:
            return render(request, "admin_register.html", {
                "error": error,
                "superuser_count": superuser_count
            })

        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()
        password_confirm = request.POST.get("password_confirm", "").strip()

        # Validation
        if not username or not email or not password or not password_confirm:
            error = "⚠️ All fields are required"
        elif len(username) < 3:
            error = "⚠️ Username must be at least 3 characters"
        elif len(password) < 8:
            error = "⚠️ Password must be at least 8 characters"
        elif password != password_confirm:
            error = "⚠️ Passwords don't match"
        elif not email or '@' not in email:
            error = "⚠️ Valid email required"
        elif User.objects.filter(username=username).exists():
            error = "⚠️ Username already exists"
        elif User.objects.filter(email=email).exists():
            error = "⚠️ Email already exists"
        else:
            # RACE CONDITION FIX: Use transaction.atomic()
            from django.db import transaction
            try:
                with transaction.atomic():
                    # Recheck count inside transaction
                    current_count = User.objects.filter(is_superuser=True).count()
                    if current_count >= 3:
                        raise ValueError("Admin limit reached during registration")
                    
                    # ✅ Create Django superuser with proper password hashing
                    user = User.objects.create_superuser(
                        username=username,
                        email=email,
                        password=password
                    )
                    logger.info(f"[SUCCESS] New superuser created: {username} ({email})")
                    
                    success = f"✅ Admin '{username}' registered successfully! Redirecting to login..."
                    messages.success(request, f"Admin account created! You can now login with username '{username}'")
                    
                    # Redirect to login after 2 seconds (JS in template)
                    return render(request, "admin_register.html", {
                        "success": success,
                        "superuser_count": current_count + 1,
                        "redirect": True
                    })
            except ValueError as ve:
                error = f"❌ {str(ve)}"
            except Exception as e:
                logger.error(f"❌ Error creating admin: {str(e)}")
                error = f"❌ Error creating admin: {str(e)}"
            
    return render(request, "admin_register.html", {
        "error": error,
        "success": success,
        "superuser_count": superuser_count,
        "key_required": superuser_count > 0 and secret_key and not can_register
    }) 