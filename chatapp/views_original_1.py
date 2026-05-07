from django.shortcuts import render, redirect
from .models import Group, Message, AnonymousUser
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import timedelta
import uuid
import logging
from .utils.translator import translate_text, normalize_to_professional_english, get_message_for_sender, get_message_for_receiver
from .utils.tamil_detector import is_valid_english_only, get_language_violation_details, contains_tamil_script

logger = logging.getLogger(__name__)

def ensure_us_english(text):
    """
    Standardize text to US English format only.
    Converts common British English to US English.
    """
    if not text:
        return text
    
    # British → US English conversions (both lowercase and capitalized)
    us_english_map = {
        # Common British spellings to US English (with word boundaries)
        'colour': 'color',
        'Colour': 'Color',
        'favour': 'favor',
        'Favour': 'Favor',
        'honour': 'honor',
        'Honour': 'Honor',
        'labour': 'labor',
        'Labour': 'Labor',
        'harbour': 'harbor',
        'Harbour': 'Harbor',
        'centre': 'center',
        'Centre': 'Center',
        'metre': 'meter',
        'Metre': 'Meter',
        'theatre': 'theater',
        'Theatre': 'Theater',
        'travelling': 'traveling',
        'Travelling': 'Traveling',
        'realise': 'realize',
        'Realise': 'Realize',
        'organise': 'organize',
        'Organise': 'Organize',
        'recognise': 'recognize',
        'Recognise': 'Recognize',
        'apologise': 'apologize',
        'Apologise': 'Apologize',
        'analyse': 'analyze',
        'Analyse': 'Analyze',
        'licence': 'license',
        'Licence': 'License',
        'defence': 'defense',
        'Defence': 'Defense',
        'offence': 'offense',
        'Offence': 'Offense',
        'grey': 'gray',
        'Grey': 'Gray',
        'cheque': 'check',
        'Cheque': 'Check',
        'gaol': 'jail',
        'Gaol': 'Jail',
        'kerb': 'curb',
        'Kerb': 'Curb',
        'programme': 'program',
        'Programme': 'Program',
    }
    
    result = text
    for british, american in us_english_map.items():
        result = result.replace(british, american)
    
    return result


def check_and_cleanup_group(group):
    """Check if group should be deleted and perform deletion if needed."""
    if not group:
        return False, "group_not_found"
    
    try:
        should_delete, reason = group.should_auto_delete()
        
        if should_delete:
            online_count = group.get_group_online_count()
            if online_count == 0:
                group.delete()
                return True, reason
        
        return False, reason
    except Exception as e:
        logger.error(f"check_and_cleanup_group error: {str(e)}")
        return False, "error"


def update_user_online_status(session_id, user_name, is_online=True):
    """Update or create user's online status"""
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
    """Mark users as offline if inactive for 5+ minutes"""
    try:
        five_min_ago = timezone.now() - timedelta(minutes=5)
        inactive = AnonymousUser.objects.filter(
            is_online=True,
            last_seen__lt=five_min_ago
        )
        
        for user in inactive:
            user.is_online = False
            user.save(update_fields=['is_online'])
        
        return inactive.count()
    except Exception as e:
        logger.error(f"auto_offline_inactive_users error: {str(e)}")
        return 0


def home(request):
    """Home page - entry point of the app"""
    return render(request, "home.html")


