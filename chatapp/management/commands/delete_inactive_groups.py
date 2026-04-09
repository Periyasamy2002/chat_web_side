"""
Management command to delete inactive groups (no activity for 30+ minutes).
Run with: python manage.py delete_inactive_groups
Schedule with cron: */5 * * * * cd /path && python manage.py delete_inactive_groups
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from chatapp.models import Group, AnonymousUser


class Command(BaseCommand):
    help = 'Delete groups that have been inactive for more than 30 minutes (no active users)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print groups that would be deleted without actually deleting them',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Skip if groups don't have last_activity field (migration not applied)
        try:
            Group.objects.all().values_list('last_activity', flat=True)[:1]
        except Exception as e:
            if 'last_activity' in str(e):
                self.stdout.write(
                    self.style.WARNING(
                        'Migration not applied: last_activity field missing. Run: python manage.py migrate'
                    )
                )
                return
            raise

        thirty_min_ago = timezone.now() - timedelta(minutes=30)
        five_min_ago = timezone.now() - timedelta(minutes=5)

        # Find groups with no activity for 30+ minutes
        inactive_groups = Group.objects.filter(last_activity__lt=thirty_min_ago)

        deleted_count = 0
        for group in inactive_groups:
            # Check if group still has online users
            online_count = AnonymousUser.objects.filter(
                is_online=True,
                last_seen__gte=five_min_ago
            ).count()

            # Also check if group has any messages (safety check)
            message_count = group.messages.count()

            if online_count == 0:
                if dry_run:
                    self.stdout.write(
                        f'[DRY RUN] Would delete: {group.code} '
                        f'(last_activity: {group.last_activity}, messages: {message_count}, online: {online_count})'
                    )
                else:
                    group_code = group.code
                    message_ids = list(group.messages.values_list('id', flat=True))
                    group.delete()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Deleted inactive group: {group_code} '
                            f'(messages: {message_count}, online: {online_count})'
                        )
                    )
                    deleted_count += 1

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(f'\n✓ Successfully deleted {deleted_count} inactive groups')
            )
        else:
            self.stdout.write(
                f'\n[DRY RUN] Would delete {len(list(inactive_groups))} inactive groups'
            )

        # Summary statistics
        total_groups = Group.objects.count()
        total_messages = sum(g.messages.count() for g in Group.objects.all())
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSummary: {total_groups} groups total, {total_messages} messages total'
            )
        )
