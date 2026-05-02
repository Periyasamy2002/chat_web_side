from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from chatapp.models import UserProfile


class Command(BaseCommand):
    help = 'Create an admin user if it does not exist'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='admin123', help='Admin username')
        parser.add_argument('--password', type=str, default='Admin@123', help='Admin password')
        parser.add_argument('--email', type=str, default='admin@chat.com', help='Admin email')

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        email = options['email']

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'User {username} already exists'))
            return

        # Create superuser
        user = User.objects.create_superuser(username=username, email=email, password=password)
        
        # Ensure UserProfile exists and is approved
        profile, created = UserProfile.objects.get_or_create(
            user=user,
            defaults={'is_approved': True}
        )
        
        if not created:
            profile.is_approved = True
            profile.save()

        self.stdout.write(self.style.SUCCESS(f'✅ Admin user "{username}" created successfully'))
        self.stdout.write(f'   Email: {email}')
        self.stdout.write(f'   Password: {password}')
