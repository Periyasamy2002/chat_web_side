"""
Test fixtures and sample data for the chat application.
Run with: python manage.py loaddata fixtures/sample_data.json
"""

from django.conf import settings
from django.core.files.base import ContentFile
from chatapp.models import Group, Message, AnonymousUser
from django.utils import timezone
from datetime import timedelta
import json

def create_sample_data():
    """Create sample groups, users, and messages for testing"""
    
    # Clear existing data
    Message.objects.all().delete()
    AnonymousUser.objects.all().delete()
    Group.objects.all().delete()
    
    print("Creating sample groups...")
    
    # Create test groups
    groups_data = [
        {"code": "DEVTEAM", "name": "Development Team"},
        {"code": "DESIGN", "name": "Design Team"},
        {"code": "SUPPORT", "name": "Customer Support"},
    ]
    
    groups = {}
    for group_data in groups_data:
        group = Group.objects.create(
            code=group_data["code"],
            name=group_data["name"],
            last_activity=timezone.now()
        )
        groups[group_data["code"]] = group
        print(f"  ✓ Created group: {group.code}")
    
    # Create sample users
    print("\nCreating sample users...")
    
    users_data = [
        {"session_id": "user1", "user_name": "Alice", "is_online": True},
        {"session_id": "user2", "user_name": "Bob", "is_online": True},
        {"session_id": "user3", "user_name": "Charlie", "is_online": False},
    ]
    
    users = {}
    for user_data in users_data:
        user = AnonymousUser.objects.create(
            session_id=user_data["session_id"],
            user_name=user_data["user_name"],
            is_online=user_data["is_online"],
            last_seen=timezone.now() if user_data["is_online"] else timezone.now() - timedelta(minutes=15)
        )
        users[user_data["session_id"]] = user
        print(f"  ✓ Created user: {user.user_name} ({user.session_id})")
    
    # Create sample text messages
    print("\nCreating sample text messages...")
    
    text_messages = [
        {
            "group": "DEVTEAM",
            "user_name": "Alice",
            "session_id": "user1",
            "content": "Hey everyone! How's the sprint going?",
            "timestamp_offset": -600  # 10 minutes ago
        },
        {
            "group": "DEVTEAM",
            "user_name": "Bob",
            "session_id": "user2",
            "content": "Going well! Just finishing up the API endpoint.",
            "timestamp_offset": -480  # 8 minutes ago
        },
        {
            "group": "DEVTEAM",
            "user_name": "Alice",
            "session_id": "user1",
            "content": "Great! Any blockers?",
            "timestamp_offset": -300  # 5 minutes ago
        },
        {
            "group": "DESIGN",
            "user_name": "Charlie",
            "session_id": "user3",
            "content": "New mockups are ready for review",
            "timestamp_offset": -120  # 2 minutes ago
        },
    ]
    
    for msg_data in text_messages:
        timestamp = timezone.now() + timedelta(seconds=msg_data["timestamp_offset"])
        msg = Message.objects.create(
            group=groups[msg_data["group"]],
            user_name=msg_data["user_name"],
            session_id=msg_data["session_id"],
            content=msg_data["content"],
            message_type="text",
            timestamp=timestamp
        )
        print(f"  ✓ Created text message: {msg.user_name} -> {msg_data['group']}")
    
    # Create sample voice message (with dummy audio)
    print("\nCreating sample voice messages...")
    
    # Create a dummy audio file
    dummy_audio = b"fake audio data for testing"
    
    voice_msg = Message.objects.create(
        group=groups["DEVTEAM"],
        user_name="Bob",
        session_id="user2",
        message_type="voice",
        duration=5.2,
        audio_mime_type="audio/webm"
    )
    voice_msg.audio_file.save(
        f"voice_messages/sample_voice_{voice_msg.id}.webm",
        ContentFile(dummy_audio),
        save=True
    )
    print(f"  ✓ Created voice message: Bob -> DEVTEAM (5.2s)")
    
    # Create a deleted message
    deleted_msg = Message.objects.create(
        group=groups["DESIGN"],
        user_name="Alice",
        session_id="user1",
        content="This message will be deleted",
        message_type="text",
        is_deleted="deleted_for_all"
    )
    print(f"  ✓ Created deleted message (marked as deleted for all)")
    
    print("\n✅ Sample data created successfully!")
    print(f"\nSummary:")
    print(f"  - Groups: {len(groups)}")
    print(f"  - Users: {len(users)}")
    print(f"  - Total Messages: {Message.objects.count()}")
    print(f"  - Text Messages: {Message.objects.filter(message_type='text').count()}")
    print(f"  - Voice Messages: {Message.objects.filter(message_type='voice').count()}")
    print(f"  - Deleted Messages: {Message.objects.filter(is_deleted='deleted_for_all').count()}")


def export_to_json():
    """Export current data to JSON fixture"""
    fixtures = {
        "groups": [],
        "users": [],
        "messages": []
    }
    
    for group in Group.objects.all():
        fixtures["groups"].append({
            "code": group.code,
            "name": group.name,
            "created_at": group.created_at.isoformat(),
        })
    
    for user in AnonymousUser.objects.all():
        fixtures["users"].append({
            "session_id": user.session_id,
            "user_name": user.user_name,
            "is_online": user.is_online,
            "last_seen": user.last_seen.isoformat(),
        })
    
    for msg in Message.objects.all():
        fixtures["messages"].append({
            "group_code": msg.group.code,
            "user_name": msg.user_name,
            "session_id": msg.session_id,
            "content": msg.content,
            "message_type": msg.message_type,
            "is_deleted": msg.is_deleted,
            "timestamp": msg.timestamp.isoformat(),
        })
    
    return json.dumps(fixtures, indent=2)


if __name__ == "__main__":
    create_sample_data()
