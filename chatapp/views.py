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
        
        # Create or update anonymous user record
        try:
            anon_user, created = AnonymousUser.objects.get_or_create(
                session_id=request.session.session_key,
                defaults={'user_name': user_name}
            )
            if not created:
                anon_user.user_name = user_name
                anon_user.save()
        except:
            pass
        
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
    
    # Handle text message posting
    if request.method == "POST":
        content = request.POST.get("message")
        if content and content.strip():
            Message.objects.create(
                group=group, 
                content=content,
                message_type='text',
                user_name=user_name,
                session_id=session_id
            )
        return redirect('group', code=code)
    
    # Get online users in this group
    online_users = AnonymousUser.objects.filter(
        last_seen__gte=timezone.now() - timezone.timedelta(minutes=5)
    ).distinct()
    
    context = {
        "group": group,
        "messages": messages_list,
        "user_name": user_name,
        "online_count": online_users.count(),
    }
    
    return render(request, "group.html", context)

@require_http_methods(["POST"])
def upload_voice_message(request, code):
    """Handle voice message uploads"""
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
        
        # Create voice message
        message = Message.objects.create(
            group=group,
            audio_file=audio_file,
            message_type='voice',
            duration=max(duration, 1),
            user_name=user_name,
            session_id=session_id
        )
        
        return JsonResponse({
            'success': True,
            'message_id': message.id,
            'audio_url': message.audio_file.url
        })
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Group not found'}, status=404)
    except Exception as e:
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
    """Update user online/offline status"""
    try:
        group = Group.objects.get(code=code)
        user_name = request.session.get('user_name', 'Anonymous')
        session_id = request.session.session_key
        is_online = request.POST.get('is_online', 'false').lower() == 'true'
        
        anon_user, _ = AnonymousUser.objects.get_or_create(
            session_id=session_id,
            defaults={'user_name': user_name}
        )
        anon_user.is_online = is_online
        anon_user.last_seen = timezone.now()
        anon_user.save()
        
        # Get updated online count
        online_count = AnonymousUser.objects.filter(
            is_online=True,
            last_seen__gte=timezone.now() - timezone.timedelta(minutes=5)
        ).count()
        
        return JsonResponse({
            'success': True,
            'is_online': anon_user.is_online,
            'online_count': online_count
        })
    except Exception as e:
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