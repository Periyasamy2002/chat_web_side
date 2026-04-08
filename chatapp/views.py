from django.shortcuts import render, redirect
from .models import Group, Message, AnonymousUser
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import json
import uuid

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
            print(f"Note: last_activity field not yet available. Run: python manage.py migrate")
        
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
            
            print(f"✓ User '{user_name}' joined group '{code}'")
        except Exception as e:
            print(f"Error creating user record: {str(e)}")
        
        # Add group code to session
        request.session['group_code'] = code
        
        return redirect("group", code=group.code)

    return render(request, "chat.html")

def group(request, code):
    try:
        group = Group.objects.get(code=code)
    except Group.DoesNotExist:
        return redirect('chat')
    
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
        user_name = request.session.get('user_name', 'Anonymous')
        session_id = request.session.session_key
        
        if 'audio' not in request.FILES:
            return JsonResponse({'error': 'No audio file provided'}, status=400)
        
        audio_file = request.FILES['audio']
        duration = float(request.POST.get('duration', 0))
        
        # Validate file size (max 50MB)
        if audio_file.size > 50 * 1024 * 1024:
            return JsonResponse({'error': 'Audio file too large (max 50MB)'}, status=400)
        
        # Create or update anonymous user
        anon_user, _ = AnonymousUser.objects.get_or_create(
            session_id=session_id,
            defaults={'user_name': user_name}
        )
        anon_user.last_seen = timezone.now()
        anon_user.save(update_fields=['last_seen'])
        
        # Create voice message
        message = Message.objects.create(
            group=group,
            audio_file=audio_file,
            message_type='voice',
            duration=max(duration, 1),
            user_name=user_name,
            session_id=session_id
        )
        
        # Update group last activity if field exists
        try:
            if hasattr(group, 'last_activity'):
                group.last_activity = timezone.now()
                group.save(update_fields=['last_activity'])
        except Exception as e:
            if 'last_activity' not in str(e):
                raise
        
        print(f"✓ Voice message uploaded: {user_name} in group {group.code} (duration: {duration}s)")
        
        return JsonResponse({
            'success': True,
            'message_id': message.id,
            'audio_url': message.audio_file.url
        })
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Group not found'}, status=404)
    except Exception as e:
        print(f"Error in upload_voice_message: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)

@require_http_methods(["POST"])
def delete_message(request, code):
    """Delete a message for me or for everyone"""
    try:
        group = Group.objects.get(code=code)
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
        
        return JsonResponse({'success': True, 'status': message.is_deleted})
    except Message.DoesNotExist:
        return JsonResponse({'error': 'Message not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_http_methods(["POST"])
def update_user_status(request, code):
    """Update user online/offline status with auto-timeout detection"""
    try:
        group = Group.objects.get(code=code)
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
        anon_user.save()
        
        # Update group last activity timestamp if field exists
        try:
            if hasattr(group, 'last_activity'):
                group.last_activity = timezone.now()
                group.save(update_fields=['last_activity'])
        except Exception as e:
            if 'last_activity' not in str(e):
                raise
        
        # Auto-mark users offline if inactive for 30 minutes
        # (This is a safety net - frontend should also ping regularly)
        try:
            thirty_min_ago = timezone.now() - timezone.timedelta(minutes=30)
            inactive_users = AnonymousUser.objects.filter(
                is_online=True,
                last_seen__lt=thirty_min_ago
            )
            for user in inactive_users:
                user.is_online = False
                user.save(update_fields=['is_online'])
                print(f"Auto-marked user {user.user_name} as offline (inactive for 30+ minutes)")
        except Exception as e:
            print(f"Warning: Could not auto-mark users offline: {str(e)}")
        
        # Get updated online count for this group
        five_min_ago = timezone.now() - timezone.timedelta(minutes=5)
        online_count = AnonymousUser.objects.filter(
            is_online=True,
            last_seen__gte=five_min_ago
        ).count()
        
        return JsonResponse({
            'success': True,
            'is_online': anon_user.is_online,
            'online_count': online_count
        })
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Group not found'}, status=404)
    except Exception as e:
        print(f"Error in update_user_status: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)

@require_http_methods(["GET"])
def get_online_users(request, code):
    """Get list of online users"""
    try:
        group = Group.objects.get(code=code)
        online_users = AnonymousUser.objects.filter(
            is_online=True,
            last_seen__gte=timezone.now() - timezone.timedelta(minutes=5)
        ).values_list('user_name', 'id')
        
        users_list = [
            {
                'id': user[1],
                'display_name': user[0] or 'Anonymous'
            }
            for user in online_users
        ]
        
        return JsonResponse({
            'success': True,
            'users': users_list,
            'count': len(users_list)
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_http_methods(["GET"])
def get_new_messages(request, code):
    """Get new messages since last timestamp - for live updates"""
    try:
        group = Group.objects.get(code=code)
        session_id = request.session.session_key
        since_timestamp = request.GET.get('since', '')
        
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
        
        messages = messages_query.values(
            'id', 'user_name', 'session_id', 'content', 'message_type', 
            'audio_file', 'duration', 'timestamp', 'is_deleted'
        )
        
        messages_list = []
        for msg in messages:
            # Skip deleted messages for other users
            if msg['is_deleted'] == 'deleted_for_me' and msg['session_id'] != session_id:
                continue
            
            message_obj = {
                'id': msg['id'],
                'user_name': msg['user_name'],
                'content': msg['content'],
                'message_type': msg['message_type'],
                'timestamp': msg['timestamp'].isoformat(),
                'is_sender': msg['session_id'] == session_id,
                'is_deleted': msg['is_deleted'],
            }
            
            if msg['message_type'] == 'voice':
                message_obj['audio_url'] = msg['audio_file']
                message_obj['duration'] = msg['duration']
            
            messages_list.append(message_obj)
        
        # Get online count and update last activity
        five_min_ago = timezone.now() - timezone.timedelta(minutes=5)
        online_count = AnonymousUser.objects.filter(
            is_online=True,
            last_seen__gte=five_min_ago
        ).count()
        
        # Auto-delete groups only if migration has been applied
        try:
            if hasattr(group, 'last_activity'):
                thirty_min_ago = timezone.now() - timezone.timedelta(minutes=30)
                empty_groups = Group.objects.filter(
                    last_activity__lt=thirty_min_ago
                ).exclude(messages__isnull=False)
                
                deleted_count = 0
                for empty_group in empty_groups:
                    # Double-check online count for this specific group
                    group_online = AnonymousUser.objects.filter(
                        is_online=True,
                        last_seen__gte=five_min_ago
                    ).count()
                    
                    if group_online == 0:
                        print(f"Auto-deleting empty group: {empty_group.code}")
                        empty_group.delete()
                        deleted_count += 1
                
                if deleted_count > 0:
                    print(f"Auto-deleted {deleted_count} empty groups")
        except Exception as e:
            if 'last_activity' not in str(e):
                print(f"Warning: Auto-delete check failed: {str(e)}")
        
        return JsonResponse({
            'success': True,
            'messages': messages_list,
            'online_count': online_count,
            'timestamp': timezone.now().isoformat()
        })
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Group not found'}, status=404)
    except Exception as e:
        print(f"Error in get_new_messages: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)

@require_http_methods(["POST"])
def send_message_ajax(request, code):
    """Send text message via AJAX - for live updates with activity tracking"""
    try:
        group = Group.objects.get(code=code)
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
        anon_user.save(update_fields=['last_seen'])
        
        # Create text message
        message = Message.objects.create(
            group=group,
            content=content,
            message_type='text',
            user_name=user_name,
            session_id=session_id
        )
        
        # Update group last activity if field exists
        try:
            if hasattr(group, 'last_activity'):
                group.last_activity = timezone.now()
                group.save(update_fields=['last_activity'])
        except Exception as e:
            if 'last_activity' not in str(e):
                raise
        
        print(f"✓ Text message sent: {user_name} in group {group.code}")
        
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
        return JsonResponse({'error': 'Group not found'}, status=404)
    except Exception as e:
        print(f"Error in send_message_ajax: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)