from django.db import models
from django.utils import timezone

class AnonymousUser(models.Model):
    """Track anonymous users without authentication"""
    session_id = models.CharField(max_length=255, unique=True)
    user_name = models.CharField(max_length=100)
    is_online = models.BooleanField(default=True)
    last_seen = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user_name}"

    class Meta:
        ordering = ['-last_seen']

class Group(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']

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
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPE_CHOICES, default='text')
    duration = models.FloatField(default=0)
    
    # Deletion tracking
    is_deleted = models.CharField(max_length=20, choices=DELETE_STATUS_CHOICES, default='not_deleted')
    
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