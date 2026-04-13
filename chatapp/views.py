from django.shortcuts import render, redirect
from .models import Group, Message, AnonymousUser, ONLINE_TIMEOUT_MINUTES
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import timedelta
import uuid
import logging
from .utils.translator import translate_text, normalize_to_professional_english
from .utils.tamil_detector import is_valid_english_only, get_language_violation_details, contains_tamil_script, ensure_english_only_display, ensure_tamil_only_display, TAMIL_SCRIPT_START, TAMIL_SCRIPT_END, contains_tanglish

logger = logging.getLogger(__name__)

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
        for user in inactive:
            user.is_online = False
            user.save(update_fields=['is_online'])
        return inactive.count()
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
    
    Rules:
    - Input: Accept English only
    - If Tamil detected: Auto-convert to English
    - If Tanglish detected: Auto-convert to English
    - Output: English only (display)
    
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
            # If translation fails, keep original (don't filter it away!)
            english_version = content
        
        validation_msg = "⚠️ Tamil script detected. Converting to English. Only English allowed."
        should_warn = True
    
    elif has_tanglish:
        # Tanglish detected (Tamil written in English letters like "sollren") - convert to English
        logger.info(f"Tanglish detected in English mode - auto-converting: {content[:50]}")
        
        try:
            # First, try translating as if it's Tamil phonetic spelling
            # This sends it to Gemini which understands "sollren" = "tell me" in English
            eng_success, english_converted, _ = translate_text(content, 'English')
            english_version = english_converted if eng_success else content
        except Exception as e:
            logger.warning(f"Failed to convert Tanglish to English: {str(e)}")
            # If translation fails, keep original (Tanglish is already English letters, should display fine)
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
    
    # Generate Tamil backend version (for storage only, not display)
    try:
        tamil_success, tamil_version, _ = translate_text(english_version, 'Tamil')
        tamil_version = tamil_version if tamil_success else english_version
    except Exception as e:
        logger.warning(f"Failed to translate to Tamil: {str(e)}")
        tamil_version = english_version
    
    return english_version, tamil_version, validation_msg, should_warn


def process_tamil_mode_message(content):
    """
    Process message in Tamil mode: STRICT TAMIL ONLY DISPLAY.
    
    Rules:
    - Input: Accept Tamil + English
    - If English detected: Auto-convert to Tamil
    - If Tanglish detected: Auto-convert to Tamil
    - Output: Tamil only (display), English as backend/translation
    
    Returns: (english_backend, tamil_display, validation_msg, should_warn)
    """
    has_tamil = contains_tamil_script(content)
    has_tanglish = contains_tanglish(content)
    # Check for English: any ASCII letters (a-z, A-Z) that are NOT in Tanglish patterns
    has_english = any(('a' <= c <= 'z' or 'A' <= c <= 'Z') for c in content)
    
    if has_tamil and not has_english:
        # CASE 1: Pure Tamil (no English, no Tanglish) - KEEP AS IS
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
        # CASE 2: Pure Tanglish (no Tamil script, but Tamil words in English) - CONVERT TO TAMIL
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
        # CASE 3: English detected (pure or mixed with Tamil) - auto-convert to Tamil
        logger.info(f"English detected in Tamil mode - auto-converting: {content[:50]}")
        
        # First, try translating the mixed content as-is
        try:
            tamil_success, tamil_translated, _ = translate_text(content, 'Tamil')
            tamil_version = tamil_translated if tamil_success else content
        except Exception as e:
            logger.warning(f"Failed to translate to Tamil: {str(e)}")
            tamil_version = content
        
        # Get English version
        try:
            eng_success, english_version, _ = translate_text(content, 'English')
            english_version = english_version if eng_success else content
        except Exception as e:
            logger.warning(f"Failed to translate to English: {str(e)}")
            english_version = content
        
        validation_msg = "⚠️ English detected. Converting to Tamil. Only Tamil characters allowed in display."
        should_warn = True
    
    else:
        # CASE 4: Nothing detected (shouldn't happen) - treat as English
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


def home(request):
    """Home page - entry point of the app."""
    return render(request, "home.html")


def chat(request):
    """Chat page - user enters their name and group code."""
    if request.method == "POST":
        user_name = request.POST.get("user_name", "").strip()
        code = request.POST.get("code", "").strip()
        language = request.POST.get("language", "English").strip()
        language_mode = request.POST.get("language_mode", "english").strip().lower()
        
        if not user_name or not code:
            return render(request, "chat.html", {"error": "Please enter both name and group code"})
        
        is_valid_name, name_error = is_valid_english_only(user_name)
        if not is_valid_name:
            logger.warning(f"NON-ENGLISH username rejected: {user_name}")
            return render(request, "chat.html", {
                "error": "Username must be in English only. Tamil script and Tanglish are not allowed."
            })
        
        language_mode = language_mode if language_mode in ['english', 'tamil'] else 'english'
        
        request.session['user_name'] = user_name
        request.session['user_id'] = request.session.get('user_id') or str(uuid.uuid4())
        request.session['language'] = language
        request.session['language_mode'] = language_mode
        request.session.save()
        
        group, _ = Group.objects.get_or_create(code=code, defaults={"name": code})
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
            
            logger.info(f"User '{user_name}' joined group '{code}' (mode: {language_mode})")
        except Exception as e:
            logger.error(f"Error creating user record: {str(e)}")
        
        request.session['group_code'] = code
        return redirect("group", code=group.code)

    return render(request, "chat.html")


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


