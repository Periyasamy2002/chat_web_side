from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from chatapp.models import Message
import os

class Command(BaseCommand):
    help = 'Clean up old voice message files'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30, help='Delete files older than N days')

    def handle(self, *args, **options):
        days = options['days']
        cutoff = timezone.now() - timedelta(days=days)
        
        old_messages = Message.objects.filter(
            message_type='voice',
            timestamp__lt=cutoff,
            audio_file__isnull=False
        )
        
        deleted_count = 0
        for msg in old_messages:
            if msg.audio_file and os.path.exists(msg.audio_file.path):
                os.remove(msg.audio_file.path)
                deleted_count += 1
                self.stdout.write(f"Deleted {msg.audio_file.path}")
        
        self.stdout.write(self.style.SUCCESS(f"Cleaned up {deleted_count} old voice files"))