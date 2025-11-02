"""Django management command to create a superuser if none exists."""
import logging
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


# Configure logger for this module
logger = logging.getLogger(__name__)

User = get_user_model()


class Command(BaseCommand):
    """Management command to automatically create a superuser account.
    
    This command checks if any superuser exists in the database. If no
    superuser is found, it creates one using credentials from environment
    variables or defaults to 'admin' credentials.
    
    Environment Variables:
        DJANGO_SUPERUSER_USERNAME: Username for the superuser (default: 'admin')
        DJANGO_SUPERUSER_EMAIL: Email for the superuser (default: 'admin@example.com')
        DJANGO_SUPERUSER_PASSWORD: Password for the superuser (default: 'admin')
    """

    help = 'Create superuser if none exists'

    def handle(self, *args, **options):
        """Execute the management command.
        
        Args:
            *args: Variable length argument list.
            **options: Arbitrary keyword arguments.
        
        Returns:
            None
        """
        try:
            if not User.objects.filter(is_superuser=True).exists():
                username = os.environ.get(
                    'DJANGO_SUPERUSER_USERNAME',
                    'admin'
                )
                email = os.environ.get(
                    'DJANGO_SUPERUSER_EMAIL',
                    'admin@example.com'
                )
                password = os.environ.get(
                    'DJANGO_SUPERUSER_PASSWORD',
                    'admin'
                )

                User.objects.create_superuser(
                    username=username,
                    email=email,
                    password=password
                )

                success_message = f'Superuser "{username}" created successfully'
                self.stdout.write(self.style.SUCCESS(success_message))
                logger.info(success_message)
            else:
                warning_message = 'Superuser already exists'
                self.stdout.write(self.style.WARNING(warning_message))
                logger.warning(warning_message)

        except Exception as e:
            error_message = f'Failed to create superuser: {str(e)}'
            self.stdout.write(self.style.ERROR(error_message))
            logger.exception(error_message)
            raise
