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
    # Track last activity for auto-delete feature
    last_activity = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['last_activity']),
            models.Index(fields=['created_at']),
        ]

    def get_online_count(self):
        """Get count of users online in last 5 minutes"""
        from django.utils import timezone
        from datetime import timedelta
        five_min_ago = timezone.now() - timedelta(minutes=5)
        return AnonymousUser.objects.filter(
            is_online=True,
            last_seen__gte=five_min_ago
        ).count()

    def get_group_online_count(self):
        """Get count of users online in THIS GROUP in last 5 minutes"""
        from django.utils import timezone
        from datetime import timedelta
        five_min_ago = timezone.now() - timedelta(minutes=5)
        # Count messages from this group by unique users in last 5 minutes
        return AnonymousUser.objects.filter(
            is_online=True,
            last_seen__gte=five_min_ago
        ).count()

    def should_auto_delete_empty(self):
        """Check 1: If group is opened with 0 users online"""
        return self.get_online_count() == 0

    def should_auto_delete_new_empty(self):
        """Check 2: If new group created and no users joined within 5 minutes"""
        from datetime import timedelta
        five_min_ago = timezone.now() - timedelta(minutes=5)
        # If created 5+ minutes ago AND has 0 online users
        return self.created_at < five_min_ago and self.get_online_count() == 0

    def should_auto_delete_all_left(self):
        """Check 4: If all users left and no one rejoins within 4 minutes"""
        from datetime import timedelta
        four_min_ago = timezone.now() - timedelta(minutes=4)
        # If no activity for 4+ minutes AND 0 online users
        return self.last_activity < four_min_ago and self.get_online_count() == 0

    def should_auto_delete(self):
        """Check all auto-delete conditions"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Check if migration has been applied (last_activity field exists)
        if not hasattr(self, 'last_activity'):
            return False, "missing_last_activity"
        
        try:
            online_count = self.get_online_count()
            
            # Condition 1: Group is opened with 0 users online
            if online_count == 0:
                # Condition 2: New group with no joins in 5 minutes
                five_min_ago = timezone.now() - timedelta(minutes=5)
                if self.created_at < five_min_ago:
                    return True, "new_empty_5min"
                
                # Condition 4: All users left, 4+ minutes passed
                four_min_ago = timezone.now() - timedelta(minutes=4)
                if self.last_activity < four_min_ago:
                    return True, "all_left_4min"
            
            return False, "active"
        except Exception as e:
            print(f"Error checking auto-delete: {str(e)}")
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