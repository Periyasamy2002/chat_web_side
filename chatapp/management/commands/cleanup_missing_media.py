"""
Management command to clean up missing media files from the database.

This is useful for ephemeral filesystems like Render where uploaded files
don't persist between deployments. This command removes file references
from the database for files that no longer exist on the filesystem.

Usage:
    python manage.py cleanup_missing_media [--dry-run]
    python manage.py cleanup_missing_media --dry-run  # See what would be deleted
    python manage.py cleanup_missing_media             # Actually delete missing file references
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from chatapp.models import Message, MessageTranslation, DeletedMessage
import os
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clean up database references to missing media files (useful for ephemeral filesystems like Render)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be cleaned without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        mode = '[DRY RUN]' if dry_run else '[EXECUTE]'

        self.stdout.write(self.style.SUCCESS(f'{mode} Starting cleanup of missing media files...'))

        # Count deleted items
        deleted_count = 0
        checked_count = 0

        # =====================================================
        # CLEAN UP MESSAGE AUDIO FILES
        # =====================================================
        self.stdout.write(self.style.HTTP_INFO('\n=== Checking Message audio files ==='))

        messages_with_audio = Message.objects.filter(
            message_type='voice',
            audio_file__isnull=False
        ).exclude(audio_file='')

        for message in messages_with_audio:
            checked_count += 1
            if message.audio_file and message.audio_file.name:
                # Check if file exists
                try:
                    if not message.audio_file.storage.exists(message.audio_file.name):
                        self.stdout.write(
                            self.style.WARNING(
                                f'  Missing: Message {message.id} -> {message.audio_file.name}'
                            )
                        )
                        deleted_count += 1
                        if not dry_run:
                            message.audio_file = ''
                            message.save(update_fields=['audio_file'])
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'  Error checking message {message.id}: {str(e)}')
                    )

        # =====================================================
        # CLEAN UP TRANSLATION AUDIO FILES
        # =====================================================
        self.stdout.write(self.style.HTTP_INFO('\n=== Checking MessageTranslation audio files ==='))

        translations_with_audio = MessageTranslation.objects.filter(
            audio_file__isnull=False
        ).exclude(audio_file='')

        for translation in translations_with_audio:
            checked_count += 1
            if translation.audio_file and translation.audio_file.name:
                try:
                    if not translation.audio_file.storage.exists(translation.audio_file.name):
                        self.stdout.write(
                            self.style.WARNING(
                                f'  Missing: Translation {translation.id} ({translation.language}) -> {translation.audio_file.name}'
                            )
                        )
                        deleted_count += 1
                        if not dry_run:
                            translation.audio_file = ''
                            translation.save(update_fields=['audio_file'])
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'  Error checking translation {translation.id}: {str(e)}')
                    )

        # =====================================================
        # CLEAN UP DELETED MESSAGE AUDIO FILES
        # =====================================================
        self.stdout.write(self.style.HTTP_INFO('\n=== Checking DeletedMessage audio files ==='))

        deleted_messages = DeletedMessage.objects.filter(
            audio_file__isnull=False
        ).exclude(audio_file='')

        for deleted_msg in deleted_messages:
            checked_count += 1
            if deleted_msg.audio_file and deleted_msg.audio_file.name:
                try:
                    if not deleted_msg.audio_file.storage.exists(deleted_msg.audio_file.name):
                        self.stdout.write(
                            self.style.WARNING(
                                f'  Missing: DeletedMessage {deleted_msg.id} -> {deleted_msg.audio_file.name}'
                            )
                        )
                        deleted_count += 1
                        if not dry_run:
                            deleted_msg.audio_file = ''
                            deleted_msg.save(update_fields=['audio_file'])
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'  Error checking deleted message {deleted_msg.id}: {str(e)}')
                    )

        # =====================================================
        # SUMMARY
        # =====================================================
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
        self.stdout.write(self.style.SUCCESS(f'Checked: {checked_count} files'))
        self.stdout.write(self.style.SUCCESS(f'Missing: {deleted_count} files'))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'\n[DRY RUN] Would have cleaned {deleted_count} file references'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\n[EXECUTED] Cleaned {deleted_count} file references from database'
            ))

        self.stdout.write(self.style.SUCCESS('=' * 60))
