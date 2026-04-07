from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User

class Group(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)

class Message(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)