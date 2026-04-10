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
        
        # Get unique session IDs that have messages in this group
        group_users = self.messages.values_list('session_id', flat=True).distinct()
        
        # Count how many of those users are currently online
        online_in_group = AnonymousUser.objects.filter(
            session_id__in=group_users,
            is_online=True,
            last_seen__gte=five_min_ago
        ).count()
        
        print(f"[GROUP {self.code}] Group online users: {online_in_group} (from {len(group_users)} total users), Age: {(timezone.now() - self.created_at).total_seconds() / 60:.1f} min, Inactivity: {(timezone.now() - self.last_activity).total_seconds() / 60:.1f} min")
        
        return online_in_group

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
        """Check all auto-delete conditions - CONSOLIDATED VERSION"""
        from django.utils import timezone
        from datetime import timedelta
        
        try:
            # Get group-specific online count
            online_count = self.get_group_online_count()
            age_minutes = (timezone.now() - self.created_at).total_seconds() / 60
            inactivity_minutes = (timezone.now() - self.last_activity).total_seconds() / 60
            
            # Condition 1: Group opened with 0 users online
            if online_count == 0:
                # Condition 2: New group with no joins in 5 minutes (5+ min old, 0 users)
                if age_minutes >= 5:
                    reason = f"new_empty_5min (age={age_minutes:.1f}min, inactivity={inactivity_minutes:.1f}min)"
                    print(f"[DELETE CHECK] Group {self.code}: DELETE (Condition 2) - {reason}")
                    return True, "new_empty_5min"
                
                # Condition 3: All users left for 4+ minutes
                if inactivity_minutes >= 4:
                    reason = f"all_left_4min (inactivity={inactivity_minutes:.1f}min)"
                    print(f"[DELETE CHECK] Group {self.code}: DELETE (Condition 3) - {reason}")
                    return True, "all_left_4min"
                
                print(f"[DELETE CHECK] Group {self.code}: KEEP (0 users but too new/fresh: age={age_minutes:.1f}min, inactivity={inactivity_minutes:.1f}min)")
                return False, "too_new_or_fresh"
            
            # Group has online users - keep it
            print(f"[DELETE CHECK] Group {self.code}: KEEP ({online_count} online users)")
            return False, "active"
        
        except Exception as e:
            print(f"[DELETE ERROR] Group {self.code}: Error checking auto-delete: {str(e)}")
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
    
    # Translation support
    translated_content = models.TextField(blank=True, null=True, help_text='Cached translation of original content')
    translated_language = models.CharField(max_length=50, blank=True, default='', help_text='Language that translated_content is in')
    
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