from django.shortcuts import render, redirect
from .models import Group, Message, AnonymousUser
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import timedelta
import json
import uuid
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# HELPER FUNCTIONS FOR AUTO-DELETION (CONSOLIDATED)
# ============================================================================

def check_and_cleanup_group(group):
    """
    Check if group should be deleted and perform deletion if needed.
    Returns: (should_delete: bool, reason: str)
    """
    if not group:
        return False, "group_not_found"
    
    try:
        should_delete, reason = group.should_auto_delete()
        
        if should_delete:
            # Double-check online count before deletion
            online_count = group.get_group_online_count()
            print(f"[CLEANUP] Group {group.code}: Final check - {online_count} online users")
            
            if online_count == 0:
                print(f"[DELETE] Group {group.code}: DELETING - Reason: {reason}")
                group_code = group.code
                group.delete()
                return True, reason
        
        return False, reason
    
    except Exception as e:
        print(f"[ERROR] check_and_cleanup_group: {str(e)}")
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
        print(f"[USER] {user_name}: marked {'ONLINE' if is_online else 'OFFLINE'}")
        return True
    except Exception as e:
        print(f"[ERROR] update_user_online_status: {str(e)}")
        return False


def auto_offline_inactive_users():
    """Mark users as offline if inactive for 5+ minutes"""
    try:
        thirty_min_ago = timezone.now() - timedelta(minutes=5)
        inactive = AnonymousUser.objects.filter(
            is_online=True,
            last_seen__lt=thirty_min_ago
        )
        
        for user in inactive:
            user.is_online = False
            user.save(update_fields=['is_online'])
            print(f"[AUTO-OFFLINE] User {user.user_name}: marked offline (inactive {(timezone.now() - user.last_seen).total_seconds() / 60:.0f} min)")
        
        return inactive.count()
    
    except Exception as e:
        print(f"[ERROR] auto_offline_inactive_users: {str(e)}")
        return 0

def home(request):
    """Home page - entry point of the app"""
    return render(request, "home.html")

def chat(request):
    """Chat page - user enters their name and group code"""
    
    if request.method == "POST":
        user_name = request.POST.get("user_name", "").strip()
        code = request.POST.get("code", "").strip()
        
        if not user_name or not code:
            return render(request, "chat.html", {"error": "Please enter both name and group code"})
        
        # Store user name in session
        request.session['user_name'] = user_name
        request.session['user_id'] = request.session.get('user_id') or str(uuid.uuid4())
        
        # Get or create group
        group, created = Group.objects.get_or_create(code=code, defaults={"name": code})
        
        # Update last activity if field exists (after migration)
        try:
            group.last_activity = timezone.now()
            group.save(update_fields=['last_activity'])
        except Exception as e:
            # If migration hasn't been applied yet, skip this
            if 'last_activity' not in str(e):
                raise
            logger.info(f"Note: last_activity field not yet available. Run: python manage.py migrate")
        
        # Create or update anonymous user record and mark online
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
            
            logger.info(f"✓ User '{user_name}' joined group '{code}'")
            
            # Update group last_activity on user join
            group.last_activity = timezone.now()
            group.save(update_fields=['last_activity'])
        
        except Exception as e:
            logger.error(f"Error creating user record: {str(e)}")
        
        # Add group code to session
        request.session['group_code'] = code
        
        return redirect("group", code=group.code)

    return render(request, "chat.html")

