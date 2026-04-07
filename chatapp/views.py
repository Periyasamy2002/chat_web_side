from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect
from .models import Group, Message
from django.contrib.auth.decorators import login_required

def home(request):
    return render(request, "home.html")

def chat(request):
    if request.method == "POST":
        code = request.POST.get("code")
        name = request.POST.get("name")

        group, created = Group.objects.get_or_create(code=code, defaults={"name": name})
        return redirect("group", code=group.code)

    return render(request, "chat.html")

@login_required
def group(request, code):
    group = Group.objects.get(code=code)
    messages = Message.objects.filter(group=group)

    if request.method == "POST":
        content = request.POST.get("message")
        Message.objects.create(user=request.user, group=group, content=content)

    users = messages.values_list('user__username', flat=True).distinct()

    return render(request, "group.html", {
        "group": group,
        "messages": messages,
        "users": users
    })