def chat(request):
    """Chat page - user enters their name and group code"""
    if request.method == "POST":
        user_name = request.POST.get("user_name", "").strip()
        code = request.POST.get("code", "").strip()
        language = request.POST.get("language", "English").strip()
        language_mode = request.POST.get("language_mode", "english").strip().lower()  # NEW: language mode
        
        if not user_name or not code:
            return render(request, "chat.html", {"error": "Please enter both name and group code"})
        
        # CRITICAL: Validate username is English only - NO TAMIL OR TANGLISH
        is_valid_name, name_error = is_valid_english_only(user_name)
        if not is_valid_name:
            logger.warning(f"NON-ENGLISH username rejected: {user_name}")
            return render(request, "chat.html", {
                "error": "Username must be in English only. Tamil script and Tanglish are not allowed. Please use English letters and numbers only."
            })
        
        # Validate language_mode is one of the allowed values
        if language_mode not in ['english', 'tamil']:
            language_mode = 'english'
        
        request.session['user_name'] = user_name
        request.session['user_id'] = request.session.get('user_id') or str(uuid.uuid4())
        request.session['language'] = language
        request.session['language_mode'] = language_mode  # NEW: Store mode in session
        request.session.save()  # FORCE save session to ensure data persists
        
        # DEBUG: Verify session was saved
        print(f"[DEBUG REGISTRATION] Form data - language_mode: {repr(language_mode)}")
        print(f"[DEBUG REGISTRATION] Session after save - language_mode: {repr(request.session.get('language_mode'))}")
        print(f"[DEBUG REGISTRATION] Session ID: {request.session.session_key}")
        
        group, created = Group.objects.get_or_create(code=code, defaults={"name": code})
        
        try:
            group.last_activity = timezone.now()
            group.save(update_fields=['last_activity'])
        except Exception as e:
            if 'last_activity' not in str(e):
                raise
        
        try:
            anon_user, created = AnonymousUser.objects.get_or_create(
                session_id=request.session.session_key,
                defaults={
                    'user_name': user_name,
                    'is_online': True,
                    'last_seen': timezone.now(),
                    'language_mode': language_mode  # NEW: Store mode in database
                }
            )
            if not created:
                anon_user.user_name = user_name
                anon_user.is_online = True
                anon_user.last_seen = timezone.now()
                anon_user.language_mode = language_mode  # NEW: Update mode
                anon_user.save()
            
            group.last_activity = timezone.now()
            group.save(update_fields=['last_activity'])
            logger.info(f"User '{user_name}' joined group '{code}' with language: {language}, mode: {language_mode}")
        except Exception as e:
            logger.error(f"Error creating user record: {str(e)}")
        
        request.session['group_code'] = code
        return redirect("group", code=group.code)

    return render(request, "chat.html")


def group(request, code):
    """Group chat view - with automatic deletion checks and language mode support"""
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
    user_language_mode = request.session.get('language_mode', 'english').lower()  # NEW: Get language mode
    
    messages_list = Message.objects.filter(group=group).order_by('timestamp')
    
    online_users = AnonymousUser.objects.filter(
        last_seen__gte=timezone.now() - timezone.timedelta(minutes=5)
    ).distinct()
    
    last_message = messages_list.order_by('-timestamp').first()
    last_message_timestamp = last_message.timestamp.isoformat() if last_message else timezone.now().isoformat()
    
    context = {
        "group": group,
        "messages": messages_list,
        "user_name": user_name,
        "online_count": online_users.count(),
        "last_message_timestamp": last_message_timestamp,
        "language": user_language,
        "language_name": user_language,
        "language_mode": user_language_mode,  # NEW: Pass mode to template
    }
    
    return render(request, "group.html", context)


