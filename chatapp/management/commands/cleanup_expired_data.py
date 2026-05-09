from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import os

from chatapp.models import Group, Message, AnonymousUser, TranslationCache


class Command(BaseCommand):
    help = 'Cleanup expired groups, messages, voice files, translated audio, and stale cache.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=2,
            help='Delete groups and media older than this many hours when inactive.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting files or DB records.',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Display detailed cleanup information.',
        )

    def handle(self, *args, **options):
        hours = options['hours']
        dry_run = options['dry_run']
        verbose = options['verbose']

        cutoff = timezone.now() - timedelta(hours=hours)
        self.stdout.write(self.style.SUCCESS(f'Running expired cleanup for groups inactive for {hours} hours...'))

        groups = Group.objects.filter(last_activity__lt=cutoff)
        deleted_groups = 0
        deleted_messages = 0
        deleted_files = 0

        for group in groups:
            online_count = group.get_group_online_count()
            if online_count > 0:
                if verbose:
                    self.stdout.write(self.style.WARNING(f'Skipping active group {group.code} (online users: {online_count})'))
                continue

            message_count = group.messages.count()
            if verbose:
                self.stdout.write(self.style.SUCCESS(f'Cleaning group {group.code} (inactive since {group.last_activity})'))
                self.stdout.write(f'  Messages: {message_count}')

            if not dry_run:
                for message in group.messages.all():
                    deleted_files += self._delete_message_files(message, dry_run, verbose)
                    message.delete()
                    deleted_messages += 1
                group.delete()
                deleted_groups += 1
            else:
                deleted_groups += 1
                deleted_messages += message_count

        self.stdout.write(self.style.SUCCESS(f'Groups expired: {deleted_groups}'))
        self.stdout.write(self.style.SUCCESS(f'Messages removed: {deleted_messages}'))
        self.stdout.write(self.style.SUCCESS(f'Files removed: {deleted_files}'))

        cache_deleted = self._cleanup_translation_cache(dry_run, verbose)
        self.stdout.write(self.style.SUCCESS(f'Translation cache entries cleaned: {cache_deleted}'))

        orphan_deleted = self._cleanup_orphan_media(dry_run, verbose)
        self.stdout.write(self.style.SUCCESS(f'Orphan media files cleaned: {orphan_deleted}'))

    def _delete_message_files(self, message, dry_run, verbose):
        deleted = 0
        file_fields = [
            'audio_file',
            'audio_file_english',
            'audio_file_tamil',
            'audio_file_hindi',
            'audio_file_malayalam',
            'audio_file_kannada',
        ]
        for field_name in file_fields:
            file_field = getattr(message, field_name, None)
            if file_field and getattr(file_field, 'path', None):
                path = file_field.path
                if os.path.exists(path):
                    if verbose:
                        self.stdout.write(f'  Deleting file: {path}')
                    if not dry_run:
                        os.remove(path)
                    deleted += 1
        return deleted

    def _cleanup_translation_cache(self, dry_run, verbose):
        stale_cutoff = timezone.now() - timedelta(days=7)
        stale_items = TranslationCache.objects.filter(last_used_at__lt=stale_cutoff)
        count = stale_items.count()
        if verbose:
            self.stdout.write(f'  Stale translation cache entries older than 7 days: {count}')
        if not dry_run:
            stale_items.delete()
        return count

    def _cleanup_orphan_media(self, dry_run, verbose):
        existing_paths = set()
        for message in Message.objects.all():
            for field_name in ['audio_file', 'audio_file_english', 'audio_file_tamil', 'audio_file_hindi', 'audio_file_malayalam', 'audio_file_kannada']:
                file_field = getattr(message, field_name, None)
                if file_field and getattr(file_field, 'path', None):
                    existing_paths.add(os.path.abspath(file_field.path))

        orphan_deleted = 0
        media_root = settings.MEDIA_ROOT
        for root, _, files in os.walk(media_root):
            for filename in files:
                path = os.path.abspath(os.path.join(root, filename))
                if path not in existing_paths:
                    if verbose:
                        self.stdout.write(f'  Orphan file: {path}')
                    if not dry_run:
                        os.remove(path)
                    orphan_deleted += 1
        return orphan_deleted
