from django.shortcuts import render, redirect
from .models import Group, Message, UserStatus
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import json

def register(request):
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == "POST":
        action = request.POST.get('action')
        
        # SIGN UP
        if action == 'signup':
            name = request.POST.get('signup_name')
            email = request.POST.get('signup_email')
            password = request.POST.get('signup_password')
            confirm_password = request.POST.get('signup_confirm_password')
            
            if password != confirm_password:
                messages.error(request, "Passwords do not match!")
                return render(request, 'register.html')
            
            if User.objects.filter(username=email).exists():
                messages.error(request, "Email already registered!")
                return render(request, 'register.html')
            
            user = User.objects.create_user(
                username=email,
                email=email,
                first_name=name,
                password=password
            )
            messages.success(request, "Account created! Please log in.")
            return render(request, 'register.html')
        
        # SIGN IN
        elif action == 'signin':
            email = request.POST.get('signin_email')
            password = request.POST.get('signin_password')
            
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                return redirect('chat')
            else:
                messages.error(request, "Invalid email or password!")
                return render(request, 'register.html')
    
    return render(request, 'register.html')

def logout_view(request):
    logout(request)
    return redirect('register')

def home(request):
    if not request.user.is_authenticated:
        return redirect('register')
    return render(request, "home.html")

def chat(request):
    if not request.user.is_authenticated:
        return redirect('register')
    
    if request.method == "POST":
        code = request.POST.get("code")
        name = request.POST.get("name")

        group, created = Group.objects.get_or_create(code=code, defaults={"name": name})
        
        # Add user to group members
        if not group.members.filter(id=request.user.id).exists():
            group.members.add(request.user)
        
        # Set user as online
        user_status, _ = UserStatus.objects.get_or_create(
            user=request.user,
            group=group,
            defaults={'is_online': True}
        )
        user_status.is_online = True
        user_status.last_seen = timezone.now()
        user_status.save()
        
        return redirect("group", code=group.code)

    return render(request, "chat.html")

@login_required(login_url='register')
def group(request, code):
    try:
        group = Group.objects.get(code=code)
    except Group.DoesNotExist:
        return redirect('chat')
    
    # Ensure user is a member
    if not group.members.filter(id=request.user.id).exists():
        group.members.add(request.user)
    
    # Update user online status
    user_status, _ = UserStatus.objects.get_or_create(
        user=request.user,
        group=group,
        defaults={'is_online': True}
    )
    user_status.is_online = True
    user_status.last_seen = timezone.now()
    user_status.save()
    
    # Get all messages
    messages_list = Message.objects.filter(group=group).select_related('user').prefetch_related('deleted_by').order_by('timestamp')
    
    # Filter messages that should be visible to current user
    visible_messages = []
    for msg in messages_list:
        if msg.is_deleted == 'deleted_for_all':
            # Everyone sees "message deleted"
            visible_messages.append(msg)
        elif msg.is_deleted == 'deleted_for_me':
            # Only hide if deleted by current user
            if request.user not in msg.deleted_by.all():
                visible_messages.append(msg)
        else:
            # Not deleted messages are always visible
            visible_messages.append(msg)
    
    # Handle text message posting
    if request.method == "POST":
        content = request.POST.get("message")
        if content and content.strip():
            Message.objects.create(
                user=request.user, 
                group=group, 
                content=content,
                message_type='text'
            )
        return redirect('group', code=code)
    
    # Get online users
    online_user_statuses = UserStatus.objects.filter(group=group, is_online=True).select_related('user')
    all_users = group.members.all()
    
    # Create a dictionary mapping user IDs to their status
    user_status_map = {}
    online_user_ids = set()
    
    for status in UserStatus.objects.filter(group=group).select_related('user'):
        user_status_map[status.user.id] = {
            'is_online': status.is_online,
            'last_seen': status.last_seen,
        }
        if status.is_online:
            online_user_ids.add(status.user.id)
    
    context = {
        "group": group,
        "messages": visible_messages,
        "all_users": all_users,
        "online_user_statuses": online_user_statuses,
        "online_user_ids": online_user_ids,
        "online_count": len(online_user_ids),
        "current_user": request.user,
        "user_status_map": user_status_map,
    }
    
    return render(request, "group.html", context)

@login_required(login_url='register')
@require_http_methods(["POST"])
def upload_voice_message(request, code):
    """Handle voice message uploads"""
    try:
        group = Group.objects.get(code=code)
        
        if 'audio' not in request.FILES:
            print("Error: No audio file in request")
            return JsonResponse({'error': 'No audio file provided'}, status=400)
        
        audio_file = request.FILES['audio']
        duration = float(request.POST.get('duration', 0))
        
        print(f"Received audio file: {audio_file.name}, size: {audio_file.size} bytes, duration: {duration}s")
        
        # Validate file size (max 50MB)
        if audio_file.size > 50 * 1024 * 1024:
            return JsonResponse({'error': 'Audio file too large (max 50MB)'}, status=400)
        
        # Create voice message
        message = Message.objects.create(
            user=request.user,
            group=group,
            audio_file=audio_file,
            message_type='voice',
            duration=max(duration, 1)
        )
        
        print(f"Voice message created successfully with ID: {message.id}")
        
        return JsonResponse({
            'success': True,
            'message_id': message.id,
            'audio_url': message.audio_file.url
        })
    except Group.DoesNotExist:
        print(f"Error: Group with code {code} not found")
        return JsonResponse({'error': 'Group not found'}, status=404)
    except Exception as e:
        print(f"Error in upload_voice_message: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)

@login_required(login_url='register')
@require_http_methods(["POST"])
def delete_message(request, code):
    """Delete a message for me or for everyone"""
    try:
        group = Group.objects.get(code=code)
        message_id = request.POST.get('message_id')
        delete_type = request.POST.get('delete_type')  # 'for_me' or 'for_all'
        
        if not message_id or not delete_type:
            return JsonResponse({'error': 'Missing parameters'}, status=400)
        
        message = Message.objects.get(id=message_id, group=group)
        
        # Only sender can delete for everyone
        if delete_type == 'for_all' and message.user != request.user:
            return JsonResponse({'error': 'Only sender can delete for everyone'}, status=403)
        
        if delete_type == 'for_all':
            message.is_deleted = 'deleted_for_all'
            message.save()
        elif delete_type == 'for_me':
            message.is_deleted = 'deleted_for_me'
            message.deleted_by.add(request.user)
        
        return JsonResponse({'success': True, 'status': message.is_deleted})
    except Message.DoesNotExist:
        return JsonResponse({'error': 'Message not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required(login_url='register')
@require_http_methods(["POST"])
def update_user_status(request, code):
    """Update user online/offline status"""
    try:
        group = Group.objects.get(code=code)
        is_online = request.POST.get('is_online', 'false').lower() == 'true'
        
        user_status, _ = UserStatus.objects.get_or_create(
            user=request.user,
            group=group
        )
        user_status.is_online = is_online
        user_status.last_seen = timezone.now()
        user_status.save()
        
        # Get updated online count
        online_count = UserStatus.objects.filter(group=group, is_online=True).count()
        
        return JsonResponse({
            'success': True,
            'is_online': user_status.is_online,
            'online_count': online_count
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required(login_url='register')
@require_http_methods(["GET"])
def get_online_users(request, code):
    """Get list of online users"""
    try:
        group = Group.objects.get(code=code)
        online_users = UserStatus.objects.filter(
            group=group, 
            is_online=True
        ).select_related('user').values_list('user__username', 'user__first_name', 'user__id')
        
        users_list = [
            {
                'id': user[2],
                'username': user[0],
                'display_name': user[1] or user[0]
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