from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User

# Constants
ONLINE_TIMEOUT_MINUTES = 5
INACTIVITY_DELETE_MINUTES = 360  # 12 hours 720
NEW_GROUP_DELETE_MINUTES = 720  # 1 day 1440

class UserProfile(models.Model):
    """Profile to track if a registered user is approved by admin"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    is_approved = models.BooleanField(default=False)
    mobile_number = models.CharField(max_length=15, blank=True, null=True, verbose_name="Mobile Number")

    def __str__(self):
        return f"{self.user.username} - Approved: {self.is_approved}"

class AnonymousUser(models.Model):
    """Track anonymous users without authentication"""
    LANGUAGE_MODE_CHOICES = [
        ('english', 'English Mode - Display only English, reject Tamil/Tanglish'),
        ('tamil', 'Tamil Mode - Display only Tamil, accept Tamil/English input'),
    ]
    
    session_id = models.CharField(max_length=255, unique=True)
    user_name = models.CharField(max_length=100)
    is_online = models.BooleanField(default=True)
    last_seen = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    language_mode = models.CharField(
        max_length=10,
        choices=LANGUAGE_MODE_CHOICES,
        default='english',
        help_text='User language display mode: English only or Tamil only'
    )

    def __str__(self):
        return f"{self.user_name} ({self.get_language_mode_display()})"

    class Meta:
        ordering = ['-last_seen']

class Group(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['last_activity']),
            models.Index(fields=['created_at']),
        ]

    def get_group_online_count(self):
        """Get count of users online in this group in last 5 minutes"""
        cutoff_time = timezone.now() - timedelta(minutes=ONLINE_TIMEOUT_MINUTES)
        return self.members.filter(last_seen__gte=cutoff_time).count()


    def should_auto_delete(self):
        """Check auto-delete conditions and return (should_delete, reason)"""
        try:
            online_count = self.get_group_online_count()
            if online_count > 0:
                return False, "active"
            
            now = timezone.now()
            age_minutes = (now - self.created_at).total_seconds() / 60
            inactivity_minutes = (now - self.last_activity).total_seconds() / 60
            
            if age_minutes >= NEW_GROUP_DELETE_MINUTES:
                return True, "new_empty_1day"
            
            if inactivity_minutes >= INACTIVITY_DELETE_MINUTES:
                return True, "all_left_12hours"
            
            return False, "too_new_or_fresh"
        
        except Exception as e:
            logger.error(f"Group {self.code}: Error checking auto-delete: {str(e)}")
            return False, "error"

class Message(models.Model):
    MESSAGE_TYPE_CHOICES = [
        ('text', 'Text'),
        ('voice', 'Voice'),
    ]
    
    DELETE_STATUS_CHOICES = [
        ('not_deleted', 'Not Deleted'),
        ('deleted_for_me', 'Deleted For Me'),
        ('deleted_for_all', 'Deleted For All'),
    ]
    
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='messages')
    user_name = models.CharField(max_length=100, default='Anonymous')
    session_id = models.CharField(max_length=255, default='')
    content = models.TextField(blank=True, null=True)
    audio_file = models.FileField(upload_to='voice_messages/', blank=True, null=True)
    audio_mime_type = models.CharField(max_length=50, default='audio/webm', help_text='MIME type of audio file')
    
    # Bilingual audio support for voice messages
    audio_file_english = models.FileField(upload_to='voice_messages/', blank=True, null=True, help_text='English version of voice message')
    audio_file_tamil = models.FileField(upload_to='voice_messages/', blank=True, null=True, help_text='Tamil version of voice message')
    
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPE_CHOICES, default='text')
    duration = models.FloatField(default=0)
    
    # Deletion tracking
    is_deleted = models.CharField(max_length=20, choices=DELETE_STATUS_CHOICES, default='not_deleted')
    
    # Translation support
    normalized_content = models.TextField(blank=True, null=True, help_text='Professional English version of message (sent to receivers)')
    translated_content = models.TextField(blank=True, null=True, help_text='Cached translation of original content')
    translated_language = models.CharField(max_length=50, blank=True, default='', help_text='Language that translated_content is in')
    
    # Bilingual message storage (NEW - explicit Tamil and English versions)
    tamil_content = models.TextField(blank=True, null=True, help_text='Tamil version of the message (auto-translated)')
    english_content = models.TextField(blank=True, null=True, help_text='Professional English version of the message')
    
    timestamp = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['group', 'timestamp']),
            models.Index(fields=['session_id', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.user_name} - {self.message_type}"

    def is_deleted_for_user(self, session_id):
        """Check if message is deleted for a specific user"""
        if self.is_deleted == 'deleted_for_all':
            return True
        return False

    def get_display_text(self):
        """Get text to display"""
        if self.is_deleted == 'deleted_for_all':
            return "This message was deleted"
        return self.content


class GroupMember(models.Model):
    """Track group membership"""
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='members')
    session_id = models.CharField(max_length=255)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('group', 'session_id')
        ordering = ['-joined_at']
        indexes = [
            models.Index(fields=['group', 'last_seen']),
        ]

    def __str__(self):
        return f"{self.session_id} in {self.group.code}"


class DeletedMessage(models.Model):
    """Track user-specific message deletions"""
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='deletions')
    session_id = models.CharField(max_length=255)
    deleted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('message', 'session_id')
        indexes = [
            models.Index(fields=['message', 'session_id']),
        ]

    def __str__(self):
        return f"{self.session_id} deleted {self.message.id}"
