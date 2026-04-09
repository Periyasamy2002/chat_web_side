"""
Django management command for automatic group cleanup
Usage: python manage.py cleanup_empty_groups

Features:
- Deletes groups with 0 users for 5+ minutes (new empty)
- Deletes groups with all users left for 4+ minutes
- Shows detailed status reports
- Supports dry-run mode for testing

Run via cron: */2 * * * * cd /path && python manage.py cleanup_empty_groups
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from chatapp.models import Group, AnonymousUser
from chatapp.group_cleanup import check_and_delete_empty_groups, get_all_groups_cleanup_status
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Automatically delete empty groups based on time and activity conditions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--status',
            action='store_true',
            help='Show cleanup status for all groups without deleting',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed deletion information',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        if options['status']:
            self.show_status()
        elif options['dry_run']:
            self.dry_run_cleanup()
        else:
            self.perform_cleanup(options['verbose'])

    def show_status(self):
        """Show cleanup status for all groups"""
        self.stdout.write(self.style.SUCCESS('\n=== GROUP CLEANUP STATUS ===\n'))
        
        statuses = get_all_groups_cleanup_status()
        
        if not statuses:
            self.stdout.write(self.style.WARNING('No groups found'))
            return
        
        for status in statuses:
            color = self.style.ERROR if status['should_delete'] else self.style.SUCCESS
            
            self.stdout.write(color(f"\n📌 Group: {status['code']} ({status['name']})"))
            self.stdout.write(f"   Created: {status['created_at']}")
            self.stdout.write(f"   Last Activity: {status['last_activity']}")
            self.stdout.write(f"   Online Users: {status['online_count']}")
            self.stdout.write(f"   Age: {status['age_minutes']} minutes")
            self.stdout.write(f"   Inactivity: {status['inactivity_minutes']} minutes")
            self.stdout.write(f"   Should Delete: {color(str(status['should_delete']))}")
            if status['should_delete']:
                self.stdout.write(color(f"   Reason: {status['delete_reason']}"))

    def dry_run_cleanup(self):
        """Show what would be deleted without actually deleting"""
        self.stdout.write(self.style.SUCCESS('\n=== DRY RUN: Groups to be deleted ===\n'))
        
        deleted_count = 0
        
        try:
            all_groups = Group.objects.all()
            
            for group in all_groups:
                should_delete, reason = group.should_auto_delete()
                
                if should_delete:
                    online_count = self._get_online_count(group)
                    
                    if online_count == 0:
                        deleted_count += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"❌ Would delete: {group.code} ({group.name})"
                            )
                        )
                        self.stdout.write(f"   Reason: {reason}")
                        self.stdout.write(f"   Age: {self._get_age_minutes(group)} minutes")
                        self.stdout.write(f"   Last Activity: {self._get_inactivity_minutes(group)} minutes ago\n")
            
            if deleted_count == 0:
                self.stdout.write(self.style.SUCCESS('✅ No groups to delete'))
            else:
                self.stdout.write(
                    self.style.WARNING(f'\n❌ Would delete {deleted_count} groups')
                )
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))

    def perform_cleanup(self, verbose=False):
        """Perform actual cleanup"""
        self.stdout.write(self.style.SUCCESS('\n=== RUNNING GROUP CLEANUP ===\n'))
        
        try:
            deleted_count, details = check_and_delete_empty_groups()
            
            if deleted_count == 0:
                self.stdout.write(self.style.SUCCESS('✅ No groups to delete'))
            else:
                self.stdout.write(
                    self.style.SUCCESS(f'\n✅ Deleted {deleted_count} groups:\n')
                )
                
                for detail in details:
                    self.stdout.write(f"   • {detail['group_code']} ({detail['reason']})")
                    if verbose:
                        self.stdout.write(f"     Created: {detail['created_at']}")
                        self.stdout.write(f"     Deleted: {detail['deleted_at']}\n")
            
            self.stdout.write(self.style.SUCCESS('\n=== CLEANUP COMPLETE ===\n'))
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))

    def _get_online_count(self, group):
        """Helper: Get online count for a group"""
        five_min_ago = timezone.now() - timedelta(minutes=5)
        online_users = AnonymousUser.objects.filter(
            is_online=True,
            last_seen__gte=five_min_ago
        )
        
        user_ids_in_group = set()
        for user in online_users:
            has_message = group.messages.filter(
                session_id=user.session_id
            ).exists()
            if has_message:
                user_ids_in_group.add(user.session_id)
        
        return len(user_ids_in_group)

    def _get_age_minutes(self, group):
        """Helper: Get group age in minutes"""
        return round((timezone.now() - group.created_at).total_seconds() / 60, 2)

    def _get_inactivity_minutes(self, group):
        """Helper: Get inactivity duration in minutes"""
        return round((timezone.now() - group.last_activity).total_seconds() / 60, 2)

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