@require_http_methods(["POST"])
def upload_voice_message(request, code):
    """Handle voice message uploads with activity tracking and normalization"""
    try:
        group = Group.objects.get(code=code)
        
        should_delete, delete_reason = check_and_cleanup_group(group)
        if should_delete:
            return JsonResponse({
                'error': 'Group deleted',
                'status': 'group_deleted',
                'reason': delete_reason
            }, status=410)
        
        user_name = request.session.get('user_name', 'Anonymous')
        user_language = request.session.get('language', 'English').strip()
        session_id = request.session.session_key
        
        # Validate audio file was provided
        if 'audio' not in request.FILES:
            logger.warning(f"Voice message upload attempted without audio file by {user_name}")
            return JsonResponse({
                'error': 'Voice input not detected. Please try again.',
                'status': 'no_audio_detected'
            }, status=400)
        
        audio_file = request.FILES['audio']
        duration = float(request.POST.get('duration', 0))
        audio_mime_type = request.POST.get('audio_mime_type', 'audio/webm')
        
        # Validate audio file size
        if audio_file.size == 0:
            logger.warning(f"Empty audio file uploaded by {user_name}")
            return JsonResponse({
                'error': 'Voice input not detected. Please try again.',
                'status': 'empty_audio_file'
            }, status=400)
        
        if audio_file.size > 50 * 1024 * 1024:
            logger.warning(f"Audio file too large ({audio_file.size} bytes) from {user_name}")
            return JsonResponse({
                'error': 'Audio file too large (max 50MB)',
                'status': 'audio_too_large'
            }, status=400)
        
        # Validate duration - must be at least 0.5 seconds
        if duration < 0.5:
            logger.warning(f"Voice message duration too short ({duration}s) from {user_name}")
            return JsonResponse({
                'error': 'Voice input not detected. Please try again.',
                'status': 'voice_too_short'
            }, status=400)
        
        # Check if there's a voice message transcription/description
        voice_text = request.POST.get('text', '').strip()
        
        # CRITICAL: Validate voice transcription text if provided - ENGLISH ONLY
        if voice_text:
            is_valid_voice, voice_error_msg = is_valid_english_only(voice_text)
            if not is_valid_voice:
                violations = get_language_violation_details(voice_text)
                logger.warning(f"NON-ENGLISH voice message text rejected from {user_name}: {violations}")
                return JsonResponse({
                    'error': voice_error_msg or 'Voice message text must be in English only. Tamil script and Tanglish are not allowed.',
                    'status': 'language_violation_speech',
                    'details': violations
                }, status=400)
        
        anon_user, _ = AnonymousUser.objects.get_or_create(
            session_id=session_id,
            defaults={'user_name': user_name}
        )
        anon_user.last_seen = timezone.now()
        anon_user.is_online = True
        anon_user.save(update_fields=['last_seen', 'is_online'])
        
        # Normalize voice text if provided
        normalized_text = voice_text
        tamil_text = voice_text
        if voice_text:
            norm_success, normalized_text, _ = normalize_to_professional_english(voice_text, user_language)
            normalized_text = normalized_text if norm_success else voice_text
            
            # Ensure US English format
            normalized_text = ensure_us_english(normalized_text)
            
            # Translate to Tamil
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
            content=voice_text if voice_text else None,  # Original transcription if provided
            normalized_content=normalized_text if voice_text else None,  # Normalized transcription (US English)
            english_content=normalized_text if voice_text else None,  # Professional English version (US English)
            tamil_content=tamil_text if voice_text else None,  # Tamil version
            message_type='voice',
            duration=max(duration, 1),
            user_name=user_name,
            session_id=session_id
        )
        
        # If there's transcribed text and user's language is Tamil, cache the translation
        if voice_text and user_language.lower() == 'tamil':
            try:
                message.translated_content = tamil_text
                message.translated_language = 'Tamil'
                message.save(update_fields=['translated_content', 'translated_language'])
            except Exception as e:
                logger.error(f"Error caching translation: {str(e)}")
        
        group.last_activity = timezone.now()
        group.save(update_fields=['last_activity'])
        
        logger.info(f"Voice message created: {message.id} by {user_name}, duration: {duration}s")
        
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
    """Delete a message for me or for everyone"""
    try:
        group = Group.objects.get(code=code)
        
        should_delete, delete_reason = check_and_cleanup_group(group)
        if should_delete:
            return JsonResponse({
                'error': 'Group deleted',
                'status': 'group_deleted',
                'reason': delete_reason
            }, status=410)
        
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
        elif delete_type == 'for_me':
            message.is_deleted = 'deleted_for_me'
        
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
    """Update user online/offline status with auto-timeout detection"""
    try:
        group = Group.objects.get(code=code)
        
        should_delete, delete_reason = check_and_cleanup_group(group)
        if should_delete:
            return JsonResponse({
                'error': 'Group deleted',
                'status': 'group_deleted',
                'reason': delete_reason
            }, status=410)
        
        user_name = request.session.get('user_name', 'Anonymous')
        session_id = request.session.session_key
        is_online = request.POST.get('is_online', 'false').lower() == 'true'
        
        anon_user, _ = AnonymousUser.objects.get_or_create(
            session_id=session_id,
            defaults={'user_name': user_name}
        )
        anon_user.is_online = is_online
        anon_user.last_seen = timezone.now()
        anon_user.save(update_fields=['is_online', 'last_seen'])
        
        group.last_activity = timezone.now()
        group.save(update_fields=['last_activity'])
        
        auto_offline_inactive_users()
        
        online_count = group.get_group_online_count()
        
        return JsonResponse({
            'success': True,
            'is_online': anon_user.is_online,
            'online_count': online_count
        })
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Group not found', 'status': 'group_not_found'}, status=404)
    except Exception as e:
        logger.error(f"update_user_status error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["GET"])
def get_online_users(request, code):
    """Get list of online users in the group"""
    try:
        group = Group.objects.get(code=code)
        
        should_delete, delete_reason = check_and_cleanup_group(group)
        if should_delete:
            return JsonResponse({
                'error': 'Group deleted',
                'status': 'group_deleted',
                'reason': delete_reason
            }, status=410)
        
        online_count = group.get_group_online_count()
        group_user_session_ids = group.messages.values_list('session_id', flat=True).distinct()
        
        online_users = AnonymousUser.objects.filter(
            session_id__in=group_user_session_ids,
            is_online=True,
            last_seen__gte=timezone.now() - timezone.timedelta(minutes=5)
        ).values_list('user_name', 'id', 'session_id').distinct()
        
        users_list = [
            {
                'id': user[1],
                'session_id': user[2],
                'display_name': user[0] or 'Anonymous'
            }
            for user in online_users
        ]
        
        return JsonResponse({
            'success': True,
            'users': users_list,
            'count': len(users_list)
        })
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Group not found', 'status': 'group_not_found'}, status=404)
    except Exception as e:
        logger.error(f"get_online_users error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)


def get_message_by_user_language(message, user_language):
    """Get message content based on user's language preference"""
    try:
        if not user_language or user_language.lower() == 'english':
            return message.content, 'original'
        
        if (message.translated_content and 
            message.translated_language and 
            message.translated_language.lower() == user_language.lower()):
            return message.translated_content, 'cached'
        
        if message.message_type == 'text' and message.content:
            success, translated_text, msg_text = translate_text(message.content, user_language)
            if success and translated_text:
                return translated_text, 'translated'
        
        return message.content, 'original'
    except Exception as e:
        logger.error(f"get_message_by_user_language error: {str(e)}")
        return message.content, 'original'


@require_http_methods(["GET"])
def get_new_messages(request, code):
    """Get new messages since last timestamp - Returns both Tamil and English versions, displays based on user mode"""
    try:
        group = Group.objects.get(code=code)
        session_id = request.session.session_key
        since_timestamp = request.GET.get('since', '')
        user_language = request.session.get('language', 'English')
        user_language_mode = request.session.get('language_mode', 'english').lower()  # NEW: Get user's mode
        
        should_delete, delete_reason = check_and_cleanup_group(group)
        if should_delete:
            return JsonResponse({
                'error': 'Group deleted',
                'status': 'group_deleted',
                'reason': delete_reason
            }, status=410)
        
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
                is_sender = msg_obj.session_id == session_id
                
                # Get both Tamil and English versions
                tamil_version = msg_obj.tamil_content or msg_obj.translated_content
                english_version = msg_obj.english_content or msg_obj.normalized_content or msg_obj.content
                
                # Ensure English version is always in US English format
                english_version = ensure_us_english(english_version)
                
                # ============= DETERMINE DISPLAY CONTENT BASED ON USER MODE =============
                if user_language_mode == 'tamil':
                    # Tamil Mode: Always display Tamil only
                    display_content = tamil_version if tamil_version else english_version
                else:
                    # English Mode: Always display English only
                    display_content = english_version if english_version else tamil_version
                
                message_obj = {
                    'id': msg_obj.id,
                    'user_name': msg_obj.user_name,
                    'content': display_content,           # What the current user sees (based on their mode)
                    'tamil': tamil_version,               # Tamil version (always included for reference)
                    'english': english_version,           # English version (always included for reference)
                    'original_content': msg_obj.content,  # Original user input
                    'message_type': msg_obj.message_type,
                    'timestamp': msg_obj.timestamp.isoformat(),
                    'is_sender': is_sender,
                    'is_deleted': msg_obj.is_deleted,
                    'language_mode': user_language_mode,  # Include mode for frontend awareness
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
            'language_mode': user_language_mode  # Include mode in response
        })
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Group not found', 'success': False, 'status': 'group_not_found'}, status=404)
    except Exception as e:
        logger.error(f"get_new_messages error: {str(e)}")
        return JsonResponse({'error': str(e), 'success': False}, status=500)


@require_http_methods(["POST"])
def send_message_ajax(request, code):
    """Send text message via AJAX with dual-mode language support
    
    English Mode: Only accept English, reject Tamil/Tanglish
    Tamil Mode: Accept Tamil/English input, convert to Tamil for display
    """
    try:
        group = Group.objects.get(code=code)
        
        should_delete, delete_reason = check_and_cleanup_group(group)
        if should_delete:
            return JsonResponse({
                'error': 'Group deleted',
                'status': 'group_deleted',
                'reason': delete_reason
            }, status=410)
        
        user_name = request.session.get('user_name', 'Anonymous')
        session_id = request.session.session_key
        content = request.POST.get('message', '').strip()
        user_language = request.session.get('language', 'English').strip()
        
        # Get language_mode from session - with EXTENSIVE DEBUGGING
        user_language_mode = request.session.get('language_mode', 'english')
        
        # Print ALL session data for debugging
        print(f"\n[DEBUG SESSION] All session data:")
        for key, value in request.session.items():
            print(f"  {key}: {repr(value)}")
        
        # FALLBACK: Try to get from database if session is empty
        if not user_language_mode or user_language_mode == 'english':
            print(f"[DEBUG] Session language_mode was: {repr(user_language_mode)}")
            try:
                anon_user = AnonymousUser.objects.filter(session_id=session_id).first()
                if anon_user:
                    print(f"[DEBUG] Found AnonymousUser in DB with language_mode: {repr(anon_user.language_mode)}")
                    if anon_user.language_mode and anon_user.language_mode != 'english':
                        user_language_mode = anon_user.language_mode
                        print(f"[DEBUG] Using DB value instead: {repr(user_language_mode)}")
            except Exception as e:
                print(f"[DEBUG] DB fallback error: {str(e)}")
        
        # Ensure language_mode is lowercase and valid
        if isinstance(user_language_mode, str):
            user_language_mode = user_language_mode.strip().lower()
        else:
            user_language_mode = str(user_language_mode).lower()
            
        if user_language_mode not in ['english', 'tamil']:
            print(f"[WARNING] Invalid language_mode: {repr(user_language_mode)}, defaulting to 'english'")
            user_language_mode = 'english'
        
        print(f"[DEBUG] send_message_ajax - user_name: {user_name}")
        print(f"[DEBUG] send_message_ajax - session_id: {session_id}")
        print(f"[DEBUG] send_message_ajax - language_mode: {repr(user_language_mode)} (type: {type(user_language_mode)})")
        print(f"[DEBUG] send_message_ajax - content length: {len(content)} chars")
        print(f"[DEBUG] send_message_ajax - Condition check: user_language_mode == 'english' -> {user_language_mode == 'english'}")
        print(f"[DEBUG] send_message_ajax - Condition check: user_language_mode == 'tamil' -> {user_language_mode == 'tamil'}")
        
        if not content:
            return JsonResponse({'error': 'Message cannot be empty'}, status=400)
        
        if len(content) > 5000:
            return JsonResponse({'error': 'Message too long (max 5000 characters)'}, status=400)
        
        english_version = content
        tamil_version = content
        display_content = content
        
        # ============= ENGLISH MODE =============
        if user_language_mode == 'english':
            print(f"[DEBUG] ENGLISH MODE - validating message")  # DEBUG (don't print content)
            # CRITICAL: Validate that message is STRICTLY English only - NO TAMIL OR TANGLISH ALLOWED
            is_valid, error_msg = is_valid_english_only(content)
            if not is_valid:
                violations = get_language_violation_details(content)
                logger.warning(f"NON-ENGLISH message rejected from {user_name} (ENGLISH MODE): {violations}")
                print(f"[DEBUG] ENGLISH MODE - VALIDATION FAILED")  # DEBUG
                return JsonResponse({
                    'error': error_msg or 'Messages must be in English only. Tamil script, Tamil language, and Tanglish are not allowed.',
                    'status': 'language_violation',
                    'details': violations
                }, status=400)
            
            # Normalize and convert to US English
            norm_success, normalized_content, norm_msg = normalize_to_professional_english(content, 'English')
            english_version = normalized_content if norm_success else content
            english_version = ensure_us_english(english_version)
            
            # Translate to Tamil for full bilingual storage
            try:
                tamil_success, tamil_version, _ = translate_text(english_version, 'Tamil')
                if not tamil_success or not tamil_version:
                    tamil_version = english_version
            except Exception as e:
                logger.warning(f"Failed to translate to Tamil: {str(e)}")
                tamil_version = english_version
            
            # In English mode, display English only
            display_content = ensure_us_english(english_version)
            print(f"[DEBUG] ENGLISH MODE - ACCEPTED")  # DEBUG
        
        # ============= TAMIL MODE =============
        elif user_language_mode == 'tamil':
            print(f"[DEBUG] TAMIL MODE - ACCEPTING ALL INPUT (not validating like English mode)")  # DEBUG
            # In Tamil mode, accept both Tamil and English
            # If Tamil script detected, it's fine - just use it
            # If English, convert to Tamil for display
            
            is_tamil = contains_tamil_script(content)
            print(f"[DEBUG] TAMIL MODE - has Tamil script: {is_tamil}")  # DEBUG
            
            if is_tamil:
                # User typed in Tamil script - keep as is
                tamil_version = content
                print(f"[DEBUG] TAMIL MODE - Tamil input detected")  # DEBUG
                
                # Try to extract English meaning
                try:
                    # Translate Tamil to English for internal storage
                    eng_success, english_extracted, _ = translate_text(content, 'English')
                    if eng_success and english_extracted:
                        english_version = english_extracted
                    else:
                        english_version = content  # Fallback
                except Exception as e:
                    logger.warning(f"Failed to translate Tamil to English: {str(e)}")
                    english_version = content
            else:
                # User typed in English (or Tanglish) - convert to Tamil for display
                print(f"[DEBUG] TAMIL MODE - Non-Tamil input detected, converting to Tamil")  # DEBUG
                # First, try to normalize to professional English
                norm_success, normalized_content, norm_msg = normalize_to_professional_english(content, 'English')
                english_version = normalized_content if norm_success else content
                english_version = ensure_us_english(english_version)
                
                # Translate English to Tamil for display
                try:
                    tamil_success, tamil_translated, _ = translate_text(english_version, 'Tamil')
                    if tamil_success and tamil_translated:
                        tamil_version = tamil_translated
                    else:
                        tamil_version = english_version  # Fallback
                except Exception as e:
                    logger.warning(f"Failed to translate to Tamil: {str(e)}")
                    tamil_version = english_version
            
            # In Tamil mode, always display Tamil only
            display_content = tamil_version
            print(f"[DEBUG] TAMIL MODE - ACCEPTED")  # DEBUG
        
        else:
            # FALLBACK: Should not reach here, but if we do default to English mode
            print(f"[ERROR] UNKNOWN language_mode: {repr(user_language_mode)} - defaulting to English mode")  # DEBUG
            is_valid, error_msg = is_valid_english_only(content)
            if not is_valid:
                violations = get_language_violation_details(content)
                logger.warning(f"NON-ENGLISH message in fallback mode: {violations}")
                return JsonResponse({
                    'error': error_msg or 'Messages must be in English only.',
                    'status': 'language_violation',
                    'details': violations
                }, status=400)
            print(f"[DEBUG] TAMIL MODE - ACCEPTED, displaying: {display_content}")  # DEBUG
        
        # Update user status
        anon_user, created = AnonymousUser.objects.get_or_create(
            session_id=session_id,
            defaults={'user_name': user_name}
        )
        anon_user.last_seen = timezone.now()
        anon_user.is_online = True
        anon_user.save(update_fields=['last_seen', 'is_online'])
        
        # Store message with BOTH Tamil and English versions
        message = Message.objects.create(
            group=group,
            content=content,                    # Original user input
            normalized_content=english_version, # English version
            english_content=english_version,    # English version (explicit)
            tamil_content=tamil_version,        # Tamil version (explicit)
            message_type='text',
            user_name=user_name,
            session_id=session_id
        )
        
        # Cache translation metadata
        message.translated_content = display_content
        message.translated_language = 'Tamil' if user_language_mode == 'tamil' else 'English'
        message.save(update_fields=['translated_content', 'translated_language'])
        
        group.last_activity = timezone.now()
        group.save(update_fields=['last_activity'])
        
        logger.info(f"Message sent by {user_name} ({user_language_mode} mode): OK")
        
        return JsonResponse({
            'success': True,
            'message': {
                'id': message.id,
                'user_name': message.user_name,
                'content': display_content,                    # What this user sees (based on their mode)
                'tamil': tamil_version,                        # Full Tamil version
                'english': english_version,                    # Full English version
                'timestamp': message.timestamp.isoformat(),
                'is_sender': True,
                'is_deleted': message.is_deleted,
                'language_mode': user_language_mode            # Send mode info to frontend
            }
        })
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Group not found', 'status': 'group_not_found'}, status=404)
    except Exception as e:
        logger.error(f"send_message_ajax error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["GET"])
def get_group_cleanup_status(request, code):
    """Get deletion status and reason for a specific group"""
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
    """Get cleanup status for all groups"""
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
        
        return JsonResponse({
            'success': True,
            'total_groups': len(statuses),
            'groups': statuses
        })
    except Exception as e:
        logger.error(f"get_all_groups_status error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["POST"])
def translate_message(request, code):
    """Translate a message to user's selected language using Gemini API"""
    try:
        group = Group.objects.get(code=code)
        
        should_delete, delete_reason = check_and_cleanup_group(group)
        if should_delete:
            return JsonResponse({
                'error': 'Group deleted',
                'status': 'group_deleted',
                'reason': delete_reason
            }, status=410)
        
        text = request.POST.get('text', '').strip()
        target_language = request.POST.get('language', 'English').strip()
        
        if not text:
            return JsonResponse({'error': 'No text provided'}, status=400)
        
        if not target_language:
            return JsonResponse({'error': 'No target language specified'}, status=400)
        
        # First normalize the text to professional English
        norm_success, normalized_text, _ = normalize_to_professional_english(text)
        text_to_translate = normalized_text if norm_success else text
        
        # Then translate to target language
        success, translated_text, message = translate_text(text_to_translate, target_language)
        
        if not success:
            return JsonResponse({
                'success': False,
                'error': message,
                'translated': text_to_translate
            }, status=400)
        
        return JsonResponse({
            'success': True,
            'translated': translated_text,
            'target_language': target_language,
            'message': message
        })
        
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Group not found', 'status': 'group_not_found'}, status=404)
    except Exception as e:
        logger.error(f"translate_message error: {str(e)}")
        return JsonResponse({'error': f'Translation error: {str(e)}'}, status=400)
