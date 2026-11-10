
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from .models import User
from .views import edit_account


class AdminEditProtectionTests(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = User(
            username="edit_admin",
            email="edit_admin@example.com",
            role=User.Role.ADMIN,
            must_change_password=True,
        )
        self.admin.set_password("OriginalPassword123!")
        self.admin.save()

    def submit(self, user, data):
        request = self.factory.patch(
            "/api/edit/",
            data,
            format="json",
        )

        with patch(
            "account.views.get_user_from_token",
            return_value=user,
        ):
            return edit_account(request)

    def test_temporary_admin_cannot_edit_profile(self):
        response = self.submit(
            self.admin,
            {"username": "changed_admin"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.data["error"],
            "Password change required",
        )

        self.admin.refresh_from_db()
        self.assertEqual(self.admin.username, "edit_admin")

    def test_admin_cannot_change_password_through_edit(self):
        self.admin.must_change_password = False
        self.admin.save(update_fields=["must_change_password"])

        for field in ("password", "password_confirm"):
            with self.subTest(field=field):
                response = self.submit(
                    self.admin,
                    {field: "AnotherPassword123!"},
                )

                self.assertEqual(response.status_code, 403)

        self.admin.refresh_from_db()
        self.assertTrue(
            self.admin.check_password("OriginalPassword123!")
        )

    def test_admin_can_edit_profile_after_password_change(self):
        self.admin.must_change_password = False
        self.admin.save(update_fields=["must_change_password"])

        response = self.submit(
            self.admin,
            {"username": "updated_admin"},
        )

        self.assertEqual(response.status_code, 200)

        self.admin.refresh_from_db()
        self.assertEqual(self.admin.username, "updated_admin")

    def test_main_admin_cannot_change_password_through_edit(self):
        main_admin = User(
            username="main_admin_edit",
            email="main_admin_edit@example.com",
            role=User.Role.MAIN_ADMIN,
        )
        main_admin.set_password("OriginalPassword123!")
        main_admin.save()

        response = self.submit(
            main_admin,
            {"password": "AnotherPassword123!"},
        )

        self.assertEqual(response.status_code, 403)

        main_admin.refresh_from_db()
        self.assertTrue(
            main_admin.check_password("OriginalPassword123!")
        )

    def test_student_can_still_edit_profile(self):
        student = User(
            username="edit_student",
            email="edit_student@example.com",
            role=User.Role.STUDENT,
        )
        student.set_password("StudentPassword123!")
        student.save()

        response = self.submit(
            student,
            {"username": "updated_student"},
        )

        self.assertEqual(response.status_code, 200)

        student.refresh_from_db()
        self.assertEqual(student.username, "updated_student")
