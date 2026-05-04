"""
Management command to create a default admin user if none exists.
Useful for Render deployments where database resets frequently.

Usage:
    python manage.py create_default_admin
    python manage.py create_default_admin --username=admin --email=admin@example.com --password=admin123
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
import os
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Create a default Django admin/superuser if none exist'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default=None,
            help='Admin username (default: admin)'
        )
        parser.add_argument(
            '--email',
            type=str,
            default=None,
            help='Admin email (default: admin@example.com)'
        )
        parser.add_argument(
            '--password',
            type=str,
            default=None,
            help='Admin password (default: generated from env or prompt)'
        )

    def handle(self, *args, **options):
        # Check if any superuser exists
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(
                self.style.SUCCESS(
                    '✅ Admin user(s) already exist. Skipping creation.'
                )
            )
            return

        # Get credentials
        username = options.get('username') or os.getenv('DEFAULT_ADMIN_USERNAME', 'admin')
        email = options.get('email') or os.getenv('DEFAULT_ADMIN_EMAIL', 'admin@example.com')
        password = options.get('password') or os.getenv('DEFAULT_ADMIN_PASSWORD', 'Admin@123')

        # Validate
        if not username or not email or not password:
            self.stdout.write(
                self.style.ERROR(
                    '❌ Missing credentials. Provide via arguments or environment variables.'
                )
            )
            return

        if len(password) < 8:
            self.stdout.write(
                self.style.ERROR(
                    '❌ Password must be at least 8 characters long.'
                )
            )
            return

        # Create superuser
        try:
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Default admin created successfully!\n'
                    f'   Username: {username}\n'
                    f'   Email: {email}\n'
                    f'   Access: /admin/'
                )
            )
            logger.info(f"✅ Default admin user created: {username}")
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error creating admin: {str(e)}')
            )
            logger.error(f"Error creating default admin: {str(e)}")