def group(request, code):
    """Group chat view - with automatic deletion checks"""
    try:
        group = Group.objects.get(code=code)
    except Group.DoesNotExist:
        return redirect('chat')
    
    # AUTO-DELETE: Check if group should be deleted
    should_delete, reason = check_and_cleanup_group(group)
    if should_delete:
        return render(request, "chat.html", {
            "info": f"Group was deleted due to inactivity ({reason}). Please create a new one!"
        })
    
    # Get user name from session
    user_name = request.session.get('user_name', 'Anonymous')
    session_id = request.session.session_key
    
    # Get all messages
    messages_list = Message.objects.filter(group=group).order_by('timestamp')
    
    # Get online users in this group
    online_users = AnonymousUser.objects.filter(
        last_seen__gte=timezone.now() - timezone.timedelta(minutes=5)
    ).distinct()
    
    # Get last message timestamp for live updates
    last_message = messages_list.order_by('-timestamp').first()
    last_message_timestamp = last_message.timestamp.isoformat() if last_message else timezone.now().isoformat()
    
    context = {
        "group": group,
        "messages": messages_list,
        "user_name": user_name,
        "online_count": online_users.count(),
        "last_message_timestamp": last_message_timestamp,
    }
    
    return render(request, "group.html", context)

@require_http_methods(["POST"])
def upload_voice_message(request, code):
    """Handle voice message uploads with activity tracking"""
    try:
        group = Group.objects.get(code=code)
        
        # AUTO-DELETE CHECK: Before processing voice message
        should_delete, delete_reason = check_and_cleanup_group(group)
        if should_delete:
            print(f"[VOICE_MESSAGE] Group {code} deleted - returning 410 Gone")
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
        
        # Validate file size (max 50MB)
        if audio_file.size > 50 * 1024 * 1024:
            return JsonResponse({'error': 'Audio file too large (max 50MB)'}, status=400)
        
        # Create or update anonymous user
        anon_user, _ = AnonymousUser.objects.get_or_create(
            session_id=session_id,
            defaults={'user_name': user_name}
        )
        anon_user.last_seen = timezone.now()
        anon_user.is_online = True
        anon_user.save(update_fields=['last_seen', 'is_online'])
        
        # Create voice message
        message = Message.objects.create(
            group=group,
            audio_file=audio_file,
            audio_mime_type=audio_mime_type,
            message_type='voice',
            duration=max(duration, 1),
            user_name=user_name,
            session_id=session_id
        )
        
        # Update group last activity
        group.last_activity = timezone.now()
        group.save(update_fields=['last_activity'])
        
        print(f"[VOICE] {user_name} uploaded voice message in group {group.code} (duration: {duration}s)")
        
        return JsonResponse({
            'success': True,
            'message_id': message.id,
            'audio_url': message.audio_file.url,
            'audio_mime_type': message.audio_mime_type,
            'duration': duration
        })
    except Group.DoesNotExist:
        print(f"[VOICE_MESSAGE] Group {code} not found")
        return JsonResponse({'error': 'Group not found', 'status': 'group_not_found'}, status=404)
    except Exception as e:
        print(f"[ERROR] upload_voice_message: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)

@require_http_methods(["POST"])
def delete_message(request, code):
    """Delete a message for me or for everyone"""
    try:
        group = Group.objects.get(code=code)
        
        # AUTO-DELETE CHECK: Before processing message deletion
        should_delete, delete_reason = check_and_cleanup_group(group)
        if should_delete:
            print(f"[DELETE_MESSAGE] Group {code} deleted - returning 410 Gone")
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
        
        # Only sender (same session) can delete for everyone
        if delete_type == 'for_all' and message.session_id != session_id:
            return JsonResponse({'error': 'Only sender can delete for everyone'}, status=403)
        
        if delete_type == 'for_all':
            message.is_deleted = 'deleted_for_all'
            message.save()
        elif delete_type == 'for_me':
            message.is_deleted = 'deleted_for_me'
            message.save()
        
        print(f"[DELETE_MSG] Message {message_id} marked {delete_type} in group {code}")
        
        return JsonResponse({'success': True, 'status': message.is_deleted})
    except Group.DoesNotExist:
        print(f"[DELETE_MESSAGE] Group {code} not found")
        return JsonResponse({'error': 'Group not found', 'status': 'group_not_found'}, status=404)
    except Message.DoesNotExist:
        return JsonResponse({'error': 'Message not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_http_methods(["POST"])
@require_http_methods(["POST"])
def update_user_status(request, code):
    """Update user online/offline status with auto-timeout detection"""
    try:
        group = Group.objects.get(code=code)
        
        # AUTO-DELETE CHECK: Before processing status update
        should_delete, delete_reason = check_and_cleanup_group(group)
        if should_delete:
            print(f"[UPDATE_STATUS] Group {code} deleted - returning 410 Gone")
            return JsonResponse({
                'error': 'Group deleted',
                'status': 'group_deleted',
                'reason': delete_reason
            }, status=410)
        
        user_name = request.session.get('user_name', 'Anonymous')
        session_id = request.session.session_key
        is_online = request.POST.get('is_online', 'false').lower() == 'true'
        
        # Update or create anonymous user record
        anon_user, _ = AnonymousUser.objects.get_or_create(
            session_id=session_id,
            defaults={'user_name': user_name}
        )
        anon_user.is_online = is_online
        anon_user.last_seen = timezone.now()
        anon_user.save(update_fields=['is_online', 'last_seen'])
        
        # Update group last activity timestamp
        group.last_activity = timezone.now()
        group.save(update_fields=['last_activity'])
        
        # Auto-mark users offline if inactive for 30 minutes
        auto_offline_inactive_users()
        
        # Get updated online count for this group
        online_count = group.get_group_online_count()
        
        print(f"[STATUS] {user_name}: {'ONLINE' if is_online else 'OFFLINE'} in group {group.code}")
        
        return JsonResponse({
            'success': True,
            'is_online': anon_user.is_online,
            'online_count': online_count
        })
    except Group.DoesNotExist:
        print(f"[UPDATE_STATUS] Group {code} not found")
        return JsonResponse({'error': 'Group not found', 'status': 'group_not_found'}, status=404)
    except Exception as e:
        print(f"[ERROR] update_user_status: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)

@require_http_methods(["GET"])
@require_http_methods(["GET"])
def get_online_users(request, code):
    """Get list of online users in the group"""
    try:
        group = Group.objects.get(code=code)
        
        # AUTO-DELETE CHECK: Before returning online users
        should_delete, delete_reason = check_and_cleanup_group(group)
        if should_delete:
            print(f"[ONLINE_USERS] Group {code} deleted - returning 410 Gone")
            return JsonResponse({
                'error': 'Group deleted',
                'status': 'group_deleted',
                'reason': delete_reason
            }, status=410)
        
        # Get users who are members of this group (have messages) and are currently online
        online_count = group.get_group_online_count()
        
        # Get names of these online users
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
        
        print(f"[ONLINE_USERS] Group {code}: {len(users_list)} online users")
        
        return JsonResponse({
            'success': True,
            'users': users_list,
            'count': len(users_list)
        })
    except Group.DoesNotExist:
        print(f"[ONLINE_USERS] Group {code} not found")
        return JsonResponse({'error': 'Group not found', 'status': 'group_not_found'}, status=404)
    except Exception as e:
        print(f"[ERROR] get_online_users: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)

@require_http_methods(["GET"])
def get_new_messages(request, code):
    """Get new messages since last timestamp - for live updates"""
    try:
        group = Group.objects.get(code=code)
        session_id = request.session.session_key
        since_timestamp = request.GET.get('since', '')
        
        # AUTO-DELETE CHECK: Most frequently called endpoint - check deletion here
        should_delete, delete_reason = check_and_cleanup_group(group)
        if should_delete:
            print(f"[GET_NEW_MESSAGES] Group {code} deleted - returning 410 Gone")
            return JsonResponse({
                'error': 'Group deleted',
                'status': 'group_deleted',
                'reason': delete_reason
            }, status=410)  # HTTP 410 Gone - resource no longer exists
        
        # Build query
        messages_query = Message.objects.filter(group=group).order_by('timestamp')
        
        # Filter by timestamp if provided
        if since_timestamp:
            try:
                from django.utils.dateparse import parse_datetime
                since_dt = parse_datetime(since_timestamp)
                if since_dt:
                    messages_query = messages_query.filter(timestamp__gt=since_dt)
            except:
                pass
        
        messages_list = []
        for msg_obj in messages_query:
            # Skip deleted messages for other users
            if msg_obj.is_deleted == 'deleted_for_me' and msg_obj.session_id != session_id:
                continue
            
            message_obj = {
                'id': msg_obj.id,
                'user_name': msg_obj.user_name,
                'content': msg_obj.content,
                'message_type': msg_obj.message_type,
                'timestamp': msg_obj.timestamp.isoformat(),
                'is_sender': msg_obj.session_id == session_id,
                'is_deleted': msg_obj.is_deleted,
            }
            
            if msg_obj.message_type == 'voice':
                # Use .url property to get proper media URL (e.g., /media/voice_messages/file.webm)
                message_obj['audio_url'] = msg_obj.audio_file.url if msg_obj.audio_file else ''
                message_obj['audio_mime_type'] = msg_obj.audio_mime_type or 'audio/webm'
                message_obj['duration'] = msg_obj.duration
            
            messages_list.append(message_obj)
        
        # Get online count for this group
        online_count = group.get_group_online_count()
        
        # Update user's last_seen timestamp (heartbeat)
        update_user_online_status(session_id, request.session.get('user_name', 'Anonymous'), is_online=True)
        
        return JsonResponse({
            'success': True,
            'messages': messages_list,
            'online_count': online_count,
            'timestamp': timezone.now().isoformat()
        })
    except Group.DoesNotExist:
        print(f"[GET_NEW_MESSAGES] Group {code} not found")
        return JsonResponse({'error': 'Group not found', 'status': 'group_not_found'}, status=404)
    except Exception as e:
        print(f"[ERROR] get_new_messages: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)

@require_http_methods(["POST"])
def send_message_ajax(request, code):
    """Send text message via AJAX - for live updates with activity tracking"""
    try:
        group = Group.objects.get(code=code)
        
        # AUTO-DELETE CHECK: Before processing message
        should_delete, delete_reason = check_and_cleanup_group(group)
        if should_delete:
            print(f"[SEND_MESSAGE] Group {code} deleted - returning 410 Gone")
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
        
        # Validate message length
        if len(content) > 5000:
            return JsonResponse({'error': 'Message too long (max 5000 characters)'}, status=400)
        
        # Create or update anonymous user
        anon_user, _ = AnonymousUser.objects.get_or_create(
            session_id=session_id,
            defaults={'user_name': user_name}
        )
        anon_user.last_seen = timezone.now()
        anon_user.is_online = True
        anon_user.save(update_fields=['last_seen', 'is_online'])
        
        # Create text message
        message = Message.objects.create(
            group=group,
            content=content,
            message_type='text',
            user_name=user_name,
            session_id=session_id
        )
        
        # Update group last activity
        group.last_activity = timezone.now()
        group.save(update_fields=['last_activity'])
        
        print(f"[MESSAGE] {user_name} sent text message in group {group.code}")
        
        return JsonResponse({
            'success': True,
            'message': {
                'id': message.id,
                'user_name': message.user_name,
                'content': message.content,
                'timestamp': message.timestamp.isoformat(),
                'is_sender': True,
                'is_deleted': message.is_deleted
            }
        })
    except Group.DoesNotExist:
        print(f"[SEND_MESSAGE] Group {code} not found")
        return JsonResponse({'error': 'Group not found', 'status': 'group_not_found'}, status=404)
    except Exception as e:
        print(f"[ERROR] send_message_ajax: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)


# ============================================================================
# AUTO-DELETION & CLEANUP MONITORING ENDPOINTS
# ============================================================================

@require_http_methods(["GET"])
def get_group_cleanup_status(request, code):
    """Get deletion status and reason for a specific group (Admin only)"""
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
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["GET"])
def get_all_groups_status(request):
    """Get cleanup status for all groups (Admin monitoring)"""
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
        
        # Sort by should_delete (delete candidates first)
        statuses.sort(key=lambda x: (not x['should_delete'], x['inactivity_minutes']), reverse=True)
        
        return JsonResponse({
            'success': True,
            'total_groups': len(statuses),
            'groups': statuses
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)