import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import User

User = get_user_model()


class Command(BaseCommand):
    help = 'Creates a default Talent Verify admin user from environment variables'

    def handle(self, *args, **options):
        email = os.environ.get('TV_ADMIN_EMAIL')
        password = os.environ.get('TV_ADMIN_PASSWORD')

        if not email:
            self.stdout.write(
                self.style.ERROR('TV_ADMIN_EMAIL environment variable is not set')
            )
            return

        if not password:
            self.stdout.write(
                self.style.ERROR('TV_ADMIN_PASSWORD environment variable is not set')
            )
            return

        # Check if user already exists
        if User.objects.filter(email=email).exists():
            self.stdout.write(
                self.style.WARNING(f'User with email {email} already exists')
            )
            return

        # Create the Talent Verify admin user
        try:
            user = User.objects.create_user(
                email=email,
                password=password,
                role='tv_admin',
                is_staff=True,
                is_superuser=True,
                is_active=True
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully created Talent Verify admin user: {email}'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating user: {str(e)}')
            )