@require_http_methods(["POST"])
def upload_voice_message(request, code):
    """Handle voice message uploads."""
    try:
        group = Group.objects.get(code=code)
        should_delete, delete_reason = check_and_cleanup_group(group)
        if should_delete:
            return JsonResponse({'error': 'Group deleted', 'status': 'group_deleted', 'reason': delete_reason}, status=410)
        
        user_name = request.session.get('user_name', 'Anonymous')
        user_language = request.session.get('language', 'English').strip()
        session_id = request.session.session_key
        
        if 'audio' not in request.FILES:
            return JsonResponse({'error': 'Voice input not detected. Please try again.', 'status': 'no_audio_detected'}, status=400)
        
        audio_file = request.FILES['audio']
        duration = float(request.POST.get('duration', 0))
        audio_mime_type = request.POST.get('audio_mime_type', 'audio/webm')
        voice_text = request.POST.get('text', '').strip()
        
        if audio_file.size == 0 or duration < 0.5:
            return JsonResponse({'error': 'Voice input not detected. Please try again.', 'status': 'voice_invalid'}, status=400)
        
        if audio_file.size > 50 * 1024 * 1024:
            return JsonResponse({'error': 'Audio file too large (max 50MB)', 'status': 'audio_too_large'}, status=400)
        
        if voice_text:
            is_valid_voice, voice_error_msg = is_valid_english_only(voice_text)
            if not is_valid_voice:
                violations = get_language_violation_details(voice_text)
                logger.warning(f"NON-ENGLISH voice message rejected from {user_name}: {violations}")
                return JsonResponse({'error': voice_error_msg or 'Voice message text must be in English only.', 
                                   'status': 'language_violation_speech', 'details': violations}, status=400)
        
        anon_user, _ = AnonymousUser.objects.get_or_create(session_id=session_id, defaults={'user_name': user_name})
        anon_user.last_seen = timezone.now()
        anon_user.is_online = True
        anon_user.save(update_fields=['last_seen', 'is_online'])
        
        normalized_text = voice_text
        tamil_text = voice_text
        if voice_text:
            norm_success, normalized_text, _ = normalize_to_professional_english(voice_text, user_language)
            normalized_text = ensure_us_english(normalized_text if norm_success else voice_text)
            
            try:
                tamil_success, tamil_text, _ = translate_text(normalized_text, 'Tamil')
                tamil_text = tamil_text if tamil_success else normalized_text
            except Exception as e:
                logger.warning(f"Failed to translate voice to Tamil: {str(e)}")
                tamil_text = normalized_text
        
        message = Message.objects.create(
            group=group,
            audio_file=audio_file,
            audio_mime_type=audio_mime_type,
            content=voice_text if voice_text else None,
            normalized_content=normalized_text if voice_text else None,
            english_content=normalized_text if voice_text else None,
            tamil_content=tamil_text if voice_text else None,
            message_type='voice',
            duration=max(duration, 1),
            user_name=user_name,
            session_id=session_id
        )
        
        if voice_text and user_language.lower() == 'tamil':
            message.translated_content = tamil_text
            message.translated_language = 'Tamil'
            message.save(update_fields=['translated_content', 'translated_language'])
        
        group.last_activity = timezone.now()
        group.save(update_fields=['last_activity'])
        
        logger.info(f"Voice message created by {user_name}, duration: {duration}s")
        
        return JsonResponse({
            'success': True,
            'message_id': message.id,
            'audio_url': message.audio_file.url,
            'audio_mime_type': message.audio_mime_type,
            'duration': duration,
            'has_transcription': bool(voice_text)
        })
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Group not found', 'status': 'group_not_found'}, status=404)
    except ValueError as ve:
        logger.error(f"Value error in upload_voice_message: {str(ve)}")
        return JsonResponse({'error': 'Invalid audio duration or format', 'status': 'invalid_format'}, status=400)
    except Exception as e:
        logger.error(f"upload_voice_message error: {str(e)}")
        return JsonResponse({'error': 'Failed to process voice message. Please try again.', 'status': 'processing_error'}, status=400)


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
        
        message.is_deleted = 'deleted_for_all' if delete_type == 'for_all' else 'deleted_for_me'
        message.save()
        
        return JsonResponse({'success': True, 'status': message.is_deleted})
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
        
        group_user_session_ids = group.messages.values_list('session_id', flat=True).distinct()
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
            if msg_obj.is_deleted == 'deleted_for_me' and msg_obj.session_id != session_id:
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
                    'is_deleted': msg_obj.is_deleted,
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
        
        if len(content) > 5000:
            return JsonResponse({'error': 'Message too long (max 5000 characters)'}, status=400)
        
        # Process message based on language mode with auto-conversion
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
        
        # Update user and save message
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
