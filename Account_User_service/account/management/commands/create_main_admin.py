
from getpass import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction

from account.models import User


class Command(BaseCommand):
    help = "Create the initial Main Admin account"

    def handle(self, *args, **options):

        # Prevent creating another Main Admin
        if User.objects.filter(role=User.Role.MAIN_ADMIN).exists():
            raise CommandError("Main Admin already exists.")

        # Collect account information
        username = input("Username: ").strip()
        email = input("Email: ").strip().lower()

        if not username or not email:
            raise CommandError("Username and email are required.")

        try:
            validate_email(email)
        except ValidationError:
            raise CommandError("Invalid email address.")

        if User.objects.filter(username=username).exists():
            raise CommandError("Username already exists.")

        if User.objects.filter(email=email).exists():
            raise CommandError("Email already exists.")

        # Read password without displaying it
        password = getpass("Password: ")
        confirm_password = getpass("Confirm password: ")

        if password != confirm_password:
            raise CommandError("Passwords do not match.")

        # Prepare Main Admin account
        admin = User(
            username=username,
            email=email,
            role=User.Role.MAIN_ADMIN,
            must_change_password=False,
        )

        # Apply Django password validators
        try:
            validate_password(password, user=admin)
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages))

        admin.set_password(password)

        # Save account
        try:
            with transaction.atomic():
                if User.objects.filter(
                    role=User.Role.MAIN_ADMIN
                ).exists():
                    raise CommandError("Main Admin already exists.")

                admin.save()

        except IntegrityError:
            raise CommandError("Failed to create Main Admin account.")

        self.stdout.write(
            self.style.SUCCESS("Main Admin created successfully.")
        )
