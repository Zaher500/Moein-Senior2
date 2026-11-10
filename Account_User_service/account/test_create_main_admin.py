
from django.db import IntegrityError, transaction
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .models import User, Student


class CreateMainAdminCommandTests(TestCase):

    @patch(
        "account.management.commands.create_main_admin.getpass",
        side_effect=["K7#mQ2pL9!xR", "K7#mQ2pL9!xR"],
    )
    @patch(
        "builtins.input",
        side_effect=["main_admin", "main@example.com"],
    )
    def test_create_main_admin_successfully(self, mock_input, mock_getpass):
        call_command("create_main_admin", stdout=StringIO())

        admin = User.objects.get(username="main_admin")

        self.assertEqual(admin.role, User.Role.MAIN_ADMIN)
        self.assertFalse(admin.must_change_password)
        self.assertTrue(admin.check_password("K7#mQ2pL9!xR"))
        self.assertNotEqual(admin.password, "K7#mQ2pL9!xR")
        self.assertEqual(Student.objects.count(), 0)

    def test_cannot_create_second_main_admin(self):
        admin = User(
            username="existing_admin",
            email="existing@example.com",
            role=User.Role.MAIN_ADMIN,
        )
        admin.set_password("K7#mQ2pL9!xR")
        admin.save()

        with self.assertRaisesMessage(
            CommandError,
            "Main Admin already exists.",
        ):
            call_command("create_main_admin", stdout=StringIO())

        self.assertEqual(
            User.objects.filter(role=User.Role.MAIN_ADMIN).count(),
            1,
        )

    @patch(
        "account.management.commands.create_main_admin.getpass",
        side_effect=["K7#mQ2pL9!xR", "DifferentPassword123!"],
    )
    @patch(
        "builtins.input",
        side_effect=["main_admin", "main@example.com"],
    )
    def test_password_mismatch(self, mock_input, mock_getpass):
        with self.assertRaisesMessage(
            CommandError,
            "Passwords do not match.",
        ):
            call_command("create_main_admin", stdout=StringIO())

        self.assertEqual(User.objects.count(), 0)

    def test_database_rejects_second_main_admin(self):
        # Create the first Main Admin
        User.objects.create(
            username="main_admin_1",
            email="main1@example.com",
            role=User.Role.MAIN_ADMIN,
        )

        # Attempt to create a second Main Admin directly
        # through the ORM, bypassing our management command.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create(
                    username="main_admin_2",
                    email="main2@example.com",
                    role=User.Role.MAIN_ADMIN,
                )

        # Verify that only one Main Admin exists
        self.assertEqual(
            User.objects.filter(role=User.Role.MAIN_ADMIN).count(),
            1,
        )


#The Main Admin has been successfully created; ensure that the password is stored in an encrypted format and that there is no associated Student Profile.
#Attempt to create a second Main Admin, and verify that the system rejects it.
#Entering two non-matching passwords, and verifying that the account is not created.