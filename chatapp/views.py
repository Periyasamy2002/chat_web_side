from django.shortcuts import render, redirect
from .models import Group, Message, AnonymousUser
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import timedelta
import uuid
import logging
from .utils.translator import translate_text

logger = logging.getLogger(__name__)

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
        
        if not user_name or not code:
            return render(request, "chat.html", {"error": "Please enter both name and group code"})
        
        request.session['user_name'] = user_name
        request.session['user_id'] = request.session.get('user_id') or str(uuid.uuid4())
        request.session['language'] = language
        
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
                defaults={'user_name': user_name, 'is_online': True, 'last_seen': timezone.now()}
            )
            if not created:
                anon_user.user_name = user_name
                anon_user.is_online = True
                anon_user.last_seen = timezone.now()
                anon_user.save()
            
            group.last_activity = timezone.now()
            group.save(update_fields=['last_activity'])
            logger.info(f"User '{user_name}' joined group '{code}' with language: {language}")
        except Exception as e:
            logger.error(f"Error creating user record: {str(e)}")
        
        request.session['group_code'] = code
        return redirect("group", code=group.code)

    return render(request, "chat.html")


def group(request, code):
    """Group chat view - with automatic deletion checks"""
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
    }
    
    return render(request, "group.html", context)


@require_http_methods(["POST"])
def upload_voice_message(request, code):
    """Handle voice message uploads with activity tracking"""
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
        
        if 'audio' not in request.FILES:
            return JsonResponse({'error': 'No audio file provided'}, status=400)
        
        audio_file = request.FILES['audio']
        duration = float(request.POST.get('duration', 0))
        audio_mime_type = request.POST.get('audio_mime_type', 'audio/webm')
        
        if audio_file.size > 50 * 1024 * 1024:
            return JsonResponse({'error': 'Audio file too large (max 50MB)'}, status=400)
        
        anon_user, _ = AnonymousUser.objects.get_or_create(
            session_id=session_id,
            defaults={'user_name': user_name}
        )
        anon_user.last_seen = timezone.now()
        anon_user.is_online = True
        anon_user.save(update_fields=['last_seen', 'is_online'])
        
        message = Message.objects.create(
            group=group,
            audio_file=audio_file,
            audio_mime_type=audio_mime_type,
            message_type='voice',
            duration=max(duration, 1),
            user_name=user_name,
            session_id=session_id
        )
        
        group.last_activity = timezone.now()
        group.save(update_fields=['last_activity'])
        
        return JsonResponse({
            'success': True,
            'message_id': message.id,
            'audio_url': message.audio_file.url,
            'audio_mime_type': message.audio_mime_type,
            'duration': duration
        })
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Group not found', 'status': 'group_not_found'}, status=404)
    except Exception as e:
        logger.error(f"upload_voice_message error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)


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
    """Get new messages since last timestamp - for live updates with multi-language support"""
    try:
        group = Group.objects.get(code=code)
        session_id = request.session.session_key
        since_timestamp = request.GET.get('since', '')
        user_language = request.session.get('language', 'English')
        
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
                display_content, translation_source = get_message_by_user_language(msg_obj, user_language)
                
                message_obj = {
                    'id': msg_obj.id,
                    'user_name': msg_obj.user_name,
                    'content': display_content,
                    'original_content': msg_obj.content,
                    'message_type': msg_obj.message_type,
                    'timestamp': msg_obj.timestamp.isoformat(),
                    'is_sender': msg_obj.session_id == session_id,
                    'is_deleted': msg_obj.is_deleted,
                    'translation_source': translation_source,
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
            'timestamp': timezone.now().isoformat()
        })
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Group not found', 'success': False, 'status': 'group_not_found'}, status=404)
    except Exception as e:
        logger.error(f"get_new_messages error: {str(e)}")
        return JsonResponse({'error': str(e), 'success': False}, status=500)


@require_http_methods(["POST"])
def send_message_ajax(request, code):
    """Send text message via AJAX - for live updates with activity tracking"""
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
        
        if not content:
            return JsonResponse({'error': 'Message cannot be empty'}, status=400)
        
        if len(content) > 5000:
            return JsonResponse({'error': 'Message too long (max 5000 characters)'}, status=400)
        
        anon_user, created = AnonymousUser.objects.get_or_create(
            session_id=session_id,
            defaults={'user_name': user_name}
        )
        anon_user.last_seen = timezone.now()
        anon_user.is_online = True
        anon_user.save(update_fields=['last_seen', 'is_online'])
        
        message = Message.objects.create(
            group=group,
            content=content,
            message_type='text',
            user_name=user_name,
            session_id=session_id
        )
        
        group.last_activity = timezone.now()
        group.save(update_fields=['last_activity'])
        
        try:
            user_language = request.session.get('language', 'English').strip()
            if user_language and user_language.lower() != 'english':
                success, translated_text, msg = translate_text(content, user_language)
                if success and translated_text:
                    message.translated_content = translated_text
                    message.translated_language = user_language
                    message.save(update_fields=['translated_content', 'translated_language'])
        except Exception as e:
            logger.error(f"Translation error (non-blocking): {str(e)}")
        
        return JsonResponse({
            'success': True,
            'message': {
                'id': message.id,
                'user_name': message.user_name,
                'content': message.content,
                'translated_content': message.translated_content,
                'timestamp': message.timestamp.isoformat(),
                'is_sender': True,
                'is_deleted': message.is_deleted
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
        
        success, translated_text, message = translate_text(text, target_language)
        
        if not success:
            return JsonResponse({
                'success': False,
                'error': message,
                'translated': text
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
