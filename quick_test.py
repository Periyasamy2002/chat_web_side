"""
Quick test to verify short messages work
"""

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatproject.settings')

import django
django.setup()

from django.test import Client
from chatapp.models import Group, Message

client = Client()

# Create test group
group, _ = Group.objects.get_or_create(code='HITEST', defaults={'name': 'Hi Test'})

# Visit the group page to create session
response = client.get(f'/group/{group.code}/')
print(f"Visit group page: {response.status_code}")

# Get CSRF token from cookies
csrf_token = response.cookies.get('csrftoken', '')
print(f"CSRF token: {csrf_token[:10] if csrf_token else 'NOT FOUND'}...")

# Send short message
print("\nTesting short message 'hi'...")
response = client.post(f'/group/{group.code}/send-message/', {
    'message': 'hi'
}, HTTP_X_CSRFTOKEN=csrf_token)

print(f"Status: {response.status_code}")
print(f"Response: {response.content.decode()[:500]}")

# Check database
messages = Message.objects.filter(group=group, content='hi')
print(f"\nMessages in DB: {messages.count()}")
for msg in messages:
    print(f"  - ID: {msg.id}, Content: '{msg.content}', User: {msg.user_name}")
