from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User

class Group(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)

    def __str__(self):
        return self.name

class Message(models.Model):
    MESSAGE_TYPE_CHOICES = [
        ('text', 'Text'),
        ('voice', 'Voice'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    content = models.TextField(blank=True, null=True)  # For text messages
    audio_file = models.FileField(upload_to='voice_messages/', blank=True, null=True)  # For voice messages
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPE_CHOICES, default='text')
    duration = models.FloatField(default=0)  # Duration in seconds for voice messages
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.user.username} - {self.message_type}"