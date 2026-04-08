"""
Django management command to cleanup empty and inactive groups.

Usage: python manage.py cleanup_empty_groups

This command:
1. Marks users offline if inactive for 30+ minutes
2. Deletes groups that have been empty for 30+ minutes
3. Provides status report of cleanup actions

Run via cron: */5 * * * * cd /path/to/project && python manage.py cleanup_empty_groups
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from chatapp.models import Group, AnonymousUser


class Command(BaseCommand):
    help = 'Cleanup empty groups and auto-offline inactive users'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']

        if dry_run:
            self.stdout.write(self.style.WARNING('Running in DRY RUN mode - no changes will be made'))

        # Step 1: Auto-mark inactive users as offline
        self.stdout.write(self.style.SUCCESS('\n=== Step 1: Checking inactive users ==='))
        self.auto_offline_inactive_users(verbose, dry_run)

        # Step 2: Delete empty groups
        self.stdout.write(self.style.SUCCESS('\n=== Step 2: Checking empty groups ==='))
        self.delete_empty_groups(verbose, dry_run)

        self.stdout.write(self.style.SUCCESS('\n✓ Cleanup completed'))

    def auto_offline_inactive_users(self, verbose, dry_run):
        """Mark users offline if inactive for 30+ minutes"""
        thirty_min_ago = timezone.now() - timedelta(minutes=30)
        inactive_users = AnonymousUser.objects.filter(
            is_online=True,
            last_seen__lt=thirty_min_ago
        )

        count = inactive_users.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS('✓ No inactive users found'))
            return

        for user in inactive_users:
            if verbose:
                self.stdout.write(
                    f"  Marking offline: {user.user_name} (last seen: {user.last_seen})"
                )

            if not dry_run:
                user.is_online = False
                user.save(update_fields=['is_online'])

        msg = f'Would mark {count} user(s) offline' if dry_run else f'✓ Marked {count} user(s) offline'
        self.stdout.write(self.style.SUCCESS(msg))

    def delete_empty_groups(self, verbose, dry_run):
        """Delete groups with no online users for 30+ minutes"""
        thirty_min_ago = timezone.now() - timedelta(minutes=30)
        five_min_ago = timezone.now() - timedelta(minutes=5)

        # Find groups with no recent activity
        empty_groups = Group.objects.filter(
            last_activity__lt=thirty_min_ago
        )

        deleted_groups = []

        for group in empty_groups:
            # Check if any user was online in last 5 minutes
            recent_online = AnonymousUser.objects.filter(
                is_online=True,
                last_seen__gte=five_min_ago
            ).exists()

            # Also check if group has recent messages
            recent_messages = group.messages.filter(
                timestamp__gte=five_min_ago
            ).exists()

            if not recent_online and not recent_messages:
                deleted_groups.append(group)

                if verbose:
                    message_count = group.messages.count()
                    self.stdout.write(
                        f"  Deleting group: {group.code} "
                        f"(created: {group.created_at}, last activity: {group.last_activity}, "
                        f"messages: {message_count})"
                    )

                if not dry_run:
                    group.delete()

        if not deleted_groups:
            self.stdout.write(self.style.SUCCESS('✓ No empty groups to delete'))
        else:
            msg = (
                f'Would delete {len(deleted_groups)} group(s)'
                if dry_run
                else f'✓ Deleted {len(deleted_groups)} group(s)'
            )
            self.stdout.write(self.style.SUCCESS(msg))
