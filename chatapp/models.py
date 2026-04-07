from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Group(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    members = models.ManyToManyField(User, related_name='chat_groups', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']

class UserStatus(models.Model):
    """Track online/offline status of users in groups"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_statuses')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='user_statuses')
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'group')
        ordering = ['-last_seen']

    def __str__(self):
        return f"{self.user.username} - {self.group.name} ({self.get_status()})"

    def get_status(self):
        return "Online" if self.is_online else "Offline"

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
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='messages')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='messages')
    content = models.TextField(blank=True, null=True)
    audio_file = models.FileField(upload_to='voice_messages/', blank=True, null=True)
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPE_CHOICES, default='text')
    duration = models.FloatField(default=0)
    
    # Deletion tracking
    is_deleted = models.CharField(max_length=20, choices=DELETE_STATUS_CHOICES, default='not_deleted')
    deleted_by = models.ManyToManyField(User, related_name='deleted_messages', blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['group', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.message_type}"

    def is_deleted_for_user(self, user):
        """Check if message is deleted for a specific user"""
        if self.is_deleted == 'deleted_for_all':
            return True
        if self.is_deleted == 'deleted_for_me' and user in self.deleted_by.all():
            return True
        return False

    def get_display_text(self, user):
        """Get text to display for a user"""
        if self.is_deleted == 'deleted_for_all':
            return "This message was deleted"
        if self.is_deleted == 'deleted_for_me' and user in self.deleted_by.all():
            return None
        return self.content