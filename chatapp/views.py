from django.shortcuts import render, redirect
from .models import Group, Message
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
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
        return redirect("group", code=group.code)

    return render(request, "chat.html")

@login_required(login_url='register')
def group(request, code):
    group = Group.objects.get(code=code)
    messages_list = Message.objects.filter(group=group).order_by('timestamp')

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

    users = messages_list.values_list('user__username', flat=True).distinct()

    return render(request, "group.html", {
        "group": group,
        "messages": messages_list,
        "users": users
    })

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
            duration=max(duration, 1)  # Ensure minimum 1 second
